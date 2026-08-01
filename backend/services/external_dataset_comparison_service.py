"""Phase 10 Step 8 (comparison engine, service-layer integration):
builds and saves a side-by-side comparison of 2-5 candidates already
scored by `ExternalDatasetScoringService`. A comparison never changes
any candidate's own data -- it only reads already-persisted scores and
summary fields and records a snapshot via
`ExternalDatasetDiscoveryRepository.create_comparison`, so re-running a
comparison later after a rescore produces a new, independently
auditable snapshot rather than mutating history.
"""

from __future__ import annotations

from backend.core.exceptions import BrudError
from core_model.data_discovery import ALL_SCORING_DIMENSIONS

MIN_COMPARISON_CANDIDATES = 2
MAX_COMPARISON_CANDIDATES = 5


class ComparisonValidationError(BrudError):
    """Raised when the requested candidate set cannot be compared --
    e.g. too few/many candidates, or a candidate from another
    session."""

    status_code = 422
    code = "dataset_comparison_rejected"


class ExternalDatasetComparisonService:
    def __init__(self, discovery_repository) -> None:
        self._repository = discovery_repository

    def build_comparison_summary(
        self, session_public_id: str, candidate_public_ids: list[str]
    ) -> dict:
        unique_ids = list(dict.fromkeys(candidate_public_ids))
        if not (MIN_COMPARISON_CANDIDATES <= len(unique_ids) <= MAX_COMPARISON_CANDIDATES):
            raise ComparisonValidationError(
                f"a comparison needs {MIN_COMPARISON_CANDIDATES}-{MAX_COMPARISON_CANDIDATES} "
                f"distinct candidates, got {len(unique_ids)}"
            )

        candidates = {}
        warnings: list[str] = []
        for candidate_id in unique_ids:
            candidate = self._repository.get_candidate(candidate_id)
            if candidate["search_session_public_id"] != session_public_id:
                raise ComparisonValidationError(
                    f"candidate {candidate_id} does not belong to session {session_public_id}"
                )
            candidates[candidate_id] = candidate
            if candidate["suitability_score"] is None:
                warnings.append(f"candidate {candidate_id} has not been scored yet")

        dimensions: dict[str, dict] = {}
        for dimension in ALL_SCORING_DIMENSIONS:
            dimension_scores: dict[str, float] = {}
            for candidate_id in unique_ids:
                for component in self._repository.list_candidate_scores(candidate_id):
                    if component["dimension"] == dimension:
                        dimension_scores[candidate_id] = component["raw_value"]
                        break
            if not dimension_scores:
                continue
            is_penalty = dimension in ("risk_penalty", "unknown_licence_penalty",
                                        "gated_access_penalty", "conflict_penalty")
            best_candidate_id = (
                min(dimension_scores, key=lambda key: dimension_scores[key])
                if is_penalty
                else max(dimension_scores, key=lambda key: dimension_scores[key])
            )
            dimensions[dimension] = {
                "raw_values": dimension_scores,
                "best_candidate_public_id": best_candidate_id,
            }

        overall_scores = {
            candidate_id: candidates[candidate_id]["suitability_score"]
            for candidate_id in unique_ids
        }
        scored = {key: value for key, value in overall_scores.items() if value is not None}
        best_overall_candidate_public_id = (
            max(scored, key=lambda key: scored[key]) if scored else None
        )

        return {
            "candidate_public_ids": unique_ids,
            "overall_scores": overall_scores,
            "best_overall_candidate_public_id": best_overall_candidate_public_id,
            "dimensions": dimensions,
            "warnings": warnings,
        }

    def create_comparison(
        self,
        session_public_id: str,
        candidate_public_ids: list[str],
        *,
        created_by_admin_public_id: str,
    ) -> dict:
        summary = self.build_comparison_summary(session_public_id, candidate_public_ids)
        return self._repository.create_comparison(
            session_public_id,
            {
                "candidate_ids": summary["candidate_public_ids"],
                "summary": summary,
                "created_by_admin_public_id": created_by_admin_public_id,
            },
        )
