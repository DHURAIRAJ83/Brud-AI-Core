"""Deterministic, explainable scoring engine (Step 8). Every dimension
is a pure function returning a `ScoreComponent` -- no randomness, no
external call, no popularity/download-count signal. The same inputs
always produce the same score.
"""

from __future__ import annotations

from dataclasses import dataclass

from core_model.data_discovery import ALL_SCORING_DIMENSIONS, DEFAULT_SCORING_WEIGHTS


@dataclass(frozen=True)
class ScoreComponent:
    dimension: str
    raw_value: float
    weight: float
    score: float
    reason: str


def _component(dimension: str, raw_value: float, weight: float, reason: str) -> ScoreComponent:
    raw_clamped = max(0.0, min(1.0, raw_value))
    return ScoreComponent(
        dimension=dimension, raw_value=raw_clamped, weight=weight,
        score=raw_clamped * weight, reason=reason,
    )


def score_requirement_fit(
    *, matched_fields: int, total_fields: int, weight: float
) -> ScoreComponent:
    raw = matched_fields / total_fields if total_fields else 0.0
    reason = f"{matched_fields}/{total_fields} requirement fields matched"
    return _component("requirement_fit", raw, weight, reason)


def score_language_fit(
    *, requirement_languages: tuple[str, ...], candidate_languages: tuple[str, ...], weight: float
) -> ScoreComponent:
    if not requirement_languages:
        return _component("language_fit", 0.5, weight, "no language requirement specified")
    overlap = set(requirement_languages) & set(candidate_languages)
    raw = len(overlap) / len(requirement_languages)
    matched = sorted(overlap)
    reason = (
        f"{len(overlap)}/{len(requirement_languages)} required language(s) present: {matched}"
        if overlap
        else "no required language present in candidate metadata"
    )
    return _component("language_fit", raw, weight, reason)


def score_task_fit(
    *, requirement_tasks: tuple[str, ...], candidate_tasks: tuple[str, ...], weight: float
) -> ScoreComponent:
    if not requirement_tasks:
        return _component("task_fit", 0.5, weight, "no task requirement specified")
    overlap = set(requirement_tasks) & set(candidate_tasks)
    raw = len(overlap) / len(requirement_tasks)
    reason = (
        f"{len(overlap)}/{len(requirement_tasks)} required task(s) present"
        if overlap
        else "no required task present in candidate metadata"
    )
    return _component("task_fit", raw, weight, reason)


def score_modality_fit(
    *, requirement_modality: str, candidate_modality: str | None, weight: float
) -> ScoreComponent:
    if candidate_modality is None:
        return _component("modality_fit", 0.3, weight, "candidate modality unknown")
    raw = 1.0 if requirement_modality == candidate_modality else 0.0
    reason = (
        f"candidate modality '{candidate_modality}' matches requirement"
        if raw
        else f"candidate modality '{candidate_modality}' does not match requirement "
        f"'{requirement_modality}'"
    )
    return _component("modality_fit", raw, weight, reason)


def score_intended_use_fit(
    *, requirement_uses: tuple[str, ...], candidate_use_signals: tuple[str, ...], weight: float
) -> ScoreComponent:
    if not requirement_uses:
        return _component("intended_use_fit", 0.5, weight, "no intended use specified")
    overlap = set(requirement_uses) & set(candidate_use_signals)
    raw = len(overlap) / len(requirement_uses)
    reason = (
        f"{len(overlap)}/{len(requirement_uses)} intended use(s) plausibly supported"
        if overlap
        else "no intended-use signal found in candidate metadata"
    )
    return _component("intended_use_fit", raw, weight, reason)


def score_metadata_completeness(
    *, present_field_count: int, total_field_count: int, weight: float
) -> ScoreComponent:
    raw = present_field_count / total_field_count if total_field_count else 0.0
    return _component(
        "metadata_completeness", raw, weight,
        f"{present_field_count}/{total_field_count} metadata fields present",
    )


_TRUST_RAW_VALUES = {
    "unverified": 0.2,
    "domain_verified": 0.5,
    "organization_verified": 0.7,
    "government_verified": 0.8,
    "research_verified": 0.8,
    "community_reviewed": 0.6,
    "restricted": 0.1,
    "blocked": 0.0,
}


def score_provider_trust(*, trust_status: str, weight: float) -> ScoreComponent:
    raw = _TRUST_RAW_VALUES.get(trust_status, 0.2)
    return _component("provider_trust", raw, weight, f"provider trust_status='{trust_status}'")


def score_dataset_card_presence(*, present: bool, weight: float) -> ScoreComponent:
    raw = 1.0 if present else 0.0
    reason = "dataset card available" if present else "dataset card missing"
    return _component("dataset_card_presence", raw, weight, reason)


def score_version_traceability(
    *, has_version: bool, has_revision: bool, weight: float
) -> ScoreComponent:
    raw = (int(has_version) + int(has_revision)) / 2
    reason = f"version present={has_version}, revision present={has_revision}"
    return _component("version_traceability", raw, weight, reason)


def score_size_suitability(
    *, download_size_bytes: int | None, maximum_download_size_bytes: int | None, weight: float
) -> ScoreComponent:
    if download_size_bytes is None:
        return _component("size_suitability", 0.5, weight, "download size unknown")
    if maximum_download_size_bytes is None:
        return _component("size_suitability", 0.75, weight, "no maximum size requested")
    if download_size_bytes <= maximum_download_size_bytes:
        return _component("size_suitability", 1.0, weight, "within requested maximum size")
    return _component("size_suitability", 0.2, weight, "exceeds requested maximum size")


def score_format_suitability(
    *, candidate_formats: tuple[str, ...], preferred_formats: tuple[str, ...], weight: float
) -> ScoreComponent:
    if not preferred_formats:
        return _component("format_suitability", 0.5, weight, "no format preference specified")
    if not candidate_formats:
        return _component("format_suitability", 0.3, weight, "candidate file formats unknown")
    overlap = {f.lower() for f in candidate_formats} & {f.lower() for f in preferred_formats}
    raw = 1.0 if overlap else 0.2
    matched = sorted(overlap)
    reason = f"matches preferred format(s): {matched}" if overlap else "no preferred format present"
    return _component("format_suitability", raw, weight, reason)


def score_recency(*, last_modified_at: str | None, weight: float) -> ScoreComponent:
    if not last_modified_at:
        return _component("recency", 0.3, weight, "last_modified_at unknown")
    return _component("recency", 0.7, weight, f"last modified at {last_modified_at}")


def score_accessibility(
    *, gated: bool, private: bool, requires_authentication: bool, weight: float
) -> ScoreComponent:
    blockers = sum([gated, private, requires_authentication])
    raw = max(0.0, 1.0 - blockers * 0.3)
    reason = (
        "no access restrictions declared"
        if blockers == 0
        else f"{blockers} access restriction(s) declared (gated={gated}, private={private}, "
        f"requires_authentication={requires_authentication})"
    )
    return _component("accessibility", raw, weight, reason)


def score_risk_penalty(*, blocking_reason_count: int, weight: float) -> ScoreComponent:
    raw = 1.0 if blocking_reason_count > 0 else 0.0
    reason = (
        f"{blocking_reason_count} blocking reason(s) recorded"
        if blocking_reason_count
        else "none recorded"
    )
    return _component("risk_penalty", raw, weight, reason)


def score_unknown_licence_penalty(*, licence_status: str, weight: float) -> ScoreComponent:
    raw = 1.0 if licence_status in ("unknown", "missing") else 0.0
    return _component("unknown_licence_penalty", raw, weight, f"licence_status='{licence_status}'")


def score_gated_access_penalty(*, gated: bool, private: bool, weight: float) -> ScoreComponent:
    raw = 1.0 if (gated or private) else 0.0
    return _component(
        "gated_access_penalty", raw, weight, f"gated={gated}, private={private}"
    )


def score_conflict_penalty(*, is_possible_duplicate: bool, weight: float) -> ScoreComponent:
    raw = 1.0 if is_possible_duplicate else 0.0
    reason = (
        "flagged as a possible duplicate group" if is_possible_duplicate else "no conflict flagged"
    )
    return _component("conflict_penalty", raw, weight, reason)


def compute_suitability_score(
    components: list[ScoreComponent], *, weights: dict[str, float] | None = None
) -> dict:
    """Sums every component's already-weighted score, then normalizes
    against the maximum a candidate could reach on the positive
    dimensions alone (penalties can only pull the score down, never
    push it above what perfect positive dimensions would earn) -- fixed,
    reproducible, documented (Step 8: "the final suitability score must
    be reproducible")."""

    weights = weights or DEFAULT_SCORING_WEIGHTS
    present_dimensions = {c.dimension for c in components}
    if not present_dimensions <= set(ALL_SCORING_DIMENSIONS):
        unknown = present_dimensions - set(ALL_SCORING_DIMENSIONS)
        raise ValueError(f"unknown scoring dimension(s): {sorted(unknown)}")

    max_positive_total = sum(
        weight for dimension, weight in weights.items() if weight > 0
    )
    total = sum(c.score for c in components)
    overall = 0.0
    if max_positive_total > 0:
        overall = max(0.0, min(100.0, round(100 * total / max_positive_total)))
    return {
        "overall": overall,
        "components": [
            {
                "dimension": c.dimension,
                "raw_value": c.raw_value,
                "weight": c.weight,
                "score": c.score,
                "reason": c.reason,
            }
            for c in components
        ],
    }
