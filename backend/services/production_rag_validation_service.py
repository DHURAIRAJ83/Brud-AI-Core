"""Phase 15 Step 6: production RAG candidate structural validation.

`RagRetrievalService.retrieve()` hard-requires an `active` profile (a
real safety property -- it refuses to serve queries against an
unvalidated profile), so live retrieval smoke tests cannot run before
activation. This service checks structural/content readiness instead
(profile validated, checksums present); the real retrieval-based
smoke tests are the Step 8 *post*-activation check, run by
`ProductionRagActivationService.activate()`, which rolls back
immediately on failure. See
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
                event_type=f"production_rag_validation_{action}",
                actor_type="admin",
                actor_reference=actor_reference,
                action=action,
                resource_type="production_rag_release_candidate",
                resource_public_id=resource_public_id,
                outcome=outcome,
                metadata=metadata or {},
            )
        )
    except Exception:
        logger.exception("production_rag_validation_audit_write_failed", extra={"action": action})


class ProductionRagValidationService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = ProductionReadinessRepository(settings.resolved_database_path)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def run_validation(
        self, rag_release_candidate_public_id: str, *, admin_id: str
    ) -> dict[str, Any]:
        candidate = self.repository.get_rag_release_candidate(rag_release_candidate_public_id)
        if candidate["status"] != "built":
            raise ValidationError("only a built candidate may be validated")
        if not candidate["retrieval_profile_public_id"]:
            raise ValidationError("candidate has no retrieval profile to validate against")

        self.repository.update_rag_release_candidate(
            rag_release_candidate_public_id, {"status": "validating"}
        )

        with self.repository.transaction() as connection:
            profile_row = connection.execute(
                "SELECT status FROM rag_retrieval_profiles WHERE public_id=?",
                (candidate["retrieval_profile_public_id"],),
            ).fetchone()
        checks = {
            "retrieval_profile_ready": (
                "passed" if profile_row and profile_row["status"] == "validated" else "failed"
            ),
            "chunk_checksum_present": (
                "passed" if candidate["chunk_checksum_set_hash"] else "failed"
            ),
            "index_checksum_present": (
                "passed" if candidate["index_checksum_sha256"] else "failed"
            ),
            "embedding_model_recorded": (
                "passed" if candidate["embedding_model_reference"] else "failed"
            ),
            "record_checksum_set_recorded": (
                "passed" if candidate["record_checksum_set_hash"] else "failed"
            ),
        }
        results = [
            self.repository.add_rag_validation_result(
                rag_release_candidate_public_id,
                {
                    "validation_type": validation_type, "result_status": result_status,
                    "metrics": {}, "details": {}, "created_by_admin_public_id": admin_id,
                },
            )
            for validation_type, result_status in checks.items()
        ]

        any_failed = any(item["result_status"] == "failed" for item in results)
        final_status = "validation_failed" if any_failed else "validated"
        updated = self.repository.update_rag_release_candidate(
            rag_release_candidate_public_id, {"status": final_status}
        )
        _audit(
            self._audit, action="run_validation", actor_reference=admin_id,
            resource_public_id=rag_release_candidate_public_id, outcome=AuditOutcome.SUCCESS,
            metadata={"final_status": final_status, "result_count": len(results)},
        )
        return {"candidate": updated, "results": results}


__all__ = ["ProductionRagValidationService"]
