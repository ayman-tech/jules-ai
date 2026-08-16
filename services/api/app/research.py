from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

from pydantic import BaseModel, Field


ArtifactProfile = Literal["standard", "deep-research"]
ResearchMode = Literal["auto", "standard", "deep"]
SourceType = Literal["company", "web"]
SourceClass = Literal["primary", "independent_secondary", "commercial_estimate", "vendor_promotional", "unknown"]

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
    "bmj.com",
    "canada.ca",
    "cdc.gov",
    "doi.org",
    "ec.europa.eu",
    "ema.europa.eu",
    "europa.eu",
    "fda.gov",
    "ftc.gov",
    "frontiersin.org",
    "gov.uk",
    "nih.gov",
    "jamanetwork.com",
    "nejm.org",
    "oecd.org",
    "plos.org",
    "sciencedirect.com",
    "sec.gov",
    "statcan.gc.ca",
    "springer.com",
    "wiley.com",
    "who.int",
}

GROUNDING_REDIRECT_HOSTS = {"vertexaisearch.cloud.google.com"}

COMMERCIAL_RESEARCH_HOST_FRAGMENTS = {
    "dataintelo",
    "grandviewresearch",
    "marketresearchfuture",
    "marketsandmarkets",
    "mordorintelligence",
    "precedenceresearch",
    "verifiedmarketresearch",
}
VENDOR_PATH_TERMS = {
    "buy",
    "manufacturer",
    "our-product",
    "our-products",
    "product",
    "products",
    "shop",
    "supplier",
}
INDEPENDENT_SECONDARY_HOSTS = {
    "apnews.com",
    "bbc.com",
    "consumerreports.org",
    "reuters.com",
}
TRACKING_QUERY_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref", "source"}
RELEVANCE_STOPWORDS = {
    "about", "analysis", "and", "are", "business", "complete", "create", "document", "for", "from",
    "give", "how", "in", "into", "market", "north", "of", "on", "plan", "prepare", "report", "research",
    "the", "this", "to", "using", "with",
}


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
    source_class: SourceClass = "unknown"
    confidence: float | None = Field(default=None, ge=0, le=1)


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
                source_class=item.get("source_class") or ("primary" if source_type == "company" else "unknown"),
                confidence=item.get("confidence"),
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
NUMERIC_CITATION_RE = re.compile(r"\[(?P<ordinals>\d+(?:\s*,\s*\d+)*)\]")


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
        ordinals = [int(value.strip()) for value in match.group("ordinals").split(",")]
        valid = [ordinal for ordinal in ordinals if total and 1 <= ordinal <= total]
        invalid.extend(f"[{ordinal}]" for ordinal in ordinals if ordinal not in valid)
        if not strict and len(valid) != len(ordinals):
            return match.group(0)
        return f"[{', '.join(map(str, valid))}]" if valid else ""

    normalized = NUMERIC_CITATION_RE.sub(validate_numeric, normalized)
    return CitationNormalizationResult(normalized, tuple(dict.fromkeys(invalid)))


def citation_ordinals(value: str) -> tuple[int, ...]:
    ordinals: list[int] = []
    for match in NUMERIC_CITATION_RE.finditer(value):
        ordinals.extend(int(item.strip()) for item in match.group("ordinals").split(","))
    return tuple(dict.fromkeys(ordinals))


def remap_citations(value: str, mapping: dict[int, int]) -> str:
    def replace(match: re.Match[str]) -> str:
        mapped = [
            mapping[ordinal]
            for ordinal in (int(item.strip()) for item in match.group("ordinals").split(","))
            if ordinal in mapping
        ]
        return f"[{', '.join(map(str, dict.fromkeys(mapped)))}]" if mapped else ""

    return NUMERIC_CITATION_RE.sub(replace, value)


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


def classify_source(source: dict[str, Any]) -> SourceClass:
    if source_is_primary(source):
        return "primary"
    parsed = urlparse(source.get("url") or "")
    host = (parsed.hostname or "").lower().removeprefix("www.")
    title = (source.get("title") or "").lower()
    path_terms = set(re.findall(r"[a-z0-9]+", parsed.path.lower()))
    if any(fragment in host for fragment in COMMERCIAL_RESEARCH_HOST_FRAGMENTS) or re.search(
        r"\bmarket (?:size|share|forecast|report|research)\b", title
    ):
        return "commercial_estimate"
    if path_terms.intersection(VENDOR_PATH_TERMS) or re.search(
        r"\b(?:buy|shop|our product|manufacturer|supplier|promotional feature)\b", title
    ):
        return "vendor_promotional"
    if host in INDEPENDENT_SECONDARY_HOSTS or host.endswith(".org"):
        return "independent_secondary"
    return "unknown"


def source_is_visibly_relevant(source: dict[str, Any], *, query: str, claim: str) -> bool:
    """Reject obvious query-parameter poisoning without guessing at broad topical relevance."""

    parsed = urlparse(source.get("url") or "")
    if not parsed.query:
        return True
    query_tokens = {
        token for token in re.findall(r"[a-z0-9]+", f"{query} {claim}".lower())
        if len(token) >= 4 and token not in RELEVANCE_STOPWORDS
    }
    visible_tokens = set(re.findall(
        r"[a-z0-9]+",
        f"{source.get('title') or ''} {parsed.hostname or ''} {parsed.path}".lower(),
    ))
    parameter_tokens = set(re.findall(r"[a-z0-9]+", parsed.query.lower()))
    injected_topic = query_tokens.intersection(parameter_tokens)
    return not injected_topic or bool(query_tokens.intersection(visible_tokens))


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


async def url_is_public_http(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    return await asyncio.to_thread(_host_is_public, parsed.hostname)


def canonical_public_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return url.strip()
    host = parsed.hostname.lower()
    try:
        port = parsed.port
    except ValueError:
        return ""
    default_port = (parsed.scheme == "https" and port == 443) or (parsed.scheme == "http" and port == 80)
    host_label = f"[{host}]" if ":" in host else host
    netloc = host_label if port is None or default_port else f"{host_label}:{port}"
    query = urlencode(sorted(
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in TRACKING_QUERY_KEYS
    ))
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    return urlunparse((parsed.scheme.lower(), netloc, path, "", query, ""))


async def canonicalize_grounding_url(url: str) -> str:
    """Resolve only Google's grounding redirect URLs and reject non-public destinations."""

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or (parsed.hostname or "").lower() not in GROUNDING_REDIRECT_HOSTS:
        return canonical_public_url(url)
    try:
        import httpx

        current = url
        async with httpx.AsyncClient(follow_redirects=False, timeout=4.0) as client:
            for _ in range(5):
                response = await client.head(current)
                if response.status_code in {405, 501}:
                    response = await client.get(current, headers={"Range": "bytes=0-0"})
                if response.status_code not in {301, 302, 303, 307, 308}:
                    return canonical_public_url(current)
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
