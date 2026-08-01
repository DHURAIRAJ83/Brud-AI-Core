"""Phase 15 Steps 15-16: full model activation sequence with mandatory
pre-verified rollback readiness and automatic rollback on a failed
post-activation health check.

Reuses the *existing, unmodified* `ModelAssignmentService` end to end
(`activate_assignment`, `ensure_instance_loaded`, `rollback_execute`)
plus `InferenceRuntimeService.run_health_check` for the real
post-activation signal -- this service never loads a model or touches
`inference_model_assignments` directly. It requires an already
created/approved `inference_model_assignments` row (built by an admin
through the existing assignment workflow) and an already-`verified`
`production_rollback_plans` row (Step 16) before it will activate
anything, mirroring the "reuse an existing prerequisite, never
recreate it" pattern used by the RAG activation track. See
docs/production/phase15_text_nlp_production_readiness_plan.md.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from typing import Any

from backend.core.config import Settings
from backend.core.json_utils import dumps_json
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.base import ValidationError
from backend.database.repositories.inference_runtime import InferenceRuntimeRepository
from backend.database.repositories.model_release import ModelReleaseRepository
from backend.database.repositories.production_readiness import ProductionReadinessRepository
from backend.models.domain import AuditEventCreate, AuditOutcome
from backend.models.inference_runtime import RollbackPreviewRequest
from backend.services.inference_runtime_service import InferenceRuntimeService
from backend.services.model_assignment_service import ModelAssignmentService

logger = logging.getLogger(__name__)

_ACTIVATABLE_STATUSES = ("approved", "canary")
_HEALTHY_STATUSES = ("healthy",)
_HEALTH_TO_RESULT_STATUS = {
    "healthy": "passed",
    "degraded": "passed_with_warning",
    "unhealthy": "failed",
}


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
                event_type=f"production_model_activation_{action}",
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
        logger.exception("production_model_activation_audit_write_failed", extra={"action": action})


class ProductionModelActivationService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = ProductionReadinessRepository(settings.resolved_database_path)
        runtime_repository = InferenceRuntimeRepository(settings.resolved_database_path)
        release_repository = ModelReleaseRepository(settings.resolved_database_path)
        self._runtime = InferenceRuntimeService(runtime_repository, release_repository, settings)
        self._assignment = ModelAssignmentService(
            runtime_repository, release_repository, self._runtime, settings,
        )
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def activate(
        self,
        release_request_public_id: str,
        assignment_public_id: str,
        rollback_plan_public_id: str,
        *,
        admin_id: str,
        explicit_activation_confirmed: bool = False,
    ) -> dict[str, Any]:
        request = self.repository.get_model_release_request(release_request_public_id)
        if request["status"] not in _ACTIVATABLE_STATUSES:
            raise ValidationError(
                "release request must be approved (and, if canary was requested, must not "
                "have failed its canary) before activation"
            )
        plan = self.repository.get_rollback_plan(rollback_plan_public_id)
        if plan["target_type"] != "model":
            raise ValidationError("rollback plan target_type must be 'model'")
        if plan["status"] != "verified":
            raise ValidationError(
                "rollback readiness must be verified before activation -- validate the "
                "rollback plan first"
            )

        approval = self.repository.get_latest_model_release_approval(release_request_public_id)
        if approval is None or approval["status"] != "approved":
            raise ValidationError("no approved production model release approval exists")
        if approval["expires_at"] and approval["expires_at"] < datetime.now(UTC).isoformat():
            self.repository.mark_model_release_approval_expired(approval["public_id"])
            raise ValidationError(
                "this production model release approval has expired -- request a fresh one"
            )
        current_fingerprint = hashlib.sha256(
            dumps_json(
                {
                    "model_candidate": request["model_candidate_public_id"],
                    "release_candidate": request["model_release_candidate_public_id"],
                    "target_assignment_keys": sorted(request["target_assignment_keys"]),
                }
            ).encode("utf-8")
        ).hexdigest()
        if approval["target_fingerprint"] != current_fingerprint:
            raise ValidationError(
                "the release request changed since this approval was granted -- stale approval"
            )

        self.repository.update_model_release_request(
            release_request_public_id, {"status": "activating"}
        )
        self.repository.record_model_activation_event(
            release_request_public_id,
            {"event_type": "pre_activation_snapshot", "performed_by_admin_public_id": admin_id},
        )

        activation = self._assignment.activate_assignment(
            assignment_public_id, admin_id,
            explicit_activation_confirmed=explicit_activation_confirmed,
        )
        if not activation["activated"]:
            self.repository.update_model_release_request(
                release_request_public_id, {"status": "activation_failed"}
            )
            self.repository.record_model_activation_event(
                release_request_public_id,
                {
                    "event_type": "activation_failed",
                    "inference_model_assignment_public_id": assignment_public_id,
                    "summary": "activation gate rejected",
                    "metadata": {"reasons": activation["rejection_reasons"]},
                    "performed_by_admin_public_id": admin_id,
                },
            )
            _audit(
                self._audit, action="activate", actor_reference=admin_id,
                resource_public_id=release_request_public_id, outcome=AuditOutcome.FAILURE,
                metadata={"reasons": activation["rejection_reasons"]},
            )
            raise ValidationError(
                "activation gate rejected: " + "; ".join(activation["rejection_reasons"])
            )

        instance = self._assignment.ensure_instance_loaded(assignment_public_id, admin_id)
        health = self._runtime.run_health_check(instance["public_id"], admin_id)
        self.repository.add_model_post_activation_check(
            release_request_public_id,
            {
                "check_type": "post_activation_health",
                "result_status": _HEALTH_TO_RESULT_STATUS.get(health["overall_status"], "failed"),
                "metrics": health["checks"],
                "created_by_admin_public_id": admin_id,
            },
        )

        if health["overall_status"] in _HEALTHY_STATUSES:
            self.repository.update_model_release_request(
                release_request_public_id, {"status": "activated"}
            )
            self.repository.record_model_activation_event(
                release_request_public_id,
                {
                    "event_type": "activated",
                    "inference_model_assignment_public_id": assignment_public_id,
                    "metadata": {"health": health["overall_status"]},
                    "performed_by_admin_public_id": admin_id,
                },
            )
            _audit(
                self._audit, action="activate", actor_reference=admin_id,
                resource_public_id=release_request_public_id, outcome=AuditOutcome.SUCCESS,
            )
            return {"activated": True, "health": health, "rolled_back": False}

        rolled_back = False
        if plan["current_active_version"]:
            self._assignment.rollback_execute(
                assignment_public_id,
                RollbackPreviewRequest(
                    target_version_public_id=plan["current_active_version"],
                    reason="automatic rollback after failed post-activation health check",
                ),
                admin_id,
            )
            self.repository.update_rollback_plan_status(rollback_plan_public_id, "used")
            self.repository.record_rollback_event(
                rollback_plan_public_id,
                {
                    "event_type": "executed",
                    "performed_by_admin_public_id": admin_id,
                },
            )
            rolled_back = True

        self.repository.update_model_release_request(
            release_request_public_id, {"status": "activation_failed"}
        )
        self.repository.record_model_activation_event(
            release_request_public_id,
            {
                "event_type": "activation_failed",
                "inference_model_assignment_public_id": assignment_public_id,
                "summary": "post-activation health check failed",
                "metadata": {"health": health["overall_status"], "rolled_back": rolled_back},
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit, action="activate", actor_reference=admin_id,
            resource_public_id=release_request_public_id, outcome=AuditOutcome.FAILURE,
            metadata={"health": health["overall_status"], "rolled_back": rolled_back},
        )
        rollback_note = (
            "rolled back to the previous version"
            if rolled_back
            else "no previous version was available to roll back to"
        )
        raise ValidationError(
            f"post-activation health check failed (status={health['overall_status']}); "
            f"{rollback_note}"
        )

    def rollback(
        self,
        release_request_public_id: str,
        assignment_public_id: str,
        rollback_plan_public_id: str,
        *,
        admin_id: str,
        reason: str = "admin-initiated rollback",
    ) -> dict[str, Any]:
        request = self.repository.get_model_release_request(release_request_public_id)
        if request["status"] != "activated":
            raise ValidationError("only an activated release request may be rolled back")
        plan = self.repository.get_rollback_plan(rollback_plan_public_id)
        if not plan["current_active_version"]:
            raise ValidationError("this rollback plan has no target version to roll back to")

        result = self._assignment.rollback_execute(
            assignment_public_id,
            RollbackPreviewRequest(
                target_version_public_id=plan["current_active_version"], reason=reason,
            ),
            admin_id,
        )
        self.repository.update_rollback_plan_status(rollback_plan_public_id, "used")
        self.repository.record_rollback_event(
            rollback_plan_public_id,
            {"event_type": "executed", "performed_by_admin_public_id": admin_id},
        )
        self.repository.update_model_release_request(
            release_request_public_id, {"status": "superseded"}
        )
        self.repository.record_model_activation_event(
            release_request_public_id,
            {
                "event_type": "rolled_back",
                "inference_model_assignment_public_id": assignment_public_id,
                "summary": reason,
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit, action="rollback", actor_reference=admin_id,
            resource_public_id=release_request_public_id, outcome=AuditOutcome.SUCCESS,
        )
        return result


__all__ = ["ProductionModelActivationService"]
