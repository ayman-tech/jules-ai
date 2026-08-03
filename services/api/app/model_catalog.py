from __future__ import annotations


DEFAULT_MODEL_ID = "gemini-3.5-flash"
PRO_MODEL_ID = "gemini-3.1-pro-preview"

MODEL_CATALOG = (
    {
        "id": DEFAULT_MODEL_ID,
        "display_name": "Default",
        "supports_effort": True,
        "supports_files": True,
    },
    {
        "id": PRO_MODEL_ID,
        "display_name": "Pro",
        "supports_effort": True,
        "supports_files": True,
    },
)

MODEL_IDS = frozenset(item["id"] for item in MODEL_CATALOG)
LEGACY_MODEL_MAP = {
    "gemini-2.5-flash": DEFAULT_MODEL_ID,
    "gemini-2.5-pro": PRO_MODEL_ID,
}
