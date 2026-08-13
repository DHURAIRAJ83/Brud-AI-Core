"""MB-18: Language Distribution Analyzer -- pure. Reuses MB-13's own
already-computed language-quality reports (dominant language, overall
quality score) across every linked dataset session -- never re-scans
or re-scores language itself.
"""

from __future__ import annotations

from typing import Any


def analyze_language_distribution(*, language_sessions: list[dict[str, Any]]) -> dict[str, Any]:
    if not language_sessions:
        return {
            "dominant_language_counts": {}, "average_language_quality": None, "session_count": 0,
            "disclosure": "no MB-13 Language Intelligence session was linked to any collected dataset -- language distribution is honestly unavailable",
        }

    dominant_counts: dict[str, int] = {}
    quality_scores: list[float] = []
    for session in language_sessions:
        dominant = session.get("language_scan_report", {}).get("dominant_language")
        if dominant:
            dominant_counts[dominant] = dominant_counts.get(dominant, 0) + 1
        quality = session.get("quality_score_report", {}).get("overall_language_quality")
        if quality is not None:
            quality_scores.append(quality)

    return {
        "dominant_language_counts": dominant_counts,
        "average_language_quality": round(sum(quality_scores) / len(quality_scores), 1) if quality_scores else None,
        "session_count": len(language_sessions),
    }
