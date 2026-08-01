"""Phase 15 Step 12: model release validation.

Reuses the *existing, unmodified* `ModelReleaseService` end to end
(`collect_artifacts` -> `verify_artifacts` -> `generate_model_card` ->
`validate_model_card` -> `assess_eligibility` -> `generate_manifest` ->
`verify_manifest`) --
this service never re-implements checkpoint/tokenizer/config
verification or the eligibility cascade. It only reads the resulting
`latest_eligibility_status` back and reflects it onto the Phase-15
governance row. See
docs/production/phase15_text_nlp_production_readiness_plan.md.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.core.config import Settings
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.base import ValidationError
from backend.database.repositories.model_release import ModelReleaseRepository
from backend.database.repositories.production_readiness import ProductionReadinessRepository
from backend.models.domain import AuditEventCreate, AuditOutcome
from backend.models.model_release import ModelCardOverrides
from backend.services.model_release_service import ModelReleaseService

logger = logging.getLogger(__name__)

_ELIGIBLE_STATUSES = ("eligible", "eligible_with_warnings")


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
                event_type=f"production_model_release_validation_{action}",
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
            "production_model_release_validation_audit_write_failed", extra={"action": action}
        )


class ProductionModelReleaseValidationService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = ProductionReadinessRepository(settings.resolved_database_path)
        self._release = ModelReleaseService(
            ModelReleaseRepository(settings.resolved_database_path), settings
        )
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def run_validation(self, release_request_public_id: str, *, admin_id: str) -> dict[str, Any]:
        request = self.repository.get_model_release_request(release_request_public_id)
        candidate_public_id = request["model_release_candidate_public_id"]
        if not candidate_public_id:
            raise ValidationError(
                "this request has no linked model release candidate -- create one via "
                "the existing model registry first"
            )
        self.repository.update_model_release_request(
            release_request_public_id, {"status": "validating"}
        )
        self._release.collect_artifacts(candidate_public_id, admin_id)
        self._release.verify_artifacts(candidate_public_id, admin_id)
        self._release.generate_model_card(candidate_public_id, ModelCardOverrides(), admin_id)
        self._release.validate_model_card(candidate_public_id, admin_id)
        eligibility = self._release.assess_eligibility(candidate_public_id, admin_id)
        manifest = self._release.generate_manifest(candidate_public_id, admin_id)
        manifest_check = self._release.verify_manifest(candidate_public_id)

        eligible = eligibility.get("status") in _ELIGIBLE_STATUSES
        final_status = "validated" if eligible and manifest_check.get("matches") else (
            "validation_failed"
        )
        updated = self.repository.update_model_release_request(
            release_request_public_id, {"status": final_status}
        )
        _audit(
            self._audit, action="run_validation", actor_reference=admin_id,
            resource_public_id=release_request_public_id, outcome=AuditOutcome.SUCCESS,
            metadata={"final_status": final_status, "manifest_public_id": manifest["public_id"]},
        )
        return {
            "request": updated, "eligibility": eligibility, "manifest": manifest,
            "manifest_verified": manifest_check.get("matches"),
        }


__all__ = ["ProductionModelReleaseValidationService"]
