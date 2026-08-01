"""Phase 10 Step 8 (service-layer integration): wires the pure,
independently-tested `core_model.data_discovery.scoring` dimension
functions to the persisted candidate/requirement row shapes, derives
the honest warnings/blocking-reasons list a candidate's metadata
justifies, then persists the result via
`ExternalDatasetDiscoveryRepository.set_candidate_scores` and the
candidate's own summary columns.

The scoring *math* never lives here -- every dimension's formula stays
in `core_model/data_discovery/scoring.py`, unchanged and reproducible.
This module only supplies the mapping from a repository-shaped
candidate/requirement dict to that pure module's keyword arguments, so
scoring stays reproducible (same candidate + same requirement always
produce the same score) without this service inventing its own
scoring rules.
"""

from __future__ import annotations

from backend.core.json_utils import dumps_json
from backend.database.repositories.external_dataset_discovery import (
    ExternalDatasetDiscoveryRepository,
)
from core_model.data_discovery import DEFAULT_SCORING_WEIGHTS
from core_model.data_discovery.scoring import (
    compute_suitability_score,
    score_accessibility,
    score_conflict_penalty,
    score_dataset_card_presence,
    score_format_suitability,
    score_gated_access_penalty,
    score_intended_use_fit,
    score_language_fit,
    score_metadata_completeness,
    score_modality_fit,
    score_provider_trust,
    score_recency,
    score_requirement_fit,
    score_risk_penalty,
    score_size_suitability,
    score_task_fit,
    score_unknown_licence_penalty,
    score_version_traceability,
)

# The candidate metadata fields consulted for `metadata_completeness`
# -- a fixed, documented list rather than "every column", so the
# dimension stays stable as unrelated columns are added later.
_COMPLETENESS_FIELDS = (
    "description",
    "organization",
    "declared_licence",
    "record_count",
    "last_modified_at",
    "version",
)


def _metadata_completeness_counts(candidate: dict) -> tuple[int, int]:
    present = sum(1 for field in _COMPLETENESS_FIELDS if candidate.get(field))
    if candidate.get("file_formats"):
        present += 1
    if candidate.get("dataset_card_url") or candidate.get("homepage_url") or candidate.get(
        "repository_url"
    ):
        present += 1
    return present, len(_COMPLETENESS_FIELDS) + 2


def _requirement_fit_counts(candidate: dict, requirement: dict) -> tuple[int, int]:
    checks = [
        candidate.get("modality") is not None
        and candidate["modality"] == requirement.get("modality"),
        (not requirement.get("languages")) or bool(
            set(requirement.get("languages", [])) & set(candidate.get("languages", []))
        ),
        (not requirement.get("tasks")) or bool(
            set(requirement.get("tasks", [])) & set(candidate.get("tasks", []))
        ),
        requirement.get("commercial_requirement") in ("not_required", "unknown"),
    ]
    return sum(1 for check in checks if check), len(checks)


def derive_warnings_and_blocking_reasons(
    candidate: dict, requirement: dict
) -> tuple[list[str], list[str]]:
    """Deterministic, documented rules -- never a judgement call about
    licence *validity* (that stays `unknown`/deferred to Phase 11),
    only about what a candidate's own recorded metadata already makes
    plain: a missing card, an unresolved licence, or a commercial
    requirement Phase 10 has no way to verify."""

    warnings: list[str] = []
    if not candidate.get("dataset_card_present"):
        warnings.append("dataset_card_missing")
    if candidate.get("licence_status") == "unknown":
        warnings.append("licence_unknown")
    if not candidate.get("last_modified_at"):
        warnings.append("last_modified_unknown")

    blocking_reasons: list[str] = []
    if requirement.get("commercial_requirement") == "required":
        blocking_reasons.append("commercial_use_required_but_not_verifiable_in_this_phase")
    if candidate.get("licence_status") == "conflicting":
        blocking_reasons.append("licence_information_conflicts_across_sources")
    return warnings, blocking_reasons


def _recommendation_status(
    *, overall: float, metadata_completeness_raw: float, blocking_reason_count: int
) -> str:
    if metadata_completeness_raw < 0.34:
        return "insufficient_metadata"
    if blocking_reason_count > 0:
        return "high_risk"
    if overall >= 70:
        return "recommended_for_review"
    if overall >= 40:
        return "possible"
    return "low_fit"


def _risk_score(components: list) -> float:
    penalty_weights = sum(abs(c.weight) for c in components if c.weight < 0)
    penalty_scores = sum(-c.score for c in components if c.weight < 0)
    if penalty_weights <= 0:
        return 0.0
    return max(0.0, min(100.0, round(100 * penalty_scores / penalty_weights)))


def _quality_signal_score(components: list) -> float:
    quality_dimensions = {"metadata_completeness", "dataset_card_presence", "version_traceability"}
    quality_components = [c for c in components if c.dimension in quality_dimensions]
    if not quality_components:
        return 0.0
    return round(100 * sum(c.raw_value for c in quality_components) / len(quality_components))


def compute_candidate_score(
    candidate: dict,
    requirement: dict,
    *,
    provider_trust_status: str,
    weights: dict[str, float] | None = None,
) -> dict:
    weights = weights or DEFAULT_SCORING_WEIGHTS
    warnings, blocking_reasons = derive_warnings_and_blocking_reasons(candidate, requirement)
    matched_fields, total_fields = _requirement_fit_counts(candidate, requirement)
    present_fields, total_metadata_fields = _metadata_completeness_counts(candidate)
    metadata_completeness_raw = (
        present_fields / total_metadata_fields if total_metadata_fields else 0.0
    )
    intended_use_fit = candidate.get("intended_use_fit") or {}
    candidate_use_signals = tuple(key for key, value in intended_use_fit.items() if value)

    components = [
        score_requirement_fit(
            matched_fields=matched_fields, total_fields=total_fields,
            weight=weights["requirement_fit"],
        ),
        score_language_fit(
            requirement_languages=tuple(requirement.get("languages", [])),
            candidate_languages=tuple(candidate.get("languages", [])),
            weight=weights["language_fit"],
        ),
        score_task_fit(
            requirement_tasks=tuple(requirement.get("tasks", [])),
            candidate_tasks=tuple(candidate.get("tasks", [])),
            weight=weights["task_fit"],
        ),
        score_modality_fit(
            requirement_modality=requirement.get("modality", "text"),
            candidate_modality=candidate.get("modality"),
            weight=weights["modality_fit"],
        ),
        score_intended_use_fit(
            requirement_uses=tuple(requirement.get("intended_uses", [])),
            candidate_use_signals=candidate_use_signals,
            weight=weights["intended_use_fit"],
        ),
        score_metadata_completeness(
            present_field_count=present_fields, total_field_count=total_metadata_fields,
            weight=weights["metadata_completeness"],
        ),
        score_provider_trust(trust_status=provider_trust_status, weight=weights["provider_trust"]),
        score_dataset_card_presence(
            present=bool(candidate.get("dataset_card_present")),
            weight=weights["dataset_card_presence"],
        ),
        score_version_traceability(
            has_version=bool(candidate.get("version")),
            has_revision=bool(candidate.get("revision")),
            weight=weights["version_traceability"],
        ),
        score_size_suitability(
            download_size_bytes=candidate.get("download_size_bytes"),
            maximum_download_size_bytes=requirement.get("maximum_download_size_bytes"),
            weight=weights["size_suitability"],
        ),
        score_format_suitability(
            candidate_formats=tuple(candidate.get("file_formats", [])),
            preferred_formats=tuple(requirement.get("preferred_file_formats", [])),
            weight=weights["format_suitability"],
        ),
        score_recency(
            last_modified_at=candidate.get("last_modified_at"), weight=weights["recency"]
        ),
        score_accessibility(
            gated=bool(candidate.get("gated")), private=bool(candidate.get("private")),
            requires_authentication=bool(candidate.get("authentication_required")),
            weight=weights["accessibility"],
        ),
        score_risk_penalty(
            blocking_reason_count=len(blocking_reasons), weight=weights["risk_penalty"]
        ),
        score_unknown_licence_penalty(
            licence_status=candidate.get("licence_status", "unknown"),
            weight=weights["unknown_licence_penalty"],
        ),
        score_gated_access_penalty(
            gated=bool(candidate.get("gated")), private=bool(candidate.get("private")),
            weight=weights["gated_access_penalty"],
        ),
        score_conflict_penalty(
            is_possible_duplicate=bool(candidate.get("possible_duplicate_of_candidate_public_id")),
            weight=weights["conflict_penalty"],
        ),
    ]
    result = compute_suitability_score(components, weights=weights)
    overall = result["overall"]
    return {
        "components": result["components"],
        "overall": overall,
        "risk_score": _risk_score(components),
        "quality_signal_score": _quality_signal_score(components),
        "metadata_completeness_score": round(metadata_completeness_raw * 100),
        "recommendation_status": _recommendation_status(
            overall=overall,
            metadata_completeness_raw=metadata_completeness_raw,
            blocking_reason_count=len(blocking_reasons),
        ),
        "warnings": warnings,
        "blocking_reasons": blocking_reasons,
    }


class ExternalDatasetScoringService:
    def __init__(self, discovery_repository: ExternalDatasetDiscoveryRepository) -> None:
        self._repository = discovery_repository

    def rescore_candidate(
        self, candidate_public_id: str, requirement: dict, *, provider_trust_status: str
    ) -> dict:
        candidate = self._repository.get_candidate(candidate_public_id)
        result = compute_candidate_score(
            candidate, requirement, provider_trust_status=provider_trust_status
        )
        self._repository.set_candidate_scores(candidate_public_id, result["components"])
        return self._repository.update_candidate(
            candidate_public_id,
            {
                "suitability_score": result["overall"],
                "risk_score": result["risk_score"],
                "quality_signal_score": result["quality_signal_score"],
                "metadata_completeness_score": result["metadata_completeness_score"],
                "recommendation_status": result["recommendation_status"],
                "warnings_json": dumps_json(result["warnings"]),
                "blocking_reasons_json": dumps_json(result["blocking_reasons"]),
            },
        )
