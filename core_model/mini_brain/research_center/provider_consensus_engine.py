"""MB-10: Provider Consensus Engine -- pure. Combines already-computed
duplicate and conflict resolutions (from `duplicate_resolver`/
`conflict_resolver`, themselves built on the existing, reused
`ExternalDatasetDuplicateService`) into an agreement verdict across
providers. Never re-detects duplicates or conflicts itself.
"""

from __future__ import annotations

from typing import Any


def build_consensus(
    *, provider_outputs: list[dict[str, Any]], duplicate_resolution: dict[str, Any],
    conflict_resolution: dict[str, Any],
) -> dict[str, Any]:
    provider_count = len(provider_outputs)
    has_conflicts = conflict_resolution["has_unresolved_conflicts"]
    independent_signals = duplicate_resolution["independent_signal_count"]

    if provider_count == 0:
        agreement_score = 0.0
        verdict = "no_data"
    elif has_conflicts:
        agreement_score = 30.0
        verdict = "conflicting"
    elif independent_signals >= 2 and duplicate_resolution["duplicate_group_count"] > 0:
        agreement_score = 90.0
        verdict = "strong_agreement"
    elif provider_count >= 2:
        agreement_score = 60.0
        verdict = "partial_agreement"
    else:
        agreement_score = 40.0
        verdict = "single_source"

    return {
        "provider_count": provider_count,
        "agreement_score": agreement_score,
        "verdict": verdict,
        "duplicate_summary": {
            "duplicate_group_count": duplicate_resolution["duplicate_group_count"],
            "independent_signal_count": independent_signals,
        },
        "conflict_summary": {
            "conflict_count": conflict_resolution["conflict_count"],
            "has_unresolved_conflicts": has_conflicts,
        },
        "traceable_outputs": [
            {"provider": o["provider"], "output_text": o["output_text"]} for o in provider_outputs
        ],
    }
