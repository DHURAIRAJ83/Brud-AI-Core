"""MB-15: Caption report -- pure. A real backend call produces exactly
one generated caption text; short/medium are truncations of that same
real text, never independently generated. `long_description` mirrors
the same text rather than fabricating extra detail from a second,
unverified prompt shape. Always `verified: false` -- caption
correctness is never confirmed automatically.
"""

from __future__ import annotations

from typing import Any

SHORT_CAPTION_CHARS = 80
MEDIUM_CAPTION_CHARS = 240


def build_caption_report(*, provider_available: bool, caption: str | None, confidence: float | None) -> dict[str, Any]:
    if not provider_available or not caption:
        return {
            "provider_available": provider_available, "short_caption": None, "medium_caption": None,
            "long_description": None, "confidence": None, "verified": False,
            "disclosure": "no vision provider produced a real caption for this session",
        }
    return {
        "provider_available": True,
        "short_caption": caption[:SHORT_CAPTION_CHARS],
        "medium_caption": caption[:MEDIUM_CAPTION_CHARS],
        "long_description": caption,
        "confidence": confidence,
        "verified": False,
        "language_independent": True,
    }
