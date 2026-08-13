from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal
from urllib.parse import urljoin, urlparse

from pydantic import BaseModel, Field


ArtifactProfile = Literal["standard", "deep-research"]
SourceType = Literal["company", "web"]

DEEP_RESEARCH_PATTERNS = (
    r"\bcomplete\b",
    r"\bcomprehensive\b",
    r"\bin[- ]depth\b",
    r"\bmarket analysis\b",
    r"\bmarket research\b",
    r"\bfeasibility (?:study|analysis)\b",
    r"\bbusiness plan\b",
    r"\bcompetitive analysis\b",
)

PRIMARY_SOURCE_HOSTS = {
    "canada.ca",
    "cdc.gov",
    "ec.europa.eu",
    "ema.europa.eu",
    "europa.eu",
    "fda.gov",
    "ftc.gov",
    "gov.uk",
    "nih.gov",
    "oecd.org",
    "sec.gov",
    "statcan.gc.ca",
    "who.int",
}

GROUNDING_REDIRECT_HOSTS = {"vertexaisearch.cloud.google.com"}


def artifact_profile(instructions: str, format_name: str = "docx") -> ArtifactProfile:
    if format_name != "docx":
        return "standard"
    lowered = instructions.lower()
    return "deep-research" if any(re.search(pattern, lowered) for pattern in DEEP_RESEARCH_PATTERNS) else "standard"


class ChartSeries(BaseModel):
    name: str = Field(default="Value", max_length=100)
    values: list[float] = Field(default_factory=list, max_length=20)


class ResearchPlan(BaseModel):
    jurisdictions: list[str] = Field(default_factory=list, max_length=8)
    sections: list[str] = Field(default_factory=list, max_length=20)
    queries: list[str] = Field(default_factory=list, max_length=8)
    assumptions: list[str] = Field(default_factory=list, max_length=12)
    regulated_product: bool = False


class EvidenceSource(BaseModel):
    ordinal: int = Field(ge=1)
    source_type: SourceType
    title: str = Field(max_length=1000)
    publisher: str | None = Field(default=None, max_length=500)
    url: str | None = Field(default=None, max_length=2000)
    location: str | None = Field(default=None, max_length=500)
    excerpt: str = Field(default="", max_length=8000)
    retrieved_at: datetime | str | None = None
    identifiers: dict[str, str | int | None] = Field(default_factory=dict)


def build_evidence_registry(
    *,
    company_sources: list[dict[str, Any]],
    web_sources: list[dict[str, Any]],
) -> tuple[EvidenceSource, ...]:
    registry: list[EvidenceSource] = []
    for source_type, sources in (("company", company_sources), ("web", web_sources)):
        for item in sources:
            registry.append(EvidenceSource(
                ordinal=len(registry) + 1,
                source_type=source_type,
                title=item.get("title") or ("Authorized company evidence" if source_type == "company" else "Web source"),
                publisher=item.get("publisher"),
                url=item.get("url"),
                location=item.get("location"),
                excerpt=item.get("excerpt") or "",
                retrieved_at=item.get("retrieved_at"),
                identifiers={key: item.get(key) for key in ("knowledge_base_id", "document_id", "version_id", "chunk_id") if key in item},
            ))
    return tuple(registry)


@dataclass(frozen=True)
class CitationNormalizationResult:
    text: str
    invalid_markers: tuple[str, ...] = ()


LEGACY_CITATION_RE = re.compile(
    r"\[(?:(?P<company>Company source)|(?P<web>Web (?:source|content)))\s+(?P<ordinal>\d+)\]",
    re.IGNORECASE,
)
NUMERIC_CITATION_RE = re.compile(r"\[(?P<ordinal>\d+)\]")


def normalize_citations(
    value: str,
    *,
    company_count: int,
    web_count: int,
    strict: bool = False,
) -> CitationNormalizationResult:
    """Normalize model citation labels to a single final ordinal namespace."""

    invalid: list[str] = []
    total = company_count + web_count

    def replace_legacy(match: re.Match[str]) -> str:
        local_ordinal = int(match.group("ordinal"))
        if match.group("company"):
            final_ordinal = local_ordinal
            valid = 1 <= local_ordinal <= company_count
        else:
            final_ordinal = company_count + local_ordinal
            valid = 1 <= local_ordinal <= web_count
        if not valid:
            invalid.append(match.group(0))
            return "" if strict else match.group(0)
        return f"[{final_ordinal}]"

    normalized = LEGACY_CITATION_RE.sub(replace_legacy, value)

    def validate_numeric(match: re.Match[str]) -> str:
        ordinal = int(match.group("ordinal"))
        if total and 1 <= ordinal <= total:
            return match.group(0)
        invalid.append(match.group(0))
        return "" if strict else match.group(0)

    normalized = NUMERIC_CITATION_RE.sub(validate_numeric, normalized)
    return CitationNormalizationResult(normalized, tuple(dict.fromkeys(invalid)))


class CitationStreamNormalizer:
    """Preserve streaming while holding only a possible partial citation marker."""

    def __init__(self, *, company_count: int, web_count: int):
        self.company_count = company_count
        self.web_count = web_count
        self.buffer = ""

    def feed(self, chunk: str) -> str:
        self.buffer += chunk
        last_open = self.buffer.rfind("[")
        if last_open < 0:
            ready, self.buffer = self.buffer, ""
        elif "]" in self.buffer[last_open:]:
            ready, self.buffer = self.buffer, ""
        else:
            ready, self.buffer = self.buffer[:last_open], self.buffer[last_open:]
        return normalize_citations(
            ready,
            company_count=self.company_count,
            web_count=self.web_count,
        ).text

    def flush(self) -> str:
        ready, self.buffer = self.buffer, ""
        return normalize_citations(
            ready,
            company_count=self.company_count,
            web_count=self.web_count,
        ).text


def source_is_primary(source: dict[str, Any]) -> bool:
    host = (urlparse(source.get("url") or "").hostname or "").lower()
    publisher = (source.get("publisher") or "").lower()
    values = (host, publisher)
    return any(
        value.endswith(".gov")
        or value.endswith(".edu")
        or any(value == candidate or value.endswith(f".{candidate}") for candidate in PRIMARY_SOURCE_HOSTS)
        for value in values
    )


def deduplicate_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    output: list[dict[str, Any]] = []
    for source in sources:
        url = (source.get("url") or "").strip()
        title = re.sub(r"\s+", " ", source.get("title") or "").strip()
        key = ("url", url.lower().rstrip("/")) if url else (title.lower(), (source.get("publisher") or "").lower())
        if key in seen:
            continue
        seen.add(key)
        output.append({**source, "title": title or url})
    return output


def _host_is_public(host: str) -> bool:
    try:
        address = ipaddress.ip_address(host)
        return not (address.is_private or address.is_loopback or address.is_link_local or address.is_reserved or address.is_multicast)
    except ValueError:
        pass
    try:
        results = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError:
        return False
    for result in results:
        address = ipaddress.ip_address(result[4][0])
        if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved or address.is_multicast:
            return False
    return bool(results)


async def canonicalize_grounding_url(url: str) -> str:
    """Resolve only Google's grounding redirect URLs and reject non-public destinations."""

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or (parsed.hostname or "").lower() not in GROUNDING_REDIRECT_HOSTS:
        return url
    try:
        import httpx

        current = url
        async with httpx.AsyncClient(follow_redirects=False, timeout=4.0) as client:
            for _ in range(5):
                response = await client.head(current)
                if response.status_code in {405, 501}:
                    response = await client.get(current, headers={"Range": "bytes=0-0"})
                if response.status_code not in {301, 302, 303, 307, 308}:
                    return current
                location = response.headers.get("location")
                if not location:
                    return url
                candidate = urljoin(current, location)
                final = urlparse(candidate)
                if final.scheme not in {"http", "https"} or not final.hostname:
                    return url
                if not await asyncio.to_thread(_host_is_public, final.hostname):
                    return url
                current = candidate
        return url
    except Exception:
        return url


def strip_source_markers(value: str) -> str:
    value = LEGACY_CITATION_RE.sub("", value)
    return NUMERIC_CITATION_RE.sub("", value)


def retrieved_label(value: datetime | str | None) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, str) and value:
        return value[:10]
    return ""
