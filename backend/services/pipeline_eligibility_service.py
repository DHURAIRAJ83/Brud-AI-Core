"""Per-entity, per-target-pipeline eligibility evaluation (Phase 7,
Steps 3-5) -- the single place `GovernedBuildService` asks "is this
dataset_record eligible for this target_pipeline, and if not, why?".

Never re-implements Phase 6's rights/quality/duplicate/conflict gating:
every decision is `GovernanceApprovalService.evaluate()`'s own return
value, combined with build-specific signals (legacy classification,
prior duplicate export for this exact target, cross-build evaluation
isolation) via the pure `core_model.pipeline_integration.eligibility`
combinator.
"""

from __future__ import annotations

from typing import Any

from backend.core.config import Settings
from backend.database.repositories.governance import GovernanceRepository
from backend.database.repositories.governed_builds import GovernedBuildRepository
from backend.services.governance_service import GovernanceApprovalService
from core_model.pipeline_integration import PIPELINE_TARGET_USE_MAP
from core_model.pipeline_integration.eligibility import (
    decide_pipeline_eligibility,
    is_legacy_record,
)


class PipelineEligibilityService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.governance = GovernanceRepository(settings.resolved_database_path)
        self.governed_builds = GovernedBuildRepository(settings.resolved_database_path)
        self.approvals = GovernanceApprovalService(settings)

    def evaluate_entity(
        self,
        entity_type: str,
        entity_public_id: str,
        target_pipeline: str,
        *,
        admin_id: str,
        persist: bool,
        prior_evaluation_entity_ids: frozenset[str] = frozenset(),
        previously_exported_ids: frozenset[str] = frozenset(),
        legacy_override_reason: str | None = None,
    ) -> dict[str, Any]:
        target_use = PIPELINE_TARGET_USE_MAP[target_pipeline]

        with self.governance.transaction() as connection:
            review_item = self.governance.find_open_review_item(
                connection, entity_type, entity_public_id
            )
            approvals = self.governance.target_approvals_for_entity(
                connection, entity_type, entity_public_id
            )
        is_legacy = is_legacy_record(
            has_review_item=review_item is not None,
            has_any_target_approval=len(approvals) > 0,
        )

        excluded_by_evaluation_isolation = (
            target_pipeline in ("pretraining", "instruction_tuning", "tokenizer")
            and entity_public_id in prior_evaluation_entity_ids
        )
        already_exported_for_target = entity_public_id in previously_exported_ids

        # Never call (and never persist) a real Phase 6 governance
        # decision for a legacy-and-not-overridden entity: doing so
        # would silently "cure" its legacy status as a side effect of
        # this very preflight run, exactly the "silently include legacy
        # records" behavior Step 5 forbids. The entity gets a clean
        # LEGACY_UNCLASSIFIED result without ever touching
        # `governance_target_approvals`.
        if is_legacy and not legacy_override_reason:
            governance_decision: dict[str, Any] = {
                "decision": "not_requested",
                "decision_code": "NOT_REQUESTED",
                "warnings": [],
            }
        else:
            governance_decision = self.approvals.evaluate(
                entity_type, entity_public_id, target_use, admin_id=admin_id, persist=persist
            )

        result = decide_pipeline_eligibility(
            target_pipeline=target_pipeline,
            governance_decision=governance_decision,
            is_legacy=is_legacy,
            legacy_override_reason=legacy_override_reason,
            already_exported_for_target=already_exported_for_target,
            excluded_by_evaluation_isolation=excluded_by_evaluation_isolation,
        )
        return {**result, "target_use": target_use, "governance_decision": governance_decision}

    def prior_evaluation_entity_ids(self, *, entity_type: str = "dataset_record") -> frozenset[str]:
        with self.governed_builds.transaction() as connection:
            return self.governed_builds.prior_evaluation_entity_ids(
                connection, entity_type=entity_type
            )

    def previously_exported_entity_ids(
        self, *, target_pipeline: str, entity_type: str, entity_public_ids: list[str]
    ) -> frozenset[str]:
        with self.governed_builds.transaction() as connection:
            return frozenset(
                self.governed_builds.previously_included_entity_ids(
                    connection,
                    target_pipeline=target_pipeline,
                    entity_type=entity_type,
                    entity_public_ids=entity_public_ids,
                )
            )


__all__ = ["PipelineEligibilityService"]
