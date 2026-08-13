"""MB-08: Priority Engine -- pure. Ranks MB-08's own dataset and
training recommendations using the Knowledge Gap Registry's own real,
already-computed `priority_band` values on the underlying cases --
reusing that system's deterministic, evidence-weighted priority
scoring (`KnowledgeGapPriorityService`) rather than reimplementing a
second scoring formula. A domain's priority is the highest band among
its own cases; the overall training recommendation inherits the
highest band across every case observed in the cycle.

The registry's five bands (critical/high/medium/low/informational) are
mapped onto this task spec's requested four (Critical/High/Medium/Low)
by folding "informational" into "Low" -- a disclosed label mapping,
not a new scoring rule.
"""

from __future__ import annotations

from typing import Any

_BAND_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1, "informational": 0}
_BAND_LABEL = {
    "critical": "Critical", "high": "High", "medium": "Medium",
    "low": "Low", "informational": "Low",
}


def _dominant_band(bands: list[str]) -> str:
    if not bands:
        return "informational"
    return max(bands, key=lambda band: _BAND_RANK.get(band, 0))


def rank_priorities(
    *, dataset_recommendations: list[dict[str, Any]], knowledge_gap_cases: list[dict[str, Any]],
    training_recommendation: dict[str, Any],
) -> dict[str, Any]:
    domain_bands: dict[str, list[str]] = {}
    for case in knowledge_gap_cases:
        domain = case["domain"] or "unclassified"
        domain_bands.setdefault(domain, []).append(case["priority_band"])

    ranked_dataset_recommendations = []
    for rec in dataset_recommendations:
        band = _dominant_band(domain_bands.get(rec["domain"], []))
        ranked_dataset_recommendations.append({**rec, "priority": _BAND_LABEL[band], "_band_rank": _BAND_RANK[band]})
    ranked_dataset_recommendations.sort(key=lambda r: r["_band_rank"], reverse=True)
    for rec in ranked_dataset_recommendations:
        del rec["_band_rank"]

    overall_band = _dominant_band([band for bands in domain_bands.values() for band in bands])
    ranked_training_recommendation = {**training_recommendation, "priority": _BAND_LABEL[overall_band]}

    return {
        "dataset_recommendations": ranked_dataset_recommendations,
        "training_recommendation": ranked_training_recommendation,
    }
