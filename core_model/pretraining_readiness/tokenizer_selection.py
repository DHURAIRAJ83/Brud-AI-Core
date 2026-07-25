"""Tokenizer candidate selection scorecard -- pure functions only.
Never selects a tokenizer merely because it has the largest
vocabulary; prefers the smallest candidate that clears every
dimension at `pass` or an acceptable `warning`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SELECTION_DIMENSIONS = (
    "tamil_fragmentation",
    "tanglish_fragmentation",
    "unknown_token_rate",
    "round_trip_integrity",
    "sequence_efficiency",
    "mixed_script_handling",
    "corpus_sufficiency",
    "training_reproducibility",
    "artifact_integrity",
    "memory_suitability",
)

CANDIDATE_STATUSES = ("rejected", "experimental", "recommended", "production_candidate")


@dataclass(frozen=True)
class SelectionThresholds:
    max_tamil_fragmentation_ratio: float = 2.5
    max_tanglish_fragmentation_ratio: float = 3.0
    max_unknown_token_rate_warning: float = 0.05
    max_unknown_token_rate_fail: float = 0.15
    min_round_trip_integrity_warning: float = 0.98
    min_round_trip_integrity_fail: float = 0.90
    max_chars_per_token_for_efficiency: float = 1.2
    min_chars_per_token_for_efficiency: float = 1.8


DEFAULT_SELECTION_THRESHOLDS = SelectionThresholds()


def score_candidate(
    metrics: dict[str, Any],
    *,
    corpus_sufficiency_state: str,
    thresholds: SelectionThresholds = DEFAULT_SELECTION_THRESHOLDS,
) -> dict[str, str]:
    """``metrics`` carries the real, already-computed evaluation
    numbers for one candidate (fragmentation ratios, unknown-token
    rate, round-trip integrity, chars-per-token, artifact/reproduce
    checksums matched, memory estimate within limit)."""

    results: dict[str, str] = {}

    def _threshold_dimension(
        value: float | None, *, warn: float, fail: float, higher_is_worse: bool
    ) -> str:
        if value is None:
            return "not_evaluated"
        if higher_is_worse:
            if value > fail:
                return "fail"
            if value > warn:
                return "warning"
            return "pass"
        if value < fail:
            return "fail"
        if value < warn:
            return "warning"
        return "pass"

    results["tamil_fragmentation"] = _threshold_dimension(
        metrics.get("tamil_fragmentation_ratio"),
        warn=thresholds.max_tamil_fragmentation_ratio,
        fail=thresholds.max_tamil_fragmentation_ratio * 1.5,
        higher_is_worse=True,
    )
    results["tanglish_fragmentation"] = _threshold_dimension(
        metrics.get("tanglish_fragmentation_ratio"),
        warn=thresholds.max_tanglish_fragmentation_ratio,
        fail=thresholds.max_tanglish_fragmentation_ratio * 1.5,
        higher_is_worse=True,
    )
    results["unknown_token_rate"] = _threshold_dimension(
        metrics.get("unknown_token_rate"),
        warn=thresholds.max_unknown_token_rate_warning,
        fail=thresholds.max_unknown_token_rate_fail,
        higher_is_worse=True,
    )
    results["round_trip_integrity"] = _threshold_dimension(
        metrics.get("round_trip_integrity_rate"),
        warn=thresholds.min_round_trip_integrity_warning,
        fail=thresholds.min_round_trip_integrity_fail,
        higher_is_worse=False,
    )
    chars_per_token = metrics.get("characters_per_token")
    if chars_per_token is None:
        results["sequence_efficiency"] = "not_evaluated"
    elif (
        thresholds.min_chars_per_token_for_efficiency
        <= chars_per_token
        <= thresholds.max_chars_per_token_for_efficiency * 3
    ):
        results["sequence_efficiency"] = "pass"
    elif chars_per_token < thresholds.max_chars_per_token_for_efficiency:
        results["sequence_efficiency"] = "warning"
    else:
        results["sequence_efficiency"] = "pass"
    results["mixed_script_handling"] = _threshold_dimension(
        metrics.get("mixed_script_fragmentation_ratio"),
        warn=thresholds.max_tanglish_fragmentation_ratio,
        fail=thresholds.max_tanglish_fragmentation_ratio * 1.5,
        higher_is_worse=True,
    )
    results["corpus_sufficiency"] = {
        "insufficient": "fail",
        "experimental": "warning",
        "candidate": "pass",
        "production_candidate": "pass",
    }.get(corpus_sufficiency_state, "not_evaluated")
    results["training_reproducibility"] = (
        "pass" if metrics.get("reproducibility_verified") else "not_evaluated"
    )
    results["artifact_integrity"] = (
        "pass" if metrics.get("artifact_checksum_verified") else "fail"
    )
    results["memory_suitability"] = (
        "pass" if metrics.get("within_memory_limit", True) else "fail"
    )
    return results


def classify_candidate(dimension_results: dict[str, str]) -> str:
    """Hard fails (artifact integrity, corpus sufficiency, memory
    suitability, or any fragmentation/unknown-rate fail) reject a
    candidate outright; warnings cap it at `experimental`."""

    if any(status == "fail" for status in dimension_results.values()):
        return "rejected"
    if any(status in ("warning", "not_evaluated") for status in dimension_results.values()):
        return "experimental"
    return "recommended"


def select_recommended_candidate(
    candidates: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """``candidates`` is a list of ``{"vocabulary_size": int,
    "final_status": str, ...}`` rows. Returns the *smallest-vocabulary*
    candidate among the best-status tier -- never the largest, and
    never a rejected one."""

    eligible = [c for c in candidates if c["final_status"] != "rejected"]
    if not eligible:
        return None
    best_status_rank = {"production_candidate": 3, "recommended": 2, "experimental": 1}
    best_rank = max(best_status_rank.get(c["final_status"], 0) for c in eligible)
    tier = [c for c in eligible if best_status_rank.get(c["final_status"], 0) == best_rank]
    return min(tier, key=lambda c: c["vocabulary_size"])
