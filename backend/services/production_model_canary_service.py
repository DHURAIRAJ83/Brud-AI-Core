"""Phase 15 Step 14: canary activation.

Reuses the *existing, unmodified* `ModelAssignmentService.start_canary()`
/`execute_canary()`/`stop_canary()` -- this service only requires a
Phase-15 release approval to exist first and records the canary
outcome onto the governance row. See
docs/production/phase15_text_nlp_production_readiness_plan.md.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.core.config import Settings
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.base import ValidationError
from backend.database.repositories.inference_runtime import InferenceRuntimeRepository
from backend.database.repositories.model_release import ModelReleaseRepository
from backend.database.repositories.production_readiness import ProductionReadinessRepository
from backend.models.domain import AuditEventCreate, AuditOutcome
from backend.models.inference_runtime import CanaryStartRequest
from backend.services.inference_runtime_service import InferenceRuntimeService
from backend.services.model_assignment_service import ModelAssignmentService

logger = logging.getLogger(__name__)


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
                event_type=f"production_model_canary_{action}",
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
        logger.exception("production_model_canary_audit_write_failed", extra={"action": action})


class ProductionModelCanaryService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = ProductionReadinessRepository(settings.resolved_database_path)
        runtime_repository = InferenceRuntimeRepository(settings.resolved_database_path)
        release_repository = ModelReleaseRepository(settings.resolved_database_path)
        runtime_service = InferenceRuntimeService(runtime_repository, release_repository, settings)
        self._assignment = ModelAssignmentService(
            runtime_repository, release_repository, runtime_service, settings,
        )
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def _require_approved(self, release_request_public_id: str) -> dict[str, Any]:
        request = self.repository.get_model_release_request(release_request_public_id)
        if request["status"] != "approved":
            raise ValidationError(
                "only an approved release request may start a canary"
            )
        return request

    def start(
        self, release_request_public_id: str, assignment_public_id: str, *, admin_id: str,
        percentage: int = 0, max_request_count: int = 10,
    ) -> dict[str, Any]:
        self._require_approved(release_request_public_id)
        canary = self._assignment.start_canary(
            assignment_public_id,
            CanaryStartRequest(percentage=percentage, max_request_count=max_request_count),
            admin_id,
        )
        self.repository.update_model_release_request(
            release_request_public_id, {"status": "canary"}
        )
        self.repository.record_model_activation_event(
            release_request_public_id,
            {
                "event_type": "canary_started",
                "inference_model_assignment_public_id": assignment_public_id,
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit, action="start", actor_reference=admin_id,
            resource_public_id=release_request_public_id, outcome=AuditOutcome.SUCCESS,
        )
        return canary

    def execute(
        self, release_request_public_id: str, assignment_public_id: str,
        fixture_prompts: list[str], *, admin_id: str,
    ) -> dict[str, Any]:
        request = self.repository.get_model_release_request(release_request_public_id)
        if request["status"] != "canary":
            raise ValidationError("a canary must be started before it can be executed")
        result = self._assignment.execute_canary(
            assignment_public_id, fixture_prompts, admin_id,
        )
        passed = result.get("stop_assessment", {}).get("should_stop") is not True
        event_type = "canary_passed" if passed else "canary_failed"
        new_status = "canary" if passed else "canary_failed"
        self.repository.update_model_release_request(
            release_request_public_id, {"status": new_status}
        )
        self.repository.record_model_activation_event(
            release_request_public_id,
            {
                "event_type": event_type,
                "inference_model_assignment_public_id": assignment_public_id,
                "summary": dumps_summary(result),
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit, action="execute", actor_reference=admin_id,
            resource_public_id=release_request_public_id, outcome=AuditOutcome.SUCCESS,
            metadata={"passed": passed},
        )
        return result

    def stop(
        self, release_request_public_id: str, assignment_public_id: str, *, admin_id: str,
        reason: str = "admin_stop",
    ) -> dict[str, Any]:
        result = self._assignment.stop_canary(assignment_public_id, reason, admin_id)
        _audit(
            self._audit, action="stop", actor_reference=admin_id,
            resource_public_id=release_request_public_id, outcome=AuditOutcome.SUCCESS,
        )
        return result


def dumps_summary(result: dict[str, Any]) -> str:
    return str({k: result[k] for k in result if k in ("stop_assessment", "metrics")})


__all__ = ["ProductionModelCanaryService"]
