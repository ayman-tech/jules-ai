from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol


ScanStatus = Literal["clean", "infected", "unavailable"]


class MalwareScanner(Protocol):
    async def scan(self, *, name: str, mime_type: str, data: bytes) -> ScanStatus: ...


@dataclass(frozen=True)
class DevelopmentScanner:
    """Replace with a managed malware scanning adapter before production launch."""

    async def scan(self, *, name: str, mime_type: str, data: bytes) -> ScanStatus:
        del name, mime_type, data
        return "clean"


def get_scanner() -> MalwareScanner:
    return DevelopmentScanner()
