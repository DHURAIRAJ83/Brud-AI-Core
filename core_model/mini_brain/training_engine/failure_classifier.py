"""MB-22: Failure Classifier -- pure. Classifies an already-reported
error message into a fixed, disclosed category -- never a guess about
a cause the message doesn't actually state.
"""

from __future__ import annotations

from typing import Any

_CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "out_of_memory": ("out of memory", "oom", "memory error", "cannot allocate"),
    "checkpoint_error": ("checkpoint", "corrupt", "checksum mismatch"),
    "resource_unavailable": ("unavailable", "not installed", "not configured"),
    "cancelled": ("cancelled", "canceled", "aborted by admin"),
    "timeout": ("timeout", "timed out"),
}


def classify_failure(*, error_message: str | None) -> dict[str, Any]:
    if not error_message:
        return {"category": "unknown", "matched_keywords": [], "error_message": error_message}

    lowered = error_message.lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        matched = [k for k in keywords if k in lowered]
        if matched:
            return {"category": category, "matched_keywords": matched, "error_message": error_message}

    return {
        "category": "unclassified", "matched_keywords": [], "error_message": error_message,
        "disclosure": "no known category keyword matched -- reported honestly as unclassified rather than guessed",
    }
