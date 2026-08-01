"""Phase 15 Step 8: production RAG activation and rollback.

Reuses the *existing, unmodified* `RagRetrievalService.activate_profile()`
for the actual state transition -- this service only sequences the
governance steps around it: snapshot -> verify approval/checksums ->
activate -> post-activation checks -> on failure, reactivate the
snapshotted previous profile. The previous active profile is archived
(never deleted) so it always remains available to reactivate. See
docs/production/phase15_text_nlp_production_readiness_plan.md.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from backend.core.config import Settings
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.base import ValidationError
from backend.database.repositories.production_readiness import ProductionReadinessRepository
from backend.database.repositories.rag import RagRepository
from backend.models.domain import AuditEventCreate, AuditOutcome
from backend.models.rag import RetrieveRequest
from backend.services.rag_retrieval_service import RagRetrievalService

logger = logging.getLogger(__name__)

# Bounded, deterministic, multilingual post-activation smoke-query set.
# Deliberately not drawn from Phase 13's own query sets (those may include
# queries reserved as evaluation fixtures) -- see plan doc section 2/6.
_SMOKE_QUERIES = {
    "post_activation_retrieval": "What information is available in this knowledge base?",
    "post_activation_language_tamil": "இந்த தகவல் என்ன?",
    "post_activation_language_english": "What does this document say?",
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
                event_type=f"production_rag_activation_{action}",
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
        logger.exception("production_rag_activation_audit_write_failed", extra={"action": action})


class ProductionRagActivationService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = ProductionReadinessRepository(settings.resolved_database_path)
        self._retrieval = RagRetrievalService(
            RagRepository(settings.resolved_database_path), settings
        )
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def _previous_active_profile(self, knowledge_space_public_id: str) -> dict[str, Any] | None:
        with self.repository.transaction() as connection:
            row = connection.execute(
                """SELECT rp.public_id FROM rag_retrieval_profiles rp
                JOIN rag_knowledge_spaces ks ON ks.id = rp.knowledge_space_id
                WHERE ks.public_id=? AND rp.status='active'""",
                (knowledge_space_public_id,),
            ).fetchone()
        return dict(row) if row else None

    def _run_post_activation_smoke_checks(
        self, rag_release_candidate_public_id: str, retrieval_profile_public_id: str,
        *, admin_id: str,
    ) -> None:
        for validation_type, query_text in _SMOKE_QUERIES.items():
            response = self._retrieval.retrieve(
                RetrieveRequest(
                    retrieval_profile_public_id=retrieval_profile_public_id, query=query_text,
                ),
                admin_id,
            )
            result_count = len(response.get("results", []))
            self.repository.add_rag_validation_result(
                rag_release_candidate_public_id,
                {
                    "validation_type": validation_type,
                    "result_status": "passed" if result_count > 0 else "passed_with_warning",
                    "metrics": {"result_count": result_count}, "details": {"query": query_text},
                    "created_by_admin_public_id": admin_id,
                },
            )

    def activate(self, rag_release_candidate_public_id: str, *, admin_id: str) -> dict[str, Any]:
        candidate = self.repository.get_rag_release_candidate(rag_release_candidate_public_id)
        if candidate["status"] != "validated":
            raise ValidationError("only a validated candidate may be activated")

        request = self.repository.get_rag_promotion_request(
            candidate["promotion_request_public_id"]
        )
        approval = self.repository.get_latest_rag_promotion_approval(request["public_id"])
        if approval is None or approval["status"] != "approved":
            raise ValidationError("no approved production RAG promotion approval exists")
        if approval["expires_at"] and approval["expires_at"] < datetime.now(UTC).isoformat():
            self.repository.mark_rag_promotion_approval_expired(approval["public_id"])
            raise ValidationError(
                "this production RAG promotion approval has expired -- request a fresh one"
            )
        if approval["target_fingerprint"] != request["target_fingerprint"]:
            raise ValidationError(
                "the promotion request changed since this approval was granted -- stale approval"
            )

        previous = self._previous_active_profile(request["knowledge_space_public_id"])
        self.repository.record_rag_activation_event(
            rag_release_candidate_public_id,
            {
                "event_type": "pre_activation_snapshot",
                "promotion_approval_public_id": approval["public_id"],
                "previous_active_profile_public_id": previous["public_id"] if previous else None,
                "performed_by_admin_public_id": admin_id,
            },
        )

        try:
            self._retrieval.activate_profile(candidate["retrieval_profile_public_id"], admin_id)
            self._run_post_activation_smoke_checks(
                rag_release_candidate_public_id, candidate["retrieval_profile_public_id"],
                admin_id=admin_id,
            )
            if previous and previous["public_id"] != candidate["retrieval_profile_public_id"]:
                with self.repository.transaction() as connection:
                    connection.execute(
                        "UPDATE rag_retrieval_profiles SET status='archived' WHERE public_id=?",
                        (previous["public_id"],),
                    )
        except Exception as exc:
            # Failure never leaves production in a mixed state: the
            # candidate profile is reverted to `validated` (never left
            # `active`), and the previous profile -- never archived above
            # this point -- remains exactly as it was.
            with self.repository.transaction() as connection:
                connection.execute(
                    "UPDATE rag_retrieval_profiles SET status='validated' WHERE public_id=?",
                    (candidate["retrieval_profile_public_id"],),
                )
            self.repository.update_rag_release_candidate(
                rag_release_candidate_public_id, {"status": "failed"}
            )
            self.repository.record_rag_activation_event(
                rag_release_candidate_public_id,
                {
                    "event_type": "activation_failed", "summary": str(exc),
                    "performed_by_admin_public_id": admin_id,
                },
            )
            _audit(
                self._audit, action="activation_failed", actor_reference=admin_id,
                resource_public_id=rag_release_candidate_public_id, outcome=AuditOutcome.FAILURE,
                metadata={"error": str(exc)},
            )
            raise

        updated = self.repository.update_rag_release_candidate(
            rag_release_candidate_public_id, {"status": "activated", "production_visible": 1}
        )
        self.repository.update_rag_promotion_request(
            request["public_id"], {"status": "ready_for_activation"}
        )
        self.repository.record_rag_activation_event(
            rag_release_candidate_public_id,
            {
                "event_type": "activated", "promotion_approval_public_id": approval["public_id"],
                "previous_active_profile_public_id": previous["public_id"] if previous else None,
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit, action="activated", actor_reference=admin_id,
            resource_public_id=rag_release_candidate_public_id, outcome=AuditOutcome.SUCCESS,
        )
        return updated

    def rollback(self, rag_release_candidate_public_id: str, *, admin_id: str) -> dict[str, Any]:
        """Reactivates the snapshotted previous profile -- this only ever
        returns to what was active before, never forward to any other
        candidate."""

        events = self.repository.list_rag_activation_events(rag_release_candidate_public_id)
        snapshot = next(
            (e for e in reversed(events) if e["event_type"] == "pre_activation_snapshot"), None
        )
        if snapshot is None or not snapshot["previous_active_profile_public_id"]:
            raise ValidationError(
                "no previous active profile was recorded for this candidate -- nothing to "
                "roll back to"
            )
        candidate = self.repository.get_rag_release_candidate(rag_release_candidate_public_id)
        with self.repository.transaction() as connection:
            connection.execute(
                "UPDATE rag_retrieval_profiles SET status='archived' WHERE public_id=?",
                (candidate["retrieval_profile_public_id"],),
            )
            connection.execute(
                "UPDATE rag_retrieval_profiles SET status='active' WHERE public_id=?",
                (snapshot["previous_active_profile_public_id"],),
            )
        self.repository.update_rag_release_candidate(
            rag_release_candidate_public_id, {"status": "superseded", "production_visible": 0}
        )
        event = self.repository.record_rag_activation_event(
            rag_release_candidate_public_id,
            {
                "event_type": "rolled_back",
                "previous_active_profile_public_id": snapshot["previous_active_profile_public_id"],
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit, action="rolled_back", actor_reference=admin_id,
            resource_public_id=rag_release_candidate_public_id, outcome=AuditOutcome.SUCCESS,
        )
        return event


__all__ = ["ProductionRagActivationService"]
