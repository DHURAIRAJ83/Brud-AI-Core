"""Phase 15 Step 16: rollback plans, shared by the RAG and model
tracks. A plan must exist and be `verified` before the corresponding
activation service will proceed -- rollback readiness is checked
*before* activation, never assembled after the fact. See
docs/production/phase15_text_nlp_production_readiness_plan.md.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.core.config import Settings
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.base import ValidationError
from backend.database.repositories.production_readiness import ProductionReadinessRepository
from backend.models.domain import AuditEventCreate, AuditOutcome
from core_model.production_readiness import ROLLBACK_TARGET_TYPES

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
                event_type=f"production_rollback_plan_{action}",
                actor_type="admin",
                actor_reference=actor_reference,
                action=action,
                resource_type="production_rollback_plan",
                resource_public_id=resource_public_id,
                outcome=outcome,
                metadata=metadata or {},
            )
        )
    except Exception:
        logger.exception("production_rollback_plan_audit_write_failed", extra={"action": action})


class ProductionRollbackPlanService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = ProductionReadinessRepository(settings.resolved_database_path)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def create_plan(self, values: dict[str, Any], *, admin_id: str) -> dict[str, Any]:
        if values["target_type"] not in ROLLBACK_TARGET_TYPES:
            raise ValidationError(f"unknown target_type: {values['target_type']!r}")
        plan = self.repository.create_rollback_plan(
            {**values, "created_by_admin_public_id": admin_id}
        )
        _audit(
            self._audit, action="create", actor_reference=admin_id,
            resource_public_id=plan["public_id"], outcome=AuditOutcome.SUCCESS,
        )
        return plan

    def validate_plan(self, rollback_plan_public_id: str, *, admin_id: str) -> dict[str, Any]:
        plan = self.repository.get_rollback_plan(rollback_plan_public_id)
        if plan["status"] != "draft":
            raise ValidationError("only a draft rollback plan may be validated")
        if not plan["rollback_steps"]:
            raise ValidationError("a rollback plan requires at least one rollback step")
        updated = self.repository.update_rollback_plan_status(rollback_plan_public_id, "verified")
        self.repository.record_rollback_event(
            rollback_plan_public_id,
            {"event_type": "validated", "performed_by_admin_public_id": admin_id},
        )
        _audit(
            self._audit, action="validate", actor_reference=admin_id,
            resource_public_id=rollback_plan_public_id, outcome=AuditOutcome.SUCCESS,
        )
        return updated

    def get_plan(self, rollback_plan_public_id: str) -> dict[str, Any]:
        return self.repository.get_rollback_plan(rollback_plan_public_id)

    def list_plans(self, *, target_type: str | None = None) -> list[dict[str, Any]]:
        return self.repository.list_rollback_plans(target_type=target_type)


__all__ = ["ProductionRollbackPlanService"]
