"""MB-10: Citation Analyzer -- pure, rule-based, no AI. Looks for
surface-level citation markers in provider output text: URLs,
"according to"/"source:"-style phrases, numbered references, and
parenthetical years. This is a heuristic presence check, not a
verification that any cited source is real or accurate -- MB-10 has
no way to check that, and never claims to.
"""

from __future__ import annotations

import re
from typing import Any

_URL_PATTERN = re.compile(r"https?://\S+")
_YEAR_PATTERN = re.compile(r"\((?:19|20)\d{2}\)")
_NUMBERED_REFERENCE_PATTERN = re.compile(r"\[\d+\]")
_ATTRIBUTION_PHRASES = ("according to", "source:", "cited from", "reported by", "per the")


def analyze_citations(*, text: str) -> dict[str, Any]:
    lowered = text.lower()
    url_count = len(_URL_PATTERN.findall(text))
    year_count = len(_YEAR_PATTERN.findall(text))
    numbered_reference_count = len(_NUMBERED_REFERENCE_PATTERN.findall(text))
    attribution_phrase_count = sum(1 for phrase in _ATTRIBUTION_PHRASES if phrase in lowered)

    total_markers = url_count + year_count + numbered_reference_count + attribution_phrase_count
    citation_score = min(100.0, total_markers * 20.0)

    return {
        "url_count": url_count, "year_reference_count": year_count,
        "numbered_reference_count": numbered_reference_count,
        "attribution_phrase_count": attribution_phrase_count,
        "total_citation_markers": total_markers,
        "citation_score": round(citation_score, 1),
        "has_any_citation": total_markers > 0,
    }
