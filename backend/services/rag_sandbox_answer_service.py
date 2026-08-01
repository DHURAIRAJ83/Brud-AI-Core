"""Phase 13 Step 13/14 grounded-answer testing and citation validation.

Reuses `RagGenerationService.grounded_answer()` verbatim -- prompt
construction, context budgeting, citation-map building, insufficient-
evidence refusal, and citation validation are never reimplemented
here. This service only wraps the existing call with sandbox
governance bookkeeping and prefixes the stored answer text with the
required sandbox disclaimer (Step 13) without touching the shared
production service. See
docs/rag_sandbox/phase13_isolated_rag_sandbox_plan.md.
"""

from __future__ import annotations

import hashlib
import logging
import sqlite3
from typing import Any

from backend.core.config import Settings
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.inference_runtime import InferenceRuntimeRepository
from backend.database.repositories.model_release import ModelReleaseRepository
from backend.database.repositories.rag import RagRepository
from backend.database.repositories.rag_sandbox import RagSandboxRepository
from backend.models.domain import AuditEventCreate, AuditOutcome
from backend.models.rag import GroundedAnswerRequest
from backend.services.inference_runtime_service import InferenceRuntimeService
from backend.services.model_assignment_service import ModelAssignmentService
from backend.services.rag_generation_service import RagGenerationService
from backend.services.rag_retrieval_service import RagRetrievalService
from backend.services.rag_sandbox_eligibility_service import RagSandboxError
from core_model.rag_sandbox import SANDBOX_DISCLAIMER_EN

logger = logging.getLogger(__name__)

# Production's 4-value citation vocabulary maps onto 4 of the sandbox's
# 6-value vocabulary; "unsupported"/"conflicting" are Phase 13-only
# richer classifications not yet computed here (Known Limitations) --
# never fabricated, only left absent.
_CITATION_STATUS_MAP = {
    "valid": "valid",
    "valid_with_warning": "partially_supporting",
    "invalid": "invalid",
    "not_present": "missing",
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
                event_type=f"rag_sandbox_{action}",
                actor_type="admin",
                actor_reference=actor_reference,
                action=action,
                resource_type="rag_sandbox_experiment",
                resource_public_id=resource_public_id,
                outcome=outcome,
                metadata=metadata or {},
            )
        )
    except Exception:
        logger.exception("rag_sandbox_audit_write_failed", extra={"action": action})


class RagSandboxAnswerService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._sandbox = RagSandboxRepository(settings.resolved_database_path)
        self._rag_repository = RagRepository(settings.resolved_database_path)
        inference_repository = InferenceRuntimeRepository(settings.resolved_database_path)
        release_repository = ModelReleaseRepository(settings.resolved_database_path)
        runtime_service = InferenceRuntimeService(
            inference_repository, release_repository, settings
        )
        assignment_service = ModelAssignmentService(
            inference_repository, release_repository, runtime_service, settings
        )
        retrieval_service = RagRetrievalService(self._rag_repository, settings)
        self._generation = RagGenerationService(
            self._rag_repository,
            inference_repository,
            runtime_service,
            assignment_service,
            retrieval_service,
            settings,
        )
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def _retrieval_profile_public_id(self, retrieval_profile_id: int) -> str:
        with sqlite3.connect(self.settings.resolved_database_path) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT public_id FROM rag_retrieval_profiles WHERE id=?",
                (retrieval_profile_id,),
            ).fetchone()
        if not row:
            raise RagSandboxError("this sandbox index has no active retrieval profile")
        return row["public_id"]

    def run_generation(
        self,
        experiment_public_id: str,
        *,
        retrieval_run_public_id: str,
        generation_assignment_public_id: str,
        admin_id: str,
    ) -> dict[str, Any]:
        retrieval_run = self._sandbox.get_retrieval_run(retrieval_run_public_id)
        index_row = self._sandbox.get_index(retrieval_run["index_public_id"])
        retrieval_profile_public_id = self._retrieval_profile_public_id(
            index_row["retrieval_profile_id"]
        )
        results = self._sandbox.list_retrieval_results(retrieval_run_public_id)
        if not results:
            raise RagSandboxError("the retrieval run has no results to generate answers for")

        self._sandbox.update_experiment(
            experiment_public_id,
            {"status": "running_generation", "current_stage": "answer_generation"},
        )

        answer_runs: list[dict[str, Any]] = []
        for retrieval_result in results:
            query = self._sandbox.get_query(retrieval_result["query_public_id"])
            generation_result = self._generation.grounded_answer(
                GroundedAnswerRequest(
                    retrieval_profile_public_id=retrieval_profile_public_id,
                    assignment_public_id=generation_assignment_public_id,
                    query=query["query_text"],
                ),
                admin_id,
            )
            grounded_request = generation_result["grounded_request"]
            answer = generation_result["answer"]
            raw_answer_text = generation_result["answer_text"]
            sandbox_answer_text = f"{SANDBOX_DISCLAIMER_EN}\n\n{raw_answer_text}"

            status_map = {
                "insufficient_evidence": "insufficient_evidence",
                "completed": "grounded_answer",
                "citation_error": "generation_failed",
                "generation_failed": "generation_failed",
                "retrieval_failed": "retrieval_failed",
            }
            answer_run_status = status_map.get(grounded_request["status"], "grounded_answer")

            answer_run = self._sandbox.add_answer_run(
                experiment_public_id,
                {
                    "retrieval_result_public_id": retrieval_result["public_id"],
                    "query_public_id": query["public_id"],
                    "rag_grounded_request_id": None,
                    "generation_assignment_key": generation_assignment_public_id,
                    "answer_text": sandbox_answer_text,
                    "answer_checksum": hashlib.sha256(
                        sandbox_answer_text.encode("utf-8")
                    ).hexdigest(),
                    "answer_language": answer.get("answer_language", "unknown"),
                    "used_source_ids": [
                        citation["public_id"] for citation in generation_result["citations"]
                    ],
                    "citation_count": len(generation_result["citations"]),
                    "unsupported_claim_count": 0,
                    "insufficient_evidence_detected": answer_run_status
                    == "insufficient_evidence",
                    "conflict_detected": False,
                    "refusal_used": answer_run_status == "insufficient_evidence",
                    "latency_milliseconds": answer.get("runtime_milliseconds"),
                    "token_usage": {},
                    "status": answer_run_status,
                    "performed_by_admin_public_id": admin_id,
                },
            )

            seen_labels: set[str] = set()
            for citation in generation_result["citations"]:
                label = citation["citation_label"]
                is_duplicate = label in seen_labels
                seen_labels.add(label)
                production_status = citation["validation_status"]
                mapped_status = _CITATION_STATUS_MAP.get(production_status, "invalid")
                self._sandbox.add_citation(
                    answer_run["public_id"],
                    {
                        "citation_label": label,
                        "rag_citation_id": None,
                        "references_retrieved_source": production_status != "not_present",
                        "source_exists": production_status not in ("invalid", "not_present"),
                        "checksum_matches": (
                            True
                            if production_status in ("valid", "valid_with_warning")
                            else (False if production_status == "invalid" else None)
                        ),
                        "supports_nearby_claim": None,
                        "is_duplicate": is_duplicate,
                        "is_orphan": production_status == "not_present",
                        "validation_status": mapped_status,
                        "reason": production_status,
                    },
                )

            answer_runs.append(answer_run)

        self._sandbox.record_event(
            experiment_public_id,
            {
                "event_type": "answer_run_completed",
                "summary": f"{len(answer_runs)} answer run(s) completed",
                "metadata": {"retrieval_run_public_id": retrieval_run_public_id},
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit,
            action="run_generation",
            actor_reference=admin_id,
            resource_public_id=experiment_public_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"answer_run_count": len(answer_runs)},
        )
        return {"answer_runs": answer_runs}


__all__ = ["RagSandboxAnswerService"]
