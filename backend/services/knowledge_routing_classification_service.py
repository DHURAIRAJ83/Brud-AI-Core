"""`KnowledgeRoutingClassificationService` -- wraps the pure
`core_model.knowledge_routing.pipeline.classify()` function with
persistence (migration 039's `routing_classification_decisions` table)
and audit logging, the same wrapper pattern
`ProductionRegressionService` uses around its own pure regression
logic.

This service never calls Model, RAG, Web, Tool, or Memory. It never
persists raw input text -- only the pipeline's own `input_hash`. It is
admin-only by construction: every caller is an Admin-only API route
(Step 16) or an Admin Assistant read-only tool (Step 18).
"""

from __future__ import annotations

import logging
from typing import Any

from backend.core.config import Settings
from backend.database.repositories.knowledge_routing import KnowledgeRoutingRepository
from backend.database.repositories.phase2 import AuditLogRepository
from backend.models.domain import AuditEventCreate, AuditOutcome
from core_model.knowledge_routing.adapters import classify_record
from core_model.knowledge_routing.pipeline import (
    ClassificationInputError,
    ClassificationResult,
    classify,
)

logger = logging.getLogger(__name__)


def _result_to_persist_values(
    result: ClassificationResult, *, created_by_admin_public_id: str | None
) -> dict[str, Any]:
    return {
        "input_hash": result.input_hash,
        "context_type": result.context_type,
        "language_category": result.language_category,
        "intent": result.intent,
        "domain": result.domain,
        "subdomain": result.subdomain,
        "freshness": result.freshness,
        "ambiguity": result.ambiguity,
        "safety_risk": result.safety_risk,
        "evidence_requirement": result.evidence_requirement,
        "execution_route": result.execution_route,
        "learning_target": result.learning_target,
        "requires_human_review": result.requires_human_review,
        "input_truncated": result.input_truncated,
        "reason_codes": result.all_reason_codes,
        "policy_version": result.policy_version,
        "taxonomy_version": result.taxonomy_version,
        "created_by_admin_public_id": created_by_admin_public_id,
    }


class KnowledgeRoutingClassificationService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = KnowledgeRoutingRepository(settings.resolved_database_path)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def _audit_event(
        self,
        *,
        action: str,
        actor_reference: str,
        resource_public_id: str,
        outcome: AuditOutcome,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if self._audit is None:
            return
        try:
            self._audit.append(
                AuditEventCreate(
                    event_type=f"knowledge_routing_{action}",
                    actor_type="admin",
                    actor_reference=actor_reference,
                    action=action,
                    resource_type="routing_classification_decision",
                    resource_public_id=resource_public_id,
                    outcome=outcome,
                    metadata=metadata or {},
                )
            )
        except Exception:
            logger.exception("knowledge_routing_audit_write_failed", extra={"action": action})

    def classify_text(
        self,
        text: str,
        *,
        context_type: str = "public_chat_question",
        actor_reference: str = "system",
        persist: bool = True,
    ) -> dict[str, Any]:
        try:
            result = classify(text, context_type=context_type)
        except ClassificationInputError as exc:
            self._audit_event(
                action="classify_failed",
                actor_reference=actor_reference,
                resource_public_id="n/a",
                outcome=AuditOutcome.FAILURE,
                metadata={"error": str(exc), "context_type": context_type},
            )
            raise

        public = self._result_public(result)
        if persist:
            persisted = self.repository.create_decision(
                _result_to_persist_values(result, created_by_admin_public_id=actor_reference)
            )
            public["public_id"] = persisted["public_id"]
            public["created_at"] = persisted["created_at"]
            self._audit_event(
                action="classify",
                actor_reference=actor_reference,
                resource_public_id=persisted["public_id"],
                outcome=AuditOutcome.SUCCESS,
                metadata={"execution_route": result.execution_route, "context_type": context_type},
            )
        return public

    def classify_structured_record(
        self,
        context_type: str,
        record: dict[str, Any],
        *,
        actor_reference: str = "system",
        persist: bool = True,
    ) -> dict[str, Any]:
        result = classify_record(context_type, record)
        public = self._result_public(result)
        if persist:
            persisted = self.repository.create_decision(
                _result_to_persist_values(result, created_by_admin_public_id=actor_reference)
            )
            public["public_id"] = persisted["public_id"]
            public["created_at"] = persisted["created_at"]
            self._audit_event(
                action="classify_record",
                actor_reference=actor_reference,
                resource_public_id=persisted["public_id"],
                outcome=AuditOutcome.SUCCESS,
                metadata={"execution_route": result.execution_route, "context_type": context_type},
            )
        return public

    def get_decision(self, public_id: str) -> dict[str, Any]:
        return self.repository.get_decision(public_id)

    def list_decisions(self, **kwargs: Any) -> list[dict[str, Any]]:
        return self.repository.list_decisions(**kwargs)

    def aggregate_metrics(self) -> dict[str, Any]:
        return self.repository.aggregate_metrics()

    @staticmethod
    def _result_public(result: ClassificationResult) -> dict[str, Any]:
        return {
            "input_hash": result.input_hash,
            "context_type": result.context_type,
            "policy_version": result.policy_version,
            "taxonomy_version": result.taxonomy_version,
            "language_category": result.language_category,
            "intent": result.intent,
            "intent_secondary": list(result.intent_secondary),
            "intent_confidence_band": result.intent_confidence_band,
            "domain": result.domain,
            "subdomain": result.subdomain,
            "domain_secondary": list(result.domain_secondary),
            "domain_confidence_band": result.domain_confidence_band,
            "freshness": result.freshness,
            "freshness_confidence_band": result.freshness_confidence_band,
            "ambiguity": result.ambiguity,
            "ambiguity_confidence_band": result.ambiguity_confidence_band,
            "safety_risk": result.safety_risk,
            "safety_matched_category": result.safety_matched_category,
            "safety_confidence_band": result.safety_confidence_band,
            "evidence_requirement": result.evidence_requirement,
            "evidence_confidence_band": result.evidence_confidence_band,
            "execution_route": result.execution_route,
            "execution_route_confidence_band": result.execution_route_confidence_band,
            "route_blockers": list(result.route_blockers),
            "learning_target": result.learning_target,
            "learning_target_confidence_band": result.learning_target_confidence_band,
            "grants_training_approval": result.grants_training_approval,
            "requires_human_review": result.requires_human_review,
            "tamil_first_policy_applied": result.tamil_first_policy_applied,
            "tamil_first_policy_violation": result.tamil_first_policy_violation,
            "all_reason_codes": list(result.all_reason_codes),
            "input_truncated": result.input_truncated,
            "recommendation_only": True,
            "route_executed": False,
        }


__all__ = ["KnowledgeRoutingClassificationService"]
