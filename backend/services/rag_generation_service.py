"""Phase 16 grounded generation: retrieve -> filter -> budget context ->
build grounded prompt -> existing controlled inference runtime ->
validate citations -> return a grounded result.

Never loads a model directly and never bypasses assignment or release
eligibility — every generation call goes through
``ModelAssignmentService``/``InferenceRuntimeService`` exactly as Phase
15 established. RAG generation reuses the existing ``admin_diagnostic``
assignment scope (see ``backend/database/schema.py``'s Phase 16 note)
rather than adding a new schema-level scope value.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json
from backend.database.repositories.base import ValidationError
from backend.database.repositories.inference_runtime import InferenceRuntimeRepository
from backend.database.repositories.rag import RagRepository, public_row
from backend.models.rag import (
    GroundedAnswerRequest,
    RagSessionCreate,
    RetrievalFiltersPayload,
    RetrieveRequest,
)
from backend.services.inference_runtime_service import InferenceRuntimeService
from backend.services.model_assignment_service import ModelAssignmentService
from backend.services.rag_retrieval_service import RagRetrievalService
from core_model.rag.answer_policy import (
    NoAnswerThresholds,
    decide_answer_status,
    insufficient_evidence_message,
    should_return_no_answer,
)
from core_model.rag.chunking import estimate_token_count
from core_model.rag.citation_builder import build_citation_map, extract_cited_labels
from core_model.rag.context_budget import ContextBudget, select_chunks_within_budget
from core_model.rag.context_builder import SYSTEM_INSTRUCTIONS, build_grounded_prompt
from core_model.rag.grounding_checks import compute_grounding_quality, unsupported_sentence_ratio
from core_model.rag.grounding_checks import validate_citation as validate_citation_fn
from core_model.rag.language_routing import classify_language

RAG_SCOPE = "admin_diagnostic"
DIAGNOSTIC_DISCLAIMER = "Admin-only grounded diagnostic. This is not the public chatbot."


class RagGenerationService:
    def __init__(
        self,
        repository: RagRepository,
        inference_repository: InferenceRuntimeRepository,
        runtime_service: InferenceRuntimeService,
        assignment_service: ModelAssignmentService,
        retrieval_service: RagRetrievalService,
        settings: Settings,
    ) -> None:
        self.repository = repository
        self.inference_repository = inference_repository
        self.runtime_service = runtime_service
        self.assignment_service = assignment_service
        self.retrieval_service = retrieval_service
        self.settings = settings

    # --- assignment eligibility (reused admin_diagnostic scope) --------------

    def _verify_rag_assignment(self, assignment_public_id: str) -> dict[str, Any]:
        with self.inference_repository.transaction() as connection:
            assignment = self.inference_repository.assignment(connection, assignment_public_id)
            if assignment["scope_key"] != RAG_SCOPE:
                raise ValidationError(
                    f"RAG generation requires an '{RAG_SCOPE}' assignment (reused scope)"
                )
            if assignment["status"] != "active":
                raise ValidationError("assignment must be active for RAG generation")
            facts = self.runtime_service.gather_release_facts(
                connection, assignment["release_public_id"]
            )
            if facts["is_registry_fixture"]:
                raise ValidationError(
                    "registry-workflow fixtures cannot be used for RAG grounded generation"
                )
            if facts["evaluation_status"] == "evaluation_blocked":
                raise ValidationError(
                    "evaluation-blocked releases cannot be used for RAG grounded generation"
                )
            return dict(assignment)

    # --- grounded answer -----------------------------------------------------

    def grounded_answer(self, payload: GroundedAnswerRequest, admin_id: str) -> dict[str, Any]:
        assignment = self._verify_rag_assignment(payload.assignment_public_id)

        retrieval_result = self.retrieval_service.retrieve(
            RetrieveRequest(
                retrieval_profile_public_id=payload.retrieval_profile_public_id,
                query=payload.query,
                filters=payload.filters,
            ),
            admin_id,
        )
        return self._generate_and_persist(
            retrieval_result,
            assignment,
            payload.query,
            admin_id,
            session_public_id=payload.session_public_id,
        )

    def _generate_and_persist(
        self,
        retrieval_result: dict[str, Any],
        assignment: dict[str, Any],
        query: str,
        admin_id: str,
        *,
        session_public_id: str | None,
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            retrieval_run = self.repository.retrieval_run(
                connection, retrieval_result["public_id"]
            )
            retrieved_rows = self.repository.retrieved_chunks_for_run(
                connection, retrieval_run["id"]
            )

            profile = connection.execute(
                "SELECT * FROM rag_retrieval_profiles WHERE id=?",
                (retrieval_run["retrieval_profile_id"],),
            ).fetchone()

            selected: list[dict[str, Any]] = []
            for row in retrieved_rows:
                chunk = connection.execute(
                    "SELECT * FROM rag_chunks WHERE id=?", (row["chunk_id"],)
                ).fetchone()
                source = connection.execute(
                    "SELECT * FROM rag_knowledge_sources WHERE id=?", (row["source_id"],)
                ).fetchone()
                version = connection.execute(
                    "SELECT * FROM rag_source_versions WHERE id=?", (row["source_version_id"],)
                ).fetchone()
                selected.append(
                    {
                        "chunk_public_id": chunk["public_id"],
                        "source_public_id": source["public_id"],
                        "source_version_public_id": version["public_id"],
                        "title": source["title"],
                        "location": chunk["source_location_json"],
                        "rank": row["rank"],
                        "content_checksum_sha256": chunk["content_checksum_sha256"],
                        "estimated_token_count": chunk["estimated_token_count"],
                        "normalized_text": chunk["normalized_text"],
                        "combined_score": row["combined_score"],
                    }
                )

            session_id = None
            if session_public_id:
                session_row = connection.execute(
                    "SELECT id FROM inference_sessions WHERE public_id=?", (session_public_id,)
                ).fetchone()
                session_id = session_row["id"] if session_row else None

            instance = self.assignment_service.ensure_instance_loaded(
                assignment["public_id"], admin_id
            )
            query_tokens = estimate_token_count(query)
            budget = ContextBudget(
                maximum_model_context=instance["profile_maximum_context_length"],
                prompt_template_tokens=estimate_token_count(SYSTEM_INSTRUCTIONS),
                query_tokens=query_tokens,
                reserved_output_tokens=instance["profile_maximum_new_tokens"],
                safety_margin_tokens=10,
            )
            budget_result = select_chunks_within_budget(selected, budget)

            citation_map = build_citation_map(budget_result["selected"])
            evidence_blocks = [
                {
                    "citation_label": label,
                    "title": entry["title"],
                    "location": dumps_json(entry["location"]),
                    "text": entry["normalized_text"],
                }
                for label, entry in citation_map.items()
            ]
            prompt = build_grounded_prompt(evidence_blocks=evidence_blocks, question=query)
            context_checksum = hashlib.sha256(prompt["prompt_text"].encode("utf-8")).hexdigest()

            context_assembly_public_id = self.repository.record_context_assembly(
                connection,
                {
                    "retrieval_run_id": retrieval_run["id"],
                    "maximum_model_context": budget.maximum_model_context,
                    "prompt_template_tokens": budget.prompt_template_tokens,
                    "query_tokens": budget.query_tokens,
                    "retrieved_context_tokens": budget_result["used_tokens"],
                    "reserved_output_tokens": budget.reserved_output_tokens,
                    "safety_margin_tokens": budget.safety_margin_tokens,
                    "dropped_chunk_count": budget_result["dropped_count"],
                    "final_context_checksum_sha256": context_checksum,
                    "citation_map_json": dumps_json(citation_map),
                },
            )
            context_assembly = self.repository.context_assembly(
                connection, context_assembly_public_id
            )

            query_checksum = hashlib.sha256(query.encode("utf-8")).hexdigest()
            model_assignment_row = connection.execute(
                "SELECT id FROM inference_model_assignments WHERE public_id=?",
                (assignment["public_id"],),
            ).fetchone()
            grounded_request_public_id = self.repository.create_grounded_request(
                connection,
                {
                    "context_assembly_id": context_assembly["id"],
                    "retrieval_run_id": retrieval_run["id"],
                    "model_assignment_id": model_assignment_row["id"],
                    "scope": "admin_rag_lab",
                    "session_id": session_id,
                    "query_checksum_sha256": query_checksum,
                    "status": "accepted",
                },
            )
            grounded_request = self.repository.grounded_request(
                connection, grounded_request_public_id
            )

            # Corpus-wide injection disclosure: has any chunk in the queried
            # knowledge space's chunk sets ever been flagged, even though a
            # flagged chunk structurally can never enter an index/context?
            injection_detected_count = connection.execute(
                """SELECT COUNT(*) FROM rag_chunks c
                JOIN rag_chunk_sets cs ON cs.id=c.chunk_set_id
                JOIN rag_source_versions v ON v.id=cs.source_version_id
                JOIN rag_knowledge_sources s ON s.id=v.knowledge_source_id
                WHERE s.knowledge_space_id=? AND c.injection_status != 'clean'""",
                (retrieval_run["knowledge_space_id"],),
            ).fetchone()[0]
            if injection_detected_count:
                self.repository.record_issue(
                    connection,
                    {
                        "grounded_request_id": grounded_request["id"],
                        "issue_code": "prompt_injection_chunk_detected",
                        "severity": "info",
                        "message": (
                            f"{injection_detected_count} chunk(s) in this knowledge space are "
                            "flagged and structurally excluded from all indexes/context"
                        ),
                    },
                )

            language_info = classify_language(query)
            thresholds = NoAnswerThresholds(
                no_answer_score_threshold=(
                    profile["no_answer_threshold"]
                    if profile
                    else self.settings.rag_no_answer_threshold
                )
            )
            top_score = selected[0]["combined_score"] if selected else None
            no_answer, no_answer_reason = should_return_no_answer(
                context_fits=budget_result["fits"],
                selected_chunk_count=len(budget_result["selected"]),
                top_combined_score=top_score,
                only_quarantined_or_blocked=False,
                thresholds=thresholds,
            )

            if no_answer:
                if no_answer_reason:
                    self.repository.record_issue(
                        connection,
                        {
                            "grounded_request_id": grounded_request["id"],
                            "issue_code": no_answer_reason,
                            "severity": "warning",
                        },
                    )
                connection.execute(
                    "UPDATE rag_grounded_requests SET status='insufficient_evidence' WHERE id=?",
                    (grounded_request["id"],),
                )
                answer_text = insufficient_evidence_message(language_info["language_category"])
                answer_public_id = self.repository.record_grounded_answer(
                    connection,
                    {
                        "grounded_request_id": grounded_request["id"],
                        "answer_status": "insufficient_evidence",
                        "answer_checksum_sha256": hashlib.sha256(
                            answer_text.encode("utf-8")
                        ).hexdigest(),
                        "answer_language": language_info["language_category"],
                        "citation_count": 0,
                    },
                )
                self._audit(
                    connection, "rag_no_answer_decision", admin_id, grounded_request_public_id,
                    reason=no_answer_reason,
                )
                return {
                    "grounded_request": public_row(
                        self.repository.grounded_request(connection, grounded_request_public_id)
                    ),
                    "answer": public_row(
                        self.repository.answer_for_request(connection, grounded_request["id"])
                    ),
                    "answer_text": answer_text,
                    "citations": [],
                    "issues": [
                        public_row(row)
                        for row in self.repository.issues_for_request(
                            connection, grounded_request["id"]
                        )
                    ],
                    "disclaimer": DIAGNOSTIC_DISCLAIMER,
                }

            started = time.perf_counter()
            generation = self.runtime_service.run_generation(
                instance["public_id"],
                prompt_text=prompt["prompt_text"],
                maximum_new_tokens=instance["profile_maximum_new_tokens"],
                timeout_seconds=instance["profile_request_timeout_seconds"],
                system_text=SYSTEM_INSTRUCTIONS,
            )
            runtime_ms = int((time.perf_counter() - started) * 1000)

            cited_labels = extract_cited_labels(generation["generated_text"])
            context_chunk_ids = {entry["chunk_public_id"] for entry in citation_map.values()}
            validations = []
            seen_labels: set[str] = set()
            for index, label in enumerate(cited_labels):
                entry = citation_map.get(label)
                expected_checksum = entry["content_checksum_sha256"] if entry else None
                validation = validate_citation_fn(
                    citation_entry=entry,
                    context_chunk_ids=context_chunk_ids,
                    expected_checksum=expected_checksum,
                    citation_index=index,
                    max_citations=self.settings.rag_max_citations,
                    already_seen=label in seen_labels,
                )
                seen_labels.add(label)
                validations.append((label, entry, validation))

            unsupported_ratio = unsupported_sentence_ratio(generation["generated_text"])
            grounding_quality = compute_grounding_quality(
                citation_validations=[v[2] for v in validations],
                unsupported_ratio=unsupported_ratio,
                retrieved_chunk_count=len(selected),
                used_chunk_count=len(budget_result["selected"]),
                no_answer_appropriate=None,
                injection_chunks_detected=injection_detected_count,
                injection_chunks_excluded=injection_detected_count,
            )

            status_result = decide_answer_status(
                retrieval_failed=False,
                generation_failed=generation["stop_reason"] == "invalid_token",
                no_answer=False,
                no_answer_reason=None,
                blocked_evidence_only=False,
                grounding_quality=grounding_quality,
                thresholds=thresholds,
            )

            answer_text = generation["generated_text"]
            if status_result["status"] == "insufficient_evidence":
                answer_text = insufficient_evidence_message(language_info["language_category"])

            answer_public_id = self.repository.record_grounded_answer(
                connection,
                {
                    "grounded_request_id": grounded_request["id"],
                    "answer_status": status_result["status"],
                    "answer_checksum_sha256": hashlib.sha256(
                        answer_text.encode("utf-8")
                    ).hexdigest(),
                    "answer_language": language_info["language_category"],
                    "citation_count": len(validations),
                    "stop_reason": generation["stop_reason"],
                    "runtime_milliseconds": runtime_ms,
                    "role_token_leakage": generation["role_token_leakage"],
                    "prompt_leakage": generation["prompt_leakage"],
                    "unicode_valid": generation["unicode_valid"],
                },
            )
            answer_row = connection.execute(
                "SELECT id FROM rag_grounded_answers WHERE public_id=?", (answer_public_id,)
            ).fetchone()

            for label, entry, validation in validations:
                self.repository.record_citation(
                    connection,
                    {
                        "grounded_answer_id": answer_row["id"],
                        "citation_label": label,
                        "chunk_id": (
                            connection.execute(
                                "SELECT id FROM rag_chunks WHERE public_id=?",
                                (entry["chunk_public_id"],),
                            ).fetchone()["id"]
                            if entry
                            else None
                        ),
                        "source_id": (
                            connection.execute(
                                "SELECT id FROM rag_knowledge_sources WHERE public_id=?",
                                (entry["source_public_id"],),
                            ).fetchone()["id"]
                            if entry
                            else None
                        ),
                        "source_version_id": (
                            connection.execute(
                                "SELECT id FROM rag_source_versions WHERE public_id=?",
                                (entry["source_version_public_id"],),
                            ).fetchone()["id"]
                            if entry
                            else None
                        ),
                        "rank": entry["rank"] if entry else None,
                        "content_checksum_sha256": (
                            entry["content_checksum_sha256"] if entry else None
                        ),
                        "validation_status": validation["status"],
                    },
                )
                if validation["status"] in {"not_present", "invalid"}:
                    self.repository.record_issue(
                        connection,
                        {
                            "grounded_request_id": grounded_request["id"],
                            "issue_code": validation["reason"] or "unknown_citation",
                            "severity": "error",
                            "details_json": dumps_json({"citation_label": label}),
                        },
                    )
            final_status = (
                "completed"
                if status_result["status"] == "grounded_answer"
                else status_result["status"]
            )
            connection.execute(
                "UPDATE rag_grounded_requests SET status=? WHERE id=?",
                (final_status, grounded_request["id"]),
            )
            self._audit(
                connection, "rag_grounded_generation_completed", admin_id,
                grounded_request_public_id, answer_status=status_result["status"],
            )

            return {
                "grounded_request": public_row(
                    self.repository.grounded_request(connection, grounded_request_public_id)
                ),
                "answer": public_row(
                    self.repository.answer_for_request(connection, grounded_request["id"])
                ),
                "answer_text": answer_text,
                "citations": [
                    public_row(row)
                    for row in self.repository.citations_for_answer(connection, answer_row["id"])
                ],
                "issues": [
                    public_row(row)
                    for row in self.repository.issues_for_request(
                        connection, grounded_request["id"]
                    )
                ],
                "disclaimer": DIAGNOSTIC_DISCLAIMER,
            }

    # --- lookups -----------------------------------------------------

    def get_grounded_request(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.grounded_request(connection, public_id))

    def get_answer(self, grounded_request_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            request = self.repository.grounded_request(connection, grounded_request_public_id)
            answer = self.repository.answer_for_request(connection, request["id"])
            return public_row(answer) if answer else {}

    def get_citations(self, grounded_request_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            request = self.repository.grounded_request(connection, grounded_request_public_id)
            answer = self.repository.answer_for_request(connection, request["id"])
            if not answer:
                return {"items": []}
            rows = self.repository.citations_for_answer(connection, answer["id"])
            return {"items": [public_row(row) for row in rows]}

    def get_issues(self, grounded_request_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            request = self.repository.grounded_request(connection, grounded_request_public_id)
            rows = self.repository.issues_for_request(connection, request["id"])
            return {"items": [public_row(row) for row in rows]}

    # --- RAG chat lab (reuses Phase 15 inference_sessions table) --------------

    def create_session(self, payload: RagSessionCreate, admin_id: str) -> dict[str, Any]:
        assignment = self._verify_rag_assignment(payload.assignment_public_id)
        instance = self.assignment_service.ensure_instance_loaded(assignment["public_id"], admin_id)
        with self.inference_repository.transaction() as connection:
            instance_row = connection.execute(
                "SELECT id FROM inference_runtime_instances WHERE public_id=?",
                (instance["public_id"],),
            ).fetchone()
            model_assignment_row = connection.execute(
                "SELECT id FROM inference_model_assignments WHERE public_id=?",
                (assignment["public_id"],),
            ).fetchone()
            session_public_id = self.inference_repository.create_session(
                connection,
                {
                    "model_assignment_id": model_assignment_row["id"],
                    "inference_runtime_instance_id": instance_row["id"],
                    "scope": "admin_rag_lab",
                    "max_turns": payload.max_turns,
                    "created_by_admin_public_id": admin_id,
                },
            )
            self._audit(connection, "rag_session_created", admin_id, session_public_id)
            return {
                "session": self._public_session(connection, session_public_id),
                "retrieval_profile_public_id": payload.retrieval_profile_public_id,
            }

    def _public_session(self, connection, session_public_id: str) -> dict[str, Any]:
        from backend.database.repositories.inference_runtime import public_row as ir_public_row

        return ir_public_row(self.inference_repository.session(connection, session_public_id))

    def get_session(self, public_id: str) -> dict[str, Any]:
        with self.inference_repository.transaction() as connection:
            return self._public_session(connection, public_id)

    def post_message(
        self,
        session_public_id: str,
        message: str,
        retrieval_profile_public_id: str,
        admin_id: str,
    ) -> dict[str, Any]:
        with self.inference_repository.transaction() as connection:
            session = self.inference_repository.session(connection, session_public_id)
            if session["status"] != "active":
                raise ValidationError("session is not active")
            if session["turn_count"] >= session["max_turns"]:
                self.inference_repository.update_session(
                    connection, session["id"], {"status": "expired"}
                )
                raise ValidationError("session has reached its maximum turn count")
            assignment_row = connection.execute(
                "SELECT public_id FROM inference_model_assignments WHERE id=?",
                (session["model_assignment_id"],),
            ).fetchone()
            assignment_public_id = assignment_row["public_id"]

        assignment = self._verify_rag_assignment(assignment_public_id)
        retrieval_result = self.retrieval_service.retrieve(
            RetrieveRequest(
                retrieval_profile_public_id=retrieval_profile_public_id,
                query=message,
                filters=RetrievalFiltersPayload(),
            ),
            admin_id,
        )
        result = self._generate_and_persist(
            retrieval_result, assignment, message, admin_id, session_public_id=session_public_id
        )
        with self.inference_repository.transaction() as connection:
            session = self.inference_repository.session(connection, session_public_id)
            self.inference_repository.update_session(
                connection, session["id"], {"turn_count": session["turn_count"] + 1}
            )
        return result

    def close_session(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.inference_repository.transaction() as connection:
            session = self.inference_repository.session(connection, public_id)
            self.inference_repository.update_session(
                connection, session["id"], {"status": "closed"}
            )
            self._audit(connection, "rag_session_closed", admin_id, public_id)
            return self._public_session(connection, public_id)

    # --- audit -----------------------------------------------------

    def _audit(
        self, connection, event: str, admin_id: str, resource_id: str, **metadata: Any
    ) -> None:
        if not self.settings.audit_enabled:
            return
        connection.execute(
            """INSERT INTO audit_logs(action,actor,details,public_id,event_type,actor_type,
            actor_reference,resource_type,resource_public_id,outcome,metadata_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                event, "admin", "{}", str(uuid4()), event, "admin", admin_id,
                "rag", resource_id, "success", dumps_json(metadata),
            ),
        )
