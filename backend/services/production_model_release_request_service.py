"""Phase 15 Steps 9-11: accepted-checkpoint eligibility, model release
request, and release package -- a thin governance wrapper around the
*existing, unmodified* `ModelReleaseService`.

`ModelReleaseService` (this repository's own prior work) already
implements the entire candidate/artifact/manifest/model-card pipeline;
this service's only job is (a) re-verifying the Phase 14 acceptance
chain before a release candidate can even be created, and (b)
recording a separate, Phase-15-scoped `production_model_release_requests`
row that binds to whatever `ModelReleaseService` produces. It never
creates a `model_release_family` (an Admin does that once, directly,
through the existing registry) and never calls anything that could
activate a model. See
docs/production/phase15_text_nlp_production_readiness_plan.md.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.base import ValidationError
from backend.database.repositories.model_release import ModelReleaseRepository
from backend.database.repositories.production_readiness import ProductionReadinessRepository
from backend.database.repositories.training_incremental import TrainingIncrementalRepository
from backend.models.domain import AuditEventCreate, AuditOutcome
from backend.models.model_release import ModelReleaseCandidateCreate
from backend.services.model_release_service import ModelReleaseService
from core_model.training_incremental import BLOCKING_REGRESSION_RESULTS

logger = logging.getLogger(__name__)

_ACCEPTED_DECISIONS = ("accepted_candidate", "accepted_with_conditions")


def _audit(
    audit_repository: AuditLogRepository | None,
    *,
    action: str,
    actor_reference: str,
    resource_public_id: str,
    outcome: AuditOutcome,
    metadata: dict[str, Any] | None = None,
) -> None:
    if audit_repository is None:
        return
    try:
        audit_repository.append(
            AuditEventCreate(
                event_type=f"production_model_release_request_{action}",
                actor_type="admin",
                actor_reference=actor_reference,
                action=action,
                resource_type="production_model_release_request",
                resource_public_id=resource_public_id,
                outcome=outcome,
                metadata=metadata or {},
            )
        )
    except Exception:
        logger.exception(
            "production_model_release_request_audit_write_failed", extra={"action": action}
        )


class ProductionModelReleaseEligibilityService:
    """Step 9: read-only re-verification of the Phase 14 acceptance
    chain. Checkpoint acceptance alone must not create a release --
    this only checks whether a release request is *allowed to be
    created*, it never creates anything."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._training = TrainingIncrementalRepository(settings.resolved_database_path)

    def check_eligibility(self, incremental_training_checkpoint_public_id: str) -> dict[str, Any]:
        blocking: list[str] = []
        warnings: list[str] = []

        checkpoint = self._training.get_checkpoint(incremental_training_checkpoint_public_id)
        acceptance = self._training.get_latest_acceptance(incremental_training_checkpoint_public_id)
        if acceptance is None or acceptance["decision"] not in _ACCEPTED_DECISIONS:
            blocking.append(
                "checkpoint has no accepted_candidate/accepted_with_conditions acceptance"
            )
        elif acceptance["decision"] == "accepted_with_conditions":
            warnings.append("checkpoint was accepted with conditions")
        if not acceptance or not acceptance.get("model_candidate_public_id"):
            blocking.append("no model candidate was registered for this checkpoint")

        comparisons = self._training.list_comparisons(incremental_training_checkpoint_public_id)
        if any(c["result_status"] in BLOCKING_REGRESSION_RESULTS for c in comparisons):
            blocking.append("checkpoint has a major_regression comparison result")

        if checkpoint["status"] not in ("accepted_candidate",):
            blocking.append(
                f"checkpoint status is '{checkpoint['status']}', not accepted_candidate"
            )

        return {
            "eligible": not blocking,
            "blocking_reasons": blocking,
            "warnings": warnings,
            "model_candidate_public_id": acceptance.get("model_candidate_public_id")
            if acceptance else None,
        }


class ProductionModelReleaseRequestService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = ProductionReadinessRepository(settings.resolved_database_path)
        self._eligibility = ProductionModelReleaseEligibilityService(settings)
        self._release = ModelReleaseService(
            ModelReleaseRepository(settings.resolved_database_path), settings
        )
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def create_request(self, values: dict[str, Any], *, admin_id: str) -> dict[str, Any]:
        checkpoint_public_id = values["incremental_training_checkpoint_public_id"]
        eligibility = self._eligibility.check_eligibility(checkpoint_public_id)
        if not eligibility["eligible"]:
            raise ValidationError(
                "model release eligibility failed: " + "; ".join(eligibility["blocking_reasons"])
            )

        release_candidate_public_id = None
        if values.get("model_release_family_public_id"):
            candidate = self._release.create_candidate(
                ModelReleaseCandidateCreate(
                    model_release_family_public_id=values["model_release_family_public_id"],
                    core_model_version_public_id=eligibility["model_candidate_public_id"],
                    dataset_version_public_id=values.get("dataset_version_public_id"),
                    model_evaluation_run_public_id=values.get("model_evaluation_run_public_id"),
                    label=values.get("label"),
                    notes=values.get("notes", ""),
                ),
                admin_id,
            )
            release_candidate_public_id = candidate["public_id"]

        request = self.repository.create_model_release_request(
            {
                "request_code": f"PMR-{uuid4().hex[:16]}",
                "model_candidate_public_id": eligibility["model_candidate_public_id"],
                "incremental_training_checkpoint_public_id": checkpoint_public_id,
                "release_type": values.get("release_type", "experimental"),
                "target_assignment_keys": values.get("target_assignment_keys", []),
                "canary_requested": values.get("canary_requested", True),
                "canary_percentage_or_scope": values.get(
                    "canary_percentage_or_scope", "admin_diagnostic"
                ),
                "requested_by_admin_public_id": admin_id,
            }
        )
        if release_candidate_public_id:
            with self.repository.transaction() as connection:
                candidate_id = connection.execute(
                    "SELECT id FROM model_release_candidates WHERE public_id=?",
                    (release_candidate_public_id,),
                ).fetchone()[0]
                connection.execute(
                    "UPDATE production_model_release_requests SET model_release_candidate_id=? "
                    "WHERE public_id=?",
                    (candidate_id, request["public_id"]),
                )
        _audit(
            self._audit, action="create_request", actor_reference=admin_id,
            resource_public_id=request["public_id"], outcome=AuditOutcome.SUCCESS,
            metadata={"warnings": eligibility["warnings"]},
        )
        return self.repository.get_model_release_request(request["public_id"])

    def submit_for_review(self, release_request_public_id: str, *, admin_id: str) -> dict[str, Any]:
        current = self.repository.get_model_release_request(release_request_public_id)
        if current["status"] != "draft":
            raise ValidationError("only a draft release request can be submitted for review")
        updated = self.repository.update_model_release_request(
            release_request_public_id, {"status": "awaiting_review"}
        )
        _audit(
            self._audit, action="submit_for_review", actor_reference=admin_id,
            resource_public_id=release_request_public_id, outcome=AuditOutcome.SUCCESS,
        )
        return updated


__all__ = [
    "ProductionModelReleaseEligibilityService",
    "ProductionModelReleaseRequestService",
]
