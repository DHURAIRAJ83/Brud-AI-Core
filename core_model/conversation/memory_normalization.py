"""Per-category memory value normalization.

Normalization is bounded and conservative: it maps a small, known set
of values onto a canonical form for reliable retrieval/deduplication,
and otherwise preserves the admin/user's original wording as the
``display_value`` rather than aggressively rewriting meaning.
"""

from __future__ import annotations

_LANGUAGE_PREFERENCE_MAP = {
    "tamil": "ta", "தமிழ்": "ta", "ta": "ta",
    "english": "en", "en": "en",
    "tanglish": "tgl", "tgl": "tgl",
    "mixed": "mixed", "both": "mixed",
}
_FORMAT_PREFERENCE_MAP = {
    "short": "short", "brief": "short",
    "detailed": "detailed", "long": "detailed",
    "step by step": "step_by_step", "step_by_step": "step_by_step",
    "table": "table",
    "code first": "code_first", "code_first": "code_first",
}

MAXIMUM_NORMALIZED_LENGTH = 200


def normalize_language_preference(value: str) -> str:
    key = value.strip().lower()
    return _LANGUAGE_PREFERENCE_MAP.get(key, "unknown")


def normalize_format_preference(value: str) -> str:
    key = value.strip().lower()
    return _FORMAT_PREFERENCE_MAP.get(key, "unknown")


def normalize_bounded_text(value: str) -> str:
    """Whitespace-collapsing, length-bounded normalization used for
    project/preference/fact categories -- preserves meaning, does not
    rewrite it."""

    collapsed = " ".join(value.strip().split())
    return collapsed[:MAXIMUM_NORMALIZED_LENGTH]


def normalize_memory_value(category: str, display_value: str) -> dict[str, str]:
    if category == "language_preference":
        normalized = normalize_language_preference(display_value)
    elif category == "format_preference":
        normalized = normalize_format_preference(display_value)
    else:
        normalized = normalize_bounded_text(display_value)
    return {"normalized_value": normalized, "display_value": display_value.strip()}
