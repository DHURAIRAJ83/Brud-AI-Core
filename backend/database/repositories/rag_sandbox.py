"""Repository for the Phase 13 Isolated RAG Sandbox, Retrieval
Evaluation, Grounded Answer Testing & Admin Acceptance workflow:
experiments, approvals, corpora, records, indexes, query sets,
queries, retrieval runs/results, answer runs, citations, evaluations,
human reviews, reports, acceptances, events, and deletion-request
transitions.

Reads (never writes) Phase 12's `external_dataset_sample_*` tables and
Phase 11's `external_dataset_verification_cases`. Writes governance
rows only -- actual chunking/embedding/indexing/retrieval/generation
rows live in the existing, unmodified Phase 16 `rag_*` tables, created
via `RagIngestionService`/`RagRetrievalService`/`RagGenerationService`
scoped to the experiment's own `rag_knowledge_spaces` row. Never
writes to any training-dataset or model-release table. See
docs/rag_sandbox/phase13_isolated_rag_sandbox_plan.md.
"""

from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError, ValidationError


def _experiment_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "experiment_code": row["experiment_code"],
        "sample_import_public_id": row["sample_import_public_id"],
        "sample_report_public_id": row["sample_report_public_id"],
        "verification_case_public_id": row["verification_case_public_id"],
        "knowledge_space_public_id": row["knowledge_space_public_id"],
        "status": row["status"],
        "current_stage": row["current_stage"],
        "purpose": row["purpose"],
        "sample_report_checksum": row["sample_report_checksum"],
        "accepted_record_checksum_set_hash": row["accepted_record_checksum_set_hash"],
        "maximum_records": row["maximum_records"],
        "maximum_total_characters": row["maximum_total_characters"],
        "maximum_total_tokens": row["maximum_total_tokens"],
        "threshold_version": row["threshold_version"],
        "evaluation_version": row["evaluation_version"],
        "production_rag_readiness": row["production_rag_readiness"],
        "training_data_observation": row["training_data_observation"],
        "eligible_for_production_rag_proposal": (
            None
            if row["eligible_for_production_rag_proposal"] is None
            else bool(row["eligible_for_production_rag_proposal"])
        ),
        "eligible_for_training_assessment": (
            None
            if row["eligible_for_training_assessment"] is None
            else bool(row["eligible_for_training_assessment"])
        ),
        "expires_at": row["expires_at"],
        "created_by_admin_public_id": row["created_by_admin_public_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "deleted_at": row["deleted_at"],
    }


def _approval_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "experiment_public_id": row["experiment_public_id"],
        "sample_import_public_id": row["sample_import_public_id"],
        "sample_report_public_id": row["sample_report_public_id"],
        "verification_case_public_id": row["verification_case_public_id"],
        "approved_by_admin_id": row["approved_by_admin_id"],
        "approved_at": row["approved_at"],
        "expires_at": row["expires_at"],
        "purpose": row["purpose"],
        "accepted_record_ids": loads_json(row["accepted_record_ids_json"]),
        "accepted_record_checksums": loads_json(row["accepted_record_checksums_json"]),
        "maximum_records": row["maximum_records"],
        "maximum_total_characters": row["maximum_total_characters"],
        "maximum_total_tokens": row["maximum_total_tokens"],
        "chunking_configuration": loads_json(row["chunking_configuration_json"]),
        "retrieval_configuration": loads_json(row["retrieval_configuration_json"]),
        "embedding_assignment_key": row["embedding_assignment_key"],
        "generation_assignment_key": row["generation_assignment_key"],
        "query_set_public_id": row["query_set_public_id"],
        "target_fingerprint": row["target_fingerprint"],
        "conditions": loads_json(row["conditions_json"]),
        "status": row["status"],
        "requested_by_admin_public_id": row["requested_by_admin_public_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _corpus_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "experiment_public_id": row["experiment_public_id"],
        "knowledge_space_public_id": row["knowledge_space_public_id"],
        "sandbox_scope_key": row["sandbox_scope_key"],
        "production_visible": bool(row["production_visible"]),
        "status": row["status"],
        "record_count": row["record_count"],
        "total_characters": row["total_characters"],
        "created_by_admin_public_id": row["created_by_admin_public_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _record_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "experiment_public_id": row["experiment_public_id"],
        "corpus_public_id": row["corpus_public_id"],
        "sample_record_public_id": row["sample_record_public_id"],
        "selected_revision_id": row["selected_revision_id"],
        "content": row["content"],
        "content_checksum": row["content_checksum"],
        "language": row["language"],
        "task": row["task"],
        "source_file_id": row["source_file_id"],
        "source_location": row["source_location"],
        "rights_reference": row["rights_reference"],
        "conditions": loads_json(row["conditions_json"]),
        "contamination_flagged": bool(row["contamination_flagged"]),
        "rag_source_id": row["rag_source_id"],
        "rag_source_version_id": row["rag_source_version_id"],
        "created_at": row["created_at"],
    }


def _index_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "experiment_public_id": row["experiment_public_id"],
        "corpus_public_id": row["corpus_public_id"],
        "index_kind": row["index_kind"],
        "chunk_set_id": row["chunk_set_id"],
        "embedding_model_id": row["embedding_model_id"],
        "rag_vector_index_id": row["rag_vector_index_id"],
        "rag_keyword_index_id": row["rag_keyword_index_id"],
        "retrieval_profile_id": row["retrieval_profile_id"],
        "build_config": loads_json(row["build_config_json"]),
        "chunk_count": row["chunk_count"],
        "record_count": row["record_count"],
        "build_checksum": row["build_checksum"],
        "resource_usage": loads_json(row["resource_usage_json"]),
        "status": row["status"],
        "created_by_admin_public_id": row["created_by_admin_public_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _query_set_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "experiment_public_id": row["experiment_public_id"],
        "name": row["name"],
        "status": row["status"],
        "query_count": row["query_count"],
        "finalized_by_admin_public_id": row["finalized_by_admin_public_id"],
        "finalized_at": row["finalized_at"],
        "created_by_admin_public_id": row["created_by_admin_public_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _query_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "query_set_public_id": row["query_set_public_id"],
        "query_text": row["query_text"],
        "language": row["language"],
        "query_type": row["query_type"],
        "expected_source_ids": loads_json(row["expected_source_ids_json"]),
        "expected_answer_notes": row["expected_answer_notes"],
        "must_refuse_if_insufficient": bool(row["must_refuse_if_insufficient"]),
        "conflict_expected": bool(row["conflict_expected"]),
        "injection_test": bool(row["injection_test"]),
        "human_authored": bool(row["human_authored"]),
        "reviewed_by_admin_public_id": row["reviewed_by_admin_public_id"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
    }


def _retrieval_run_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "experiment_public_id": row["experiment_public_id"],
        "index_public_id": row["index_public_id"],
        "query_set_public_id": row["query_set_public_id"],
        "config_label": row["config_label"],
        "total_queries": row["total_queries"],
        "status": row["status"],
        "performed_by_admin_public_id": row["performed_by_admin_public_id"],
        "started_at": row["started_at"],
        "completed_at": row["completed_at"],
        "created_at": row["created_at"],
    }


def _retrieval_result_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "retrieval_run_public_id": row["retrieval_run_public_id"],
        "query_public_id": row["query_public_id"],
        "rag_retrieval_run_id": row["rag_retrieval_run_id"],
        "metric_availability": row["metric_availability"],
        "expected_source_hit": (
            None if row["expected_source_hit"] is None else bool(row["expected_source_hit"])
        ),
        "source_rank": row["source_rank"],
        "recall_at_k": row["recall_at_k"],
        "precision_at_k": row["precision_at_k"],
        "reciprocal_rank": row["reciprocal_rank"],
        "language_match": (
            None if row["language_match"] is None else bool(row["language_match"])
        ),
        "duplicate_result_rate": row["duplicate_result_rate"],
        "conflicting_source_retrieved": bool(row["conflicting_source_retrieved"]),
        "insufficient_evidence_behavior": row["insufficient_evidence_behavior"],
        "latency_milliseconds": row["latency_milliseconds"],
        "result_count": row["result_count"],
        "created_at": row["created_at"],
    }


def _answer_run_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "experiment_public_id": row["experiment_public_id"],
        "retrieval_result_public_id": row["retrieval_result_public_id"],
        "query_public_id": row["query_public_id"],
        "rag_grounded_request_id": row["rag_grounded_request_id"],
        "generation_assignment_key": row["generation_assignment_key"],
        "prompt_version": row["prompt_version"],
        "answer_text": row["answer_text"],
        "answer_checksum": row["answer_checksum"],
        "answer_language": row["answer_language"],
        "used_source_ids": loads_json(row["used_source_ids_json"]),
        "citation_count": row["citation_count"],
        "unsupported_claim_count": row["unsupported_claim_count"],
        "insufficient_evidence_detected": bool(row["insufficient_evidence_detected"]),
        "conflict_detected": bool(row["conflict_detected"]),
        "refusal_used": bool(row["refusal_used"]),
        "latency_milliseconds": row["latency_milliseconds"],
        "token_usage": loads_json(row["token_usage_json"]),
        "status": row["status"],
        "performed_by_admin_public_id": row["performed_by_admin_public_id"],
        "created_at": row["created_at"],
    }


def _citation_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "answer_run_public_id": row["answer_run_public_id"],
        "citation_label": row["citation_label"],
        "rag_citation_id": row["rag_citation_id"],
        "references_retrieved_source": bool(row["references_retrieved_source"]),
        "source_exists": bool(row["source_exists"]),
        "checksum_matches": (
            None if row["checksum_matches"] is None else bool(row["checksum_matches"])
        ),
        "supports_nearby_claim": (
            None
            if row["supports_nearby_claim"] is None
            else bool(row["supports_nearby_claim"])
        ),
        "is_duplicate": bool(row["is_duplicate"]),
        "is_orphan": bool(row["is_orphan"]),
        "validation_status": row["validation_status"],
        "reason": row["reason"],
        "created_at": row["created_at"],
    }


def _evaluation_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "experiment_public_id": row["experiment_public_id"],
        "answer_run_public_id": row["answer_run_public_id"],
        "query_public_id": row["query_public_id"],
        "evaluation_type": row["evaluation_type"],
        "result_status": row["result_status"],
        "automated": bool(row["automated"]),
        "score": row["score"],
        "details": loads_json(row["details_json"]),
        "evaluation_version": row["evaluation_version"],
        "created_at": row["created_at"],
    }


def _human_review_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "experiment_public_id": row["experiment_public_id"],
        "query_public_id": row["query_public_id"],
        "answer_run_public_id": row["answer_run_public_id"],
        "retrieval_relevant": (
            None if row["retrieval_relevant"] is None else bool(row["retrieval_relevant"])
        ),
        "answer_grounded": (
            None if row["answer_grounded"] is None else bool(row["answer_grounded"])
        ),
        "citations_correct": (
            None if row["citations_correct"] is None else bool(row["citations_correct"])
        ),
        "language_appropriate": (
            None
            if row["language_appropriate"] is None
            else bool(row["language_appropriate"])
        ),
        "refusal_correct": (
            None if row["refusal_correct"] is None else bool(row["refusal_correct"])
        ),
        "conflict_handled": (
            None if row["conflict_handled"] is None else bool(row["conflict_handled"])
        ),
        "injection_resisted": (
            None if row["injection_resisted"] is None else bool(row["injection_resisted"])
        ),
        "decision": row["decision"],
        "notes": row["notes"],
        "reviewer_admin_public_id": row["reviewer_admin_public_id"],
        "reviewed_at": row["reviewed_at"],
        "created_at": row["created_at"],
    }


def _report_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "experiment_public_id": row["experiment_public_id"],
        "report_version": row["report_version"],
        "report": loads_json(row["report_json"]),
        "report_checksum_sha256": row["report_checksum_sha256"],
        "production_rag_readiness": row["production_rag_readiness"],
        "training_data_observation": row["training_data_observation"],
        "recommended_next_action": row["recommended_next_action"],
        "finalized_by_admin_public_id": row["finalized_by_admin_public_id"],
        "finalized_at": row["finalized_at"],
        "created_at": row["created_at"],
    }


def _acceptance_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "experiment_public_id": row["experiment_public_id"],
        "report_public_id": row["report_public_id"],
        "decision": row["decision"],
        "reason": row["reason"],
        "conditions": loads_json(row["conditions_json"]),
        "reviewer_admin_public_id": row["reviewer_admin_public_id"],
        "reviewed_at": row["reviewed_at"],
        "report_checksum_sha256": row["report_checksum_sha256"],
        "target_fingerprint": row["target_fingerprint"],
        "created_at": row["created_at"],
    }


def _event_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "experiment_public_id": row["experiment_public_id"],
        "event_type": row["event_type"],
        "from_status": row["from_status"],
        "to_status": row["to_status"],
        "summary": row["summary"],
        "metadata": loads_json(row["metadata_json"]),
        "performed_by_admin_public_id": row["performed_by_admin_public_id"],
        "created_at": row["created_at"],
    }


def _deletion_request_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "deletion_request_code": row["deletion_request_code"],
        "experiment_public_id": row["experiment_public_id"],
        "status": row["status"],
        "impact_preview": loads_json(row["impact_preview_json"]),
        "reason": row["reason"],
        "requested_by_admin_public_id": row["requested_by_admin_public_id"],
        "requested_at": row["requested_at"],
        "confirmed_by_admin_public_id": row["confirmed_by_admin_public_id"],
        "confirmed_at": row["confirmed_at"],
        "executed_at": row["executed_at"],
        "cancelled_at": row["cancelled_at"],
        "created_at": row["created_at"],
    }


class RagSandboxRepository(BaseRepository):
    # -- shared lookups -----------------------------------------------------------

    def _experiment_row(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT id, status, deleted_at FROM rag_sandbox_experiments WHERE public_id=?",
            (public_id,),
        ).fetchone()
        if not row:
            raise NotFoundError("rag sandbox experiment not found")
        return row

    def _experiment_id(self, connection: sqlite3.Connection, public_id: str) -> int:
        return self._experiment_row(connection, public_id)["id"]

    def _sample_import_id(self, connection: sqlite3.Connection, public_id: str) -> int:
        row = connection.execute(
            "SELECT id FROM external_dataset_sample_imports WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("sample import not found")
        return row["id"]

    def _sample_report_id(self, connection: sqlite3.Connection, public_id: str) -> int:
        row = connection.execute(
            "SELECT id FROM external_dataset_sample_reports WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("sample report not found")
        return row["id"]

    def _verification_case_id(self, connection: sqlite3.Connection, public_id: str) -> int:
        row = connection.execute(
            "SELECT id FROM external_dataset_verification_cases WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("verification case not found")
        return row["id"]

    def _corpus_row(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT id, experiment_id, knowledge_space_id "
            "FROM rag_sandbox_corpora WHERE public_id=?",
            (public_id,),
        ).fetchone()
        if not row:
            raise NotFoundError("rag sandbox corpus not found")
        return row

    def _index_id(self, connection: sqlite3.Connection, public_id: str) -> int:
        row = connection.execute(
            "SELECT id FROM rag_sandbox_indexes WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("rag sandbox index not found")
        return row["id"]

    def _query_set_row(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT id, status FROM rag_sandbox_query_sets WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("rag sandbox query set not found")
        return row

    def _query_id(self, connection: sqlite3.Connection, public_id: str) -> int:
        row = connection.execute(
            "SELECT id FROM rag_sandbox_queries WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("rag sandbox query not found")
        return row["id"]

    def _retrieval_run_id(self, connection: sqlite3.Connection, public_id: str) -> int:
        row = connection.execute(
            "SELECT id FROM rag_sandbox_retrieval_runs WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("rag sandbox retrieval run not found")
        return row["id"]

    def _retrieval_result_id(self, connection: sqlite3.Connection, public_id: str) -> int:
        row = connection.execute(
            "SELECT id FROM rag_sandbox_retrieval_results WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("rag sandbox retrieval result not found")
        return row["id"]

    def _answer_run_id(self, connection: sqlite3.Connection, public_id: str) -> int:
        row = connection.execute(
            "SELECT id FROM rag_sandbox_answer_runs WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("rag sandbox answer run not found")
        return row["id"]

    def _report_row(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT id, experiment_id FROM rag_sandbox_reports WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("rag sandbox report not found")
        return row

    # -- experiments ----------------------------------------------------------------

    def create_experiment(self, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            sample_import_id = self._sample_import_id(
                connection, values["sample_import_public_id"]
            )
            sample_report_id = None
            if values.get("sample_report_public_id"):
                sample_report_id = self._sample_report_id(
                    connection, values["sample_report_public_id"]
                )
            verification_case_id = self._verification_case_id(
                connection, values["verification_case_public_id"]
            )
            connection.execute(
                """INSERT INTO rag_sandbox_experiments(
                public_id, experiment_code, sample_import_id, sample_report_id,
                verification_case_id, purpose, sample_report_checksum,
                accepted_record_checksum_set_hash, maximum_records,
                maximum_total_characters, maximum_total_tokens, expires_at,
                created_by_admin_public_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    values["experiment_code"],
                    sample_import_id,
                    sample_report_id,
                    verification_case_id,
                    values["purpose"],
                    values.get("sample_report_checksum"),
                    values.get("accepted_record_checksum_set_hash"),
                    values.get("maximum_records", 500),
                    values.get("maximum_total_characters", 2_000_000),
                    values.get("maximum_total_tokens", 500_000),
                    values.get("expires_at"),
                    values["created_by_admin_public_id"],
                ),
            )
        return self.get_experiment(public_id)

    def get_experiment(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._experiment_select_sql() + " WHERE e.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("rag sandbox experiment not found")
        return _experiment_public(row)

    def list_experiments(
        self,
        *,
        status: str | None = None,
        sample_import_public_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        limit, offset = self.pagination(limit, offset)
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("e.status=?")
            params.append(status)
        if sample_import_public_id:
            clauses.append("si.public_id=?")
            params.append(sample_import_public_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.transaction() as connection:
            rows = connection.execute(
                self._experiment_select_sql() + f" {where} "  # noqa: S608
                "ORDER BY e.id DESC LIMIT ? OFFSET ?",
                (*params, limit, offset),
            ).fetchall()
        return [_experiment_public(row) for row in rows]

    def get_active_experiment_for_sample_report(
        self, sample_report_public_id: str
    ) -> dict[str, Any] | None:
        with self.transaction() as connection:
            row = connection.execute(
                self._experiment_select_sql()
                + """ WHERE sr.public_id=? AND e.status NOT IN (
                    'rejected','failed','cancelled','expired','withdrawn','deleted'
                ) ORDER BY e.id DESC LIMIT 1""",
                (sample_report_public_id,),
            ).fetchone()
        return _experiment_public(row) if row else None

    def update_experiment(self, public_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        if not fields:
            return self.get_experiment(public_id)
        with self.transaction() as connection:
            self._experiment_id(connection, public_id)
            assignments = ", ".join(f'"{key}"=?' for key in fields)
            connection.execute(
                f'UPDATE rag_sandbox_experiments SET {assignments}, '  # noqa: S608
                "updated_at=CURRENT_TIMESTAMP WHERE public_id=?",
                (*fields.values(), public_id),
            )
        return self.get_experiment(public_id)

    def set_experiment_knowledge_space(
        self, public_id: str, knowledge_space_id: int
    ) -> dict[str, Any]:
        with self.transaction() as connection:
            self._experiment_id(connection, public_id)
            connection.execute(
                """UPDATE rag_sandbox_experiments
                SET knowledge_space_id=?, updated_at=CURRENT_TIMESTAMP WHERE public_id=?""",
                (knowledge_space_id, public_id),
            )
        return self.get_experiment(public_id)

    def mark_experiment_deleted(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            self._experiment_id(connection, public_id)
            connection.execute(
                """UPDATE rag_sandbox_experiments
                SET status='deleted', deleted_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP
                WHERE public_id=?""",
                (public_id,),
            )
        return self.get_experiment(public_id)

    def overview_counts(self) -> dict[str, int]:
        with self.transaction() as connection:
            awaiting_approval = connection.execute(
                "SELECT COUNT(*) FROM rag_sandbox_experiments WHERE status=?",
                ("awaiting_approval",),
            ).fetchone()[0]
            building_index = connection.execute(
                "SELECT COUNT(*) FROM rag_sandbox_experiments WHERE status=?",
                ("building_index",),
            ).fetchone()[0]
            ready = connection.execute(
                "SELECT COUNT(*) FROM rag_sandbox_experiments WHERE status=?", ("ready",)
            ).fetchone()[0]
            needs_review = connection.execute(
                "SELECT COUNT(*) FROM rag_sandbox_experiments WHERE status=?",
                ("needs_review",),
            ).fetchone()[0]
            accepted = connection.execute(
                """SELECT COUNT(*) FROM rag_sandbox_experiments
                WHERE status IN ('accepted','accepted_with_conditions')"""
            ).fetchone()[0]
            rejected = connection.execute(
                "SELECT COUNT(*) FROM rag_sandbox_experiments WHERE status=?", ("rejected",)
            ).fetchone()[0]
            citation_failures = connection.execute(
                """SELECT COUNT(*) FROM rag_sandbox_citations
                WHERE validation_status IN ('unsupported','missing','invalid','conflicting')"""
            ).fetchone()[0]
            unsupported_claim_failures = connection.execute(
                """SELECT COUNT(*) FROM rag_sandbox_evaluations
                WHERE evaluation_type='unsupported_claim' AND result_status IN
                ('unsupported','conflicting_evidence')"""
            ).fetchone()[0]
            injection_failures = connection.execute(
                """SELECT COUNT(*) FROM rag_sandbox_evaluations
                WHERE evaluation_type='prompt_injection' AND result_status IN
                ('failed','warning')"""
            ).fetchone()[0]
            potentially_ready_for_production = connection.execute(
                """SELECT COUNT(*) FROM rag_sandbox_experiments
                WHERE production_rag_readiness IN ('potentially_ready','ready_with_conditions')"""
            ).fetchone()[0]
        return {
            "rag_sandbox_experiments_awaiting_approval": awaiting_approval,
            "rag_sandbox_indexes_building": building_index,
            "rag_sandbox_experiments_ready_for_testing": ready,
            "rag_sandbox_experiments_needing_human_review": needs_review,
            "rag_sandbox_experiments_accepted": accepted,
            "rag_sandbox_experiments_rejected": rejected,
            "rag_sandbox_citation_failures": citation_failures,
            "rag_sandbox_unsupported_claim_failures": unsupported_claim_failures,
            "rag_sandbox_injection_test_failures": injection_failures,
            "rag_sandbox_experiments_potentially_ready_for_production_rag": (
                potentially_ready_for_production
            ),
        }

    @staticmethod
    def _experiment_select_sql() -> str:
        return (
            "SELECT e.*, si.public_id AS sample_import_public_id, "
            "sr.public_id AS sample_report_public_id, "
            "vc.public_id AS verification_case_public_id, "
            "ks.public_id AS knowledge_space_public_id "
            "FROM rag_sandbox_experiments e "
            "JOIN external_dataset_sample_imports si ON si.id = e.sample_import_id "
            "LEFT JOIN external_dataset_sample_reports sr ON sr.id = e.sample_report_id "
            "JOIN external_dataset_verification_cases vc ON vc.id = e.verification_case_id "
            "LEFT JOIN rag_knowledge_spaces ks ON ks.id = e.knowledge_space_id"
        )

    # -- approvals --------------------------------------------------------------------

    def create_approval(self, experiment_public_id: str, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            experiment_id = self._experiment_id(connection, experiment_public_id)
            sample_import_id = self._sample_import_id(
                connection, values["sample_import_public_id"]
            )
            sample_report_id = self._sample_report_id(
                connection, values["sample_report_public_id"]
            )
            verification_case_id = self._verification_case_id(
                connection, values["verification_case_public_id"]
            )
            query_set_id = None
            if values.get("query_set_public_id"):
                query_set_id = self._query_set_row(connection, values["query_set_public_id"])["id"]
            connection.execute(
                """INSERT INTO rag_sandbox_approvals(
                public_id, experiment_id, sample_import_id, sample_report_id,
                verification_case_id, expires_at, purpose, accepted_record_ids_json,
                accepted_record_checksums_json, maximum_records, maximum_total_characters,
                maximum_total_tokens, chunking_configuration_json, retrieval_configuration_json,
                embedding_assignment_key, generation_assignment_key, query_set_id,
                target_fingerprint, conditions_json, requested_by_admin_public_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    experiment_id,
                    sample_import_id,
                    sample_report_id,
                    verification_case_id,
                    values.get("expires_at"),
                    values["purpose"],
                    dumps_json(values.get("accepted_record_ids", [])),
                    dumps_json(values.get("accepted_record_checksums", [])),
                    values["maximum_records"],
                    values["maximum_total_characters"],
                    values["maximum_total_tokens"],
                    dumps_json(values.get("chunking_configuration", {})),
                    dumps_json(values.get("retrieval_configuration", {})),
                    values.get("embedding_assignment_key"),
                    values.get("generation_assignment_key"),
                    query_set_id,
                    values["target_fingerprint"],
                    dumps_json(values.get("conditions", {})),
                    values["requested_by_admin_public_id"],
                ),
            )
        return self.get_approval(public_id)

    def approve_approval(
        self, public_id: str, *, approved_by_admin_id: str, expires_at: str | None
    ) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT id, status FROM rag_sandbox_approvals WHERE public_id=?", (public_id,)
            ).fetchone()
            if not row:
                raise NotFoundError("rag sandbox approval not found")
            if row["status"] != "pending":
                raise ValidationError("only a pending approval may be approved")
            connection.execute(
                """UPDATE rag_sandbox_approvals
                SET status='approved', approved_by_admin_id=?, approved_at=CURRENT_TIMESTAMP,
                expires_at=COALESCE(?, expires_at), updated_at=CURRENT_TIMESTAMP
                WHERE public_id=?""",
                (approved_by_admin_id, expires_at, public_id),
            )
        return self.get_approval(public_id)

    def reject_approval(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT id, status FROM rag_sandbox_approvals WHERE public_id=?", (public_id,)
            ).fetchone()
            if not row:
                raise NotFoundError("rag sandbox approval not found")
            if row["status"] != "pending":
                raise ValidationError("only a pending approval may be rejected")
            connection.execute(
                """UPDATE rag_sandbox_approvals
                SET status='rejected', updated_at=CURRENT_TIMESTAMP WHERE public_id=?""",
                (public_id,),
            )
        return self.get_approval(public_id)

    def expire_approval(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT id, status FROM rag_sandbox_approvals WHERE public_id=?", (public_id,)
            ).fetchone()
            if not row:
                raise NotFoundError("rag sandbox approval not found")
            if row["status"] not in ("pending", "approved"):
                raise ValidationError("only a pending or approved approval may expire")
            connection.execute(
                """UPDATE rag_sandbox_approvals
                SET status='expired', updated_at=CURRENT_TIMESTAMP WHERE public_id=?""",
                (public_id,),
            )
        return self.get_approval(public_id)

    def supersede_approval(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT id, status FROM rag_sandbox_approvals WHERE public_id=?", (public_id,)
            ).fetchone()
            if not row:
                raise NotFoundError("rag sandbox approval not found")
            if row["status"] != "approved":
                raise ValidationError("only an approved approval may be superseded")
            connection.execute(
                """UPDATE rag_sandbox_approvals
                SET status='superseded', updated_at=CURRENT_TIMESTAMP WHERE public_id=?""",
                (public_id,),
            )
        return self.get_approval(public_id)

    def get_approval(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._approval_select_sql() + " WHERE a.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("rag sandbox approval not found")
        return _approval_public(row)

    def get_latest_approval(self, experiment_public_id: str) -> dict[str, Any] | None:
        with self.transaction() as connection:
            experiment_id = self._experiment_id(connection, experiment_public_id)
            row = connection.execute(
                self._approval_select_sql() + " WHERE a.experiment_id=? ORDER BY a.id DESC LIMIT 1",
                (experiment_id,),
            ).fetchone()
        return _approval_public(row) if row else None

    def list_approvals(self, experiment_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            experiment_id = self._experiment_id(connection, experiment_public_id)
            rows = connection.execute(
                self._approval_select_sql() + " WHERE a.experiment_id=? ORDER BY a.id",
                (experiment_id,),
            ).fetchall()
        return [_approval_public(row) for row in rows]

    @staticmethod
    def _approval_select_sql() -> str:
        return (
            "SELECT a.*, e.public_id AS experiment_public_id, "
            "si.public_id AS sample_import_public_id, sr.public_id AS sample_report_public_id, "
            "vc.public_id AS verification_case_public_id, "
            "qs.public_id AS query_set_public_id "
            "FROM rag_sandbox_approvals a "
            "JOIN rag_sandbox_experiments e ON e.id = a.experiment_id "
            "JOIN external_dataset_sample_imports si ON si.id = a.sample_import_id "
            "JOIN external_dataset_sample_reports sr ON sr.id = a.sample_report_id "
            "JOIN external_dataset_verification_cases vc ON vc.id = a.verification_case_id "
            "LEFT JOIN rag_sandbox_query_sets qs ON qs.id = a.query_set_id"
        )

    # -- corpora ------------------------------------------------------------------------

    def create_corpus(self, experiment_public_id: str, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            experiment_id = self._experiment_id(connection, experiment_public_id)
            connection.execute(
                """INSERT INTO rag_sandbox_corpora(
                public_id, experiment_id, knowledge_space_id, sandbox_scope_key,
                created_by_admin_public_id)
                VALUES (?,?,?,?,?)""",
                (
                    public_id,
                    experiment_id,
                    values["knowledge_space_id"],
                    values["sandbox_scope_key"],
                    values["created_by_admin_public_id"],
                ),
            )
        return self.get_corpus(public_id)

    def update_corpus(self, public_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        if not fields:
            return self.get_corpus(public_id)
        with self.transaction() as connection:
            self._corpus_row(connection, public_id)
            assignments = ", ".join(f'"{key}"=?' for key in fields)
            connection.execute(
                f'UPDATE rag_sandbox_corpora SET {assignments}, '  # noqa: S608
                "updated_at=CURRENT_TIMESTAMP WHERE public_id=?",
                (*fields.values(), public_id),
            )
        return self.get_corpus(public_id)

    def get_corpus(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._corpus_select_sql() + " WHERE c.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("rag sandbox corpus not found")
        return _corpus_public(row)

    def get_corpus_for_experiment(self, experiment_public_id: str) -> dict[str, Any] | None:
        with self.transaction() as connection:
            experiment_id = self._experiment_id(connection, experiment_public_id)
            row = connection.execute(
                self._corpus_select_sql() + " WHERE c.experiment_id=?", (experiment_id,)
            ).fetchone()
        return _corpus_public(row) if row else None

    @staticmethod
    def _corpus_select_sql() -> str:
        return (
            "SELECT c.*, e.public_id AS experiment_public_id, "
            "ks.public_id AS knowledge_space_public_id "
            "FROM rag_sandbox_corpora c "
            "JOIN rag_sandbox_experiments e ON e.id = c.experiment_id "
            "JOIN rag_knowledge_spaces ks ON ks.id = c.knowledge_space_id"
        )

    # -- records (append-only) -----------------------------------------------------------

    def add_record(self, experiment_public_id: str, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            experiment_id = self._experiment_id(connection, experiment_public_id)
            corpus_id = self._corpus_row(connection, values["corpus_public_id"])["id"]
            sample_record_row = connection.execute(
                "SELECT id FROM external_dataset_sample_records WHERE public_id=?",
                (values["sample_record_public_id"],),
            ).fetchone()
            if not sample_record_row:
                raise NotFoundError("sample record not found")
            connection.execute(
                """INSERT INTO rag_sandbox_records(
                public_id, experiment_id, corpus_id, sample_record_id, selected_revision_id,
                content, content_checksum, language, task, source_file_id, source_location,
                rights_reference, conditions_json, contamination_flagged, rag_source_id,
                rag_source_version_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    experiment_id,
                    corpus_id,
                    sample_record_row["id"],
                    values.get("selected_revision_id"),
                    values["content"],
                    values["content_checksum"],
                    values.get("language"),
                    values.get("task"),
                    values.get("source_file_id"),
                    values.get("source_location", ""),
                    values.get("rights_reference", ""),
                    dumps_json(values.get("conditions", {})),
                    int(values.get("contamination_flagged", False)),
                    values.get("rag_source_id"),
                    values.get("rag_source_version_id"),
                ),
            )
        return self.get_record(public_id)

    def get_record(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._record_select_sql() + " WHERE r.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("rag sandbox record not found")
        return _record_public(row)

    def list_records(
        self, experiment_public_id: str, *, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        limit, offset = self.pagination(limit, offset)
        with self.transaction() as connection:
            experiment_id = self._experiment_id(connection, experiment_public_id)
            rows = connection.execute(
                self._record_select_sql()
                + " WHERE r.experiment_id=? ORDER BY r.id LIMIT ? OFFSET ?",
                (experiment_id, limit, offset),
            ).fetchall()
        return [_record_public(row) for row in rows]

    def count_records(self, experiment_public_id: str) -> int:
        with self.transaction() as connection:
            experiment_id = self._experiment_id(connection, experiment_public_id)
            return connection.execute(
                "SELECT COUNT(*) FROM rag_sandbox_records WHERE experiment_id=?",
                (experiment_id,),
            ).fetchone()[0]

    @staticmethod
    def _record_select_sql() -> str:
        return (
            "SELECT r.*, e.public_id AS experiment_public_id, "
            "c.public_id AS corpus_public_id, sr.public_id AS sample_record_public_id "
            "FROM rag_sandbox_records r "
            "JOIN rag_sandbox_experiments e ON e.id = r.experiment_id "
            "JOIN rag_sandbox_corpora c ON c.id = r.corpus_id "
            "JOIN external_dataset_sample_records sr ON sr.id = r.sample_record_id"
        )

    # -- indexes --------------------------------------------------------------------------

    def create_index(self, experiment_public_id: str, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            experiment_id = self._experiment_id(connection, experiment_public_id)
            corpus_id = self._corpus_row(connection, values["corpus_public_id"])["id"]
            connection.execute(
                """INSERT INTO rag_sandbox_indexes(
                public_id, experiment_id, corpus_id, index_kind, build_config_json,
                created_by_admin_public_id)
                VALUES (?,?,?,?,?,?)""",
                (
                    public_id,
                    experiment_id,
                    corpus_id,
                    values["index_kind"],
                    dumps_json(values.get("build_config", {})),
                    values["created_by_admin_public_id"],
                ),
            )
        return self.get_index(public_id)

    def update_index(self, public_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        if not fields:
            return self.get_index(public_id)
        with self.transaction() as connection:
            self._index_id(connection, public_id)
            assignments = ", ".join(f'"{key}"=?' for key in fields)
            connection.execute(
                f'UPDATE rag_sandbox_indexes SET {assignments}, '  # noqa: S608
                "updated_at=CURRENT_TIMESTAMP WHERE public_id=?",
                (*fields.values(), public_id),
            )
        return self.get_index(public_id)

    def get_index(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._index_select_sql() + " WHERE i.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("rag sandbox index not found")
        return _index_public(row)

    def list_indexes(self, experiment_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            experiment_id = self._experiment_id(connection, experiment_public_id)
            rows = connection.execute(
                self._index_select_sql() + " WHERE i.experiment_id=? ORDER BY i.id",
                (experiment_id,),
            ).fetchall()
        return [_index_public(row) for row in rows]

    @staticmethod
    def _index_select_sql() -> str:
        return (
            "SELECT i.*, e.public_id AS experiment_public_id, "
            "c.public_id AS corpus_public_id "
            "FROM rag_sandbox_indexes i "
            "JOIN rag_sandbox_experiments e ON e.id = i.experiment_id "
            "JOIN rag_sandbox_corpora c ON c.id = i.corpus_id"
        )

    # -- query sets -----------------------------------------------------------------------

    def create_query_set(self, experiment_public_id: str, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            experiment_id = self._experiment_id(connection, experiment_public_id)
            connection.execute(
                """INSERT INTO rag_sandbox_query_sets(
                public_id, experiment_id, name, created_by_admin_public_id)
                VALUES (?,?,?,?)""",
                (public_id, experiment_id, values["name"], values["created_by_admin_public_id"]),
            )
        return self.get_query_set(public_id)

    def finalize_query_set(
        self, public_id: str, *, finalized_by_admin_public_id: str
    ) -> dict[str, Any]:
        with self.transaction() as connection:
            row = self._query_set_row(connection, public_id)
            if row["status"] == "finalized":
                raise ValidationError("query set is already finalized")
            connection.execute(
                """UPDATE rag_sandbox_query_sets
                SET status='finalized', finalized_by_admin_public_id=?,
                finalized_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP
                WHERE public_id=?""",
                (finalized_by_admin_public_id, public_id),
            )
        return self.get_query_set(public_id)

    def get_query_set(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._query_set_select_sql() + " WHERE qs.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("rag sandbox query set not found")
        return _query_set_public(row)

    def list_query_sets(self, experiment_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            experiment_id = self._experiment_id(connection, experiment_public_id)
            rows = connection.execute(
                self._query_set_select_sql() + " WHERE qs.experiment_id=? ORDER BY qs.id",
                (experiment_id,),
            ).fetchall()
        return [_query_set_public(row) for row in rows]

    @staticmethod
    def _query_set_select_sql() -> str:
        return (
            "SELECT qs.*, e.public_id AS experiment_public_id "
            "FROM rag_sandbox_query_sets qs "
            "JOIN rag_sandbox_experiments e ON e.id = qs.experiment_id"
        )

    # -- queries --------------------------------------------------------------------------

    def add_query(self, query_set_public_id: str, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            query_set_row = self._query_set_row(connection, query_set_public_id)
            if query_set_row["status"] == "finalized":
                raise ValidationError("cannot add a query to a finalized query set")
            connection.execute(
                """INSERT INTO rag_sandbox_queries(
                public_id, query_set_id, query_text, language, query_type,
                expected_source_ids_json, expected_answer_notes, must_refuse_if_insufficient,
                conflict_expected, injection_test, human_authored, created_by)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    query_set_row["id"],
                    values["query_text"],
                    values.get("language", "unknown"),
                    values["query_type"],
                    dumps_json(values.get("expected_source_ids", [])),
                    values.get("expected_answer_notes", ""),
                    int(values.get("must_refuse_if_insufficient", False)),
                    int(values.get("conflict_expected", False)),
                    int(values.get("injection_test", False)),
                    int(values.get("human_authored", True)),
                    values["created_by"],
                ),
            )
            connection.execute(
                "UPDATE rag_sandbox_query_sets SET query_count = query_count + 1 WHERE id=?",
                (query_set_row["id"],),
            )
        return self.get_query(public_id)

    def review_query(self, public_id: str, *, reviewed_by_admin_public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            self._query_id(connection, public_id)
            connection.execute(
                "UPDATE rag_sandbox_queries SET reviewed_by_admin_public_id=? WHERE public_id=?",
                (reviewed_by_admin_public_id, public_id),
            )
        return self.get_query(public_id)

    def get_query(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._query_select_sql() + " WHERE q.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("rag sandbox query not found")
        return _query_public(row)

    def list_queries(self, query_set_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            query_set_id = self._query_set_row(connection, query_set_public_id)["id"]
            rows = connection.execute(
                self._query_select_sql() + " WHERE q.query_set_id=? ORDER BY q.id",
                (query_set_id,),
            ).fetchall()
        return [_query_public(row) for row in rows]

    def count_unreviewed_assistant_queries(self, query_set_public_id: str) -> int:
        with self.transaction() as connection:
            query_set_id = self._query_set_row(connection, query_set_public_id)["id"]
            return connection.execute(
                """SELECT COUNT(*) FROM rag_sandbox_queries
                WHERE query_set_id=? AND human_authored=0
                AND reviewed_by_admin_public_id IS NULL""",
                (query_set_id,),
            ).fetchone()[0]

    @staticmethod
    def _query_select_sql() -> str:
        return (
            "SELECT q.*, qs.public_id AS query_set_public_id "
            "FROM rag_sandbox_queries q "
            "JOIN rag_sandbox_query_sets qs ON qs.id = q.query_set_id"
        )

    # -- retrieval runs/results (append-only) ---------------------------------------------

    def record_retrieval_run(
        self, experiment_public_id: str, values: dict[str, Any]
    ) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            experiment_id = self._experiment_id(connection, experiment_public_id)
            index_id = self._index_id(connection, values["index_public_id"])
            query_set_id = self._query_set_row(connection, values["query_set_public_id"])["id"]
            connection.execute(
                """INSERT INTO rag_sandbox_retrieval_runs(
                public_id, experiment_id, index_id, query_set_id, config_label, total_queries,
                status, performed_by_admin_public_id, started_at, completed_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    experiment_id,
                    index_id,
                    query_set_id,
                    values.get("config_label", ""),
                    values.get("total_queries", 0),
                    values.get("status", "completed"),
                    values["performed_by_admin_public_id"],
                    values.get("started_at"),
                    values.get("completed_at"),
                ),
            )
        return self.get_retrieval_run(public_id)

    def get_retrieval_run(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._retrieval_run_select_sql() + " WHERE rr.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("rag sandbox retrieval run not found")
        return _retrieval_run_public(row)

    def list_retrieval_runs(self, experiment_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            experiment_id = self._experiment_id(connection, experiment_public_id)
            rows = connection.execute(
                self._retrieval_run_select_sql() + " WHERE rr.experiment_id=? ORDER BY rr.id",
                (experiment_id,),
            ).fetchall()
        return [_retrieval_run_public(row) for row in rows]

    @staticmethod
    def _retrieval_run_select_sql() -> str:
        return (
            "SELECT rr.*, e.public_id AS experiment_public_id, "
            "i.public_id AS index_public_id, qs.public_id AS query_set_public_id "
            "FROM rag_sandbox_retrieval_runs rr "
            "JOIN rag_sandbox_experiments e ON e.id = rr.experiment_id "
            "JOIN rag_sandbox_indexes i ON i.id = rr.index_id "
            "JOIN rag_sandbox_query_sets qs ON qs.id = rr.query_set_id"
        )

    def add_retrieval_result(
        self, retrieval_run_public_id: str, values: dict[str, Any]
    ) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            retrieval_run_id = self._retrieval_run_id(connection, retrieval_run_public_id)
            query_id = self._query_id(connection, values["query_public_id"])
            connection.execute(
                """INSERT INTO rag_sandbox_retrieval_results(
                public_id, retrieval_run_id, query_id, rag_retrieval_run_id,
                metric_availability, expected_source_hit, source_rank, recall_at_k,
                precision_at_k, reciprocal_rank, language_match, duplicate_result_rate,
                conflicting_source_retrieved, insufficient_evidence_behavior,
                latency_milliseconds, result_count)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    retrieval_run_id,
                    query_id,
                    values.get("rag_retrieval_run_id"),
                    values.get("metric_availability", "not_available"),
                    values.get("expected_source_hit"),
                    values.get("source_rank"),
                    values.get("recall_at_k"),
                    values.get("precision_at_k"),
                    values.get("reciprocal_rank"),
                    values.get("language_match"),
                    values.get("duplicate_result_rate"),
                    int(values.get("conflicting_source_retrieved", False)),
                    values.get("insufficient_evidence_behavior"),
                    values.get("latency_milliseconds"),
                    values.get("result_count", 0),
                ),
            )
        return self.get_retrieval_result(public_id)

    def get_retrieval_result(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._retrieval_result_select_sql() + " WHERE res.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("rag sandbox retrieval result not found")
        return _retrieval_result_public(row)

    def list_retrieval_results(self, retrieval_run_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            retrieval_run_id = self._retrieval_run_id(connection, retrieval_run_public_id)
            rows = connection.execute(
                self._retrieval_result_select_sql()
                + " WHERE res.retrieval_run_id=? ORDER BY res.id",
                (retrieval_run_id,),
            ).fetchall()
        return [_retrieval_result_public(row) for row in rows]

    @staticmethod
    def _retrieval_result_select_sql() -> str:
        return (
            "SELECT res.*, rr.public_id AS retrieval_run_public_id, "
            "q.public_id AS query_public_id "
            "FROM rag_sandbox_retrieval_results res "
            "JOIN rag_sandbox_retrieval_runs rr ON rr.id = res.retrieval_run_id "
            "JOIN rag_sandbox_queries q ON q.id = res.query_id"
        )

    # -- answer runs (append-only) -----------------------------------------------------------

    def add_answer_run(self, experiment_public_id: str, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            experiment_id = self._experiment_id(connection, experiment_public_id)
            retrieval_result_id = self._retrieval_result_id(
                connection, values["retrieval_result_public_id"]
            )
            query_id = self._query_id(connection, values["query_public_id"])
            connection.execute(
                """INSERT INTO rag_sandbox_answer_runs(
                public_id, experiment_id, retrieval_result_id, query_id,
                rag_grounded_request_id, generation_assignment_key, prompt_version,
                answer_text, answer_checksum, answer_language, used_source_ids_json,
                citation_count, unsupported_claim_count, insufficient_evidence_detected,
                conflict_detected, refusal_used, latency_milliseconds, token_usage_json,
                status, performed_by_admin_public_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    experiment_id,
                    retrieval_result_id,
                    query_id,
                    values.get("rag_grounded_request_id"),
                    values.get("generation_assignment_key"),
                    values.get("prompt_version", "v1"),
                    values.get("answer_text", ""),
                    values.get("answer_checksum"),
                    values.get("answer_language", "unknown"),
                    dumps_json(values.get("used_source_ids", [])),
                    values.get("citation_count", 0),
                    values.get("unsupported_claim_count", 0),
                    int(values.get("insufficient_evidence_detected", False)),
                    int(values.get("conflict_detected", False)),
                    int(values.get("refusal_used", False)),
                    values.get("latency_milliseconds"),
                    dumps_json(values.get("token_usage", {})),
                    values["status"],
                    values["performed_by_admin_public_id"],
                ),
            )
        return self.get_answer_run(public_id)

    def get_answer_run(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._answer_run_select_sql() + " WHERE ar.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("rag sandbox answer run not found")
        return _answer_run_public(row)

    def list_answer_runs(self, experiment_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            experiment_id = self._experiment_id(connection, experiment_public_id)
            rows = connection.execute(
                self._answer_run_select_sql() + " WHERE ar.experiment_id=? ORDER BY ar.id",
                (experiment_id,),
            ).fetchall()
        return [_answer_run_public(row) for row in rows]

    @staticmethod
    def _answer_run_select_sql() -> str:
        return (
            "SELECT ar.*, e.public_id AS experiment_public_id, "
            "res.public_id AS retrieval_result_public_id, q.public_id AS query_public_id "
            "FROM rag_sandbox_answer_runs ar "
            "JOIN rag_sandbox_experiments e ON e.id = ar.experiment_id "
            "JOIN rag_sandbox_retrieval_results res ON res.id = ar.retrieval_result_id "
            "JOIN rag_sandbox_queries q ON q.id = ar.query_id"
        )

    # -- citations (append-only) -------------------------------------------------------------

    def add_citation(self, answer_run_public_id: str, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            answer_run_id = self._answer_run_id(connection, answer_run_public_id)
            connection.execute(
                """INSERT INTO rag_sandbox_citations(
                public_id, answer_run_id, citation_label, rag_citation_id,
                references_retrieved_source, source_exists, checksum_matches,
                supports_nearby_claim, is_duplicate, is_orphan, validation_status, reason)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    answer_run_id,
                    values["citation_label"],
                    values.get("rag_citation_id"),
                    int(values.get("references_retrieved_source", False)),
                    int(values.get("source_exists", False)),
                    values.get("checksum_matches"),
                    values.get("supports_nearby_claim"),
                    int(values.get("is_duplicate", False)),
                    int(values.get("is_orphan", False)),
                    values["validation_status"],
                    values.get("reason", ""),
                ),
            )
        return self.get_citation(public_id)

    def get_citation(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._citation_select_sql() + " WHERE ci.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("rag sandbox citation not found")
        return _citation_public(row)

    def list_citations(self, answer_run_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            answer_run_id = self._answer_run_id(connection, answer_run_public_id)
            rows = connection.execute(
                self._citation_select_sql() + " WHERE ci.answer_run_id=? ORDER BY ci.id",
                (answer_run_id,),
            ).fetchall()
        return [_citation_public(row) for row in rows]

    def list_citations_for_experiment(self, experiment_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            experiment_id = self._experiment_id(connection, experiment_public_id)
            rows = connection.execute(
                self._citation_select_sql()
                + " JOIN rag_sandbox_answer_runs ar2 ON ar2.id = ci.answer_run_id "
                "WHERE ar2.experiment_id=? ORDER BY ci.id",
                (experiment_id,),
            ).fetchall()
        return [_citation_public(row) for row in rows]

    @staticmethod
    def _citation_select_sql() -> str:
        return (
            "SELECT ci.*, ar.public_id AS answer_run_public_id "
            "FROM rag_sandbox_citations ci "
            "JOIN rag_sandbox_answer_runs ar ON ar.id = ci.answer_run_id"
        )

    # -- evaluations (append-only) -----------------------------------------------------------

    def add_evaluation(self, experiment_public_id: str, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            experiment_id = self._experiment_id(connection, experiment_public_id)
            answer_run_id = None
            if values.get("answer_run_public_id"):
                answer_run_id = self._answer_run_id(connection, values["answer_run_public_id"])
            query_id = None
            if values.get("query_public_id"):
                query_id = self._query_id(connection, values["query_public_id"])
            connection.execute(
                """INSERT INTO rag_sandbox_evaluations(
                public_id, experiment_id, answer_run_id, query_id, evaluation_type,
                result_status, automated, score, details_json, evaluation_version)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    experiment_id,
                    answer_run_id,
                    query_id,
                    values["evaluation_type"],
                    values["result_status"],
                    int(values.get("automated", True)),
                    values.get("score"),
                    dumps_json(values.get("details", {})),
                    values.get("evaluation_version", "v1"),
                ),
            )
        return self.get_evaluation(public_id)

    def get_evaluation(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._evaluation_select_sql() + " WHERE ev.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("rag sandbox evaluation not found")
        return _evaluation_public(row)

    def list_evaluations(
        self, experiment_public_id: str, *, evaluation_type: str | None = None
    ) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            experiment_id = self._experiment_id(connection, experiment_public_id)
            clause = " AND ev.evaluation_type=?" if evaluation_type else ""
            params: tuple[Any, ...] = (
                (experiment_id, evaluation_type) if evaluation_type else (experiment_id,)
            )
            rows = connection.execute(
                self._evaluation_select_sql()
                + f" WHERE ev.experiment_id=?{clause} ORDER BY ev.id",  # noqa: S608
                params,
            ).fetchall()
        return [_evaluation_public(row) for row in rows]

    @staticmethod
    def _evaluation_select_sql() -> str:
        return (
            "SELECT ev.*, e.public_id AS experiment_public_id, "
            "ar.public_id AS answer_run_public_id, q.public_id AS query_public_id "
            "FROM rag_sandbox_evaluations ev "
            "JOIN rag_sandbox_experiments e ON e.id = ev.experiment_id "
            "LEFT JOIN rag_sandbox_answer_runs ar ON ar.id = ev.answer_run_id "
            "LEFT JOIN rag_sandbox_queries q ON q.id = ev.query_id"
        )

    # -- human reviews (append-only) ---------------------------------------------------------

    def add_human_review(
        self, experiment_public_id: str, values: dict[str, Any]
    ) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            experiment_id = self._experiment_id(connection, experiment_public_id)
            query_id = self._query_id(connection, values["query_public_id"])
            answer_run_id = None
            if values.get("answer_run_public_id"):
                answer_run_id = self._answer_run_id(connection, values["answer_run_public_id"])
            connection.execute(
                """INSERT INTO rag_sandbox_human_reviews(
                public_id, experiment_id, query_id, answer_run_id, retrieval_relevant,
                answer_grounded, citations_correct, language_appropriate, refusal_correct,
                conflict_handled, injection_resisted, decision, notes, reviewer_admin_public_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    experiment_id,
                    query_id,
                    answer_run_id,
                    values.get("retrieval_relevant"),
                    values.get("answer_grounded"),
                    values.get("citations_correct"),
                    values.get("language_appropriate"),
                    values.get("refusal_correct"),
                    values.get("conflict_handled"),
                    values.get("injection_resisted"),
                    values["decision"],
                    values.get("notes", ""),
                    values["reviewer_admin_public_id"],
                ),
            )
        return self.get_human_review(public_id)

    def get_human_review(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._human_review_select_sql() + " WHERE hr.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("rag sandbox human review not found")
        return _human_review_public(row)

    def list_human_reviews(self, experiment_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            experiment_id = self._experiment_id(connection, experiment_public_id)
            rows = connection.execute(
                self._human_review_select_sql() + " WHERE hr.experiment_id=? ORDER BY hr.id",
                (experiment_id,),
            ).fetchall()
        return [_human_review_public(row) for row in rows]

    def get_latest_human_review_for_query(self, query_public_id: str) -> dict[str, Any] | None:
        with self.transaction() as connection:
            query_id = self._query_id(connection, query_public_id)
            row = connection.execute(
                self._human_review_select_sql()
                + " WHERE hr.query_id=? ORDER BY hr.id DESC LIMIT 1",
                (query_id,),
            ).fetchone()
        return _human_review_public(row) if row else None

    @staticmethod
    def _human_review_select_sql() -> str:
        return (
            "SELECT hr.*, e.public_id AS experiment_public_id, "
            "q.public_id AS query_public_id, ar.public_id AS answer_run_public_id "
            "FROM rag_sandbox_human_reviews hr "
            "JOIN rag_sandbox_experiments e ON e.id = hr.experiment_id "
            "JOIN rag_sandbox_queries q ON q.id = hr.query_id "
            "LEFT JOIN rag_sandbox_answer_runs ar ON ar.id = hr.answer_run_id"
        )

    # -- reports (append-only, versioned) -----------------------------------------------------

    def add_report(self, experiment_public_id: str, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            experiment_id = self._experiment_id(connection, experiment_public_id)
            next_version = (
                connection.execute(
                    "SELECT COALESCE(MAX(report_version), 0) + 1 FROM rag_sandbox_reports "
                    "WHERE experiment_id=?",
                    (experiment_id,),
                ).fetchone()[0]
            )
            connection.execute(
                """INSERT INTO rag_sandbox_reports(
                public_id, experiment_id, report_version, report_json, report_checksum_sha256,
                production_rag_readiness, training_data_observation, recommended_next_action,
                finalized_by_admin_public_id)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    experiment_id,
                    next_version,
                    dumps_json(values["report"]),
                    values["report_checksum_sha256"],
                    values["production_rag_readiness"],
                    values["training_data_observation"],
                    values.get("recommended_next_action", ""),
                    values["finalized_by_admin_public_id"],
                ),
            )
        return self.get_report(public_id)

    def get_report(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._report_select_sql() + " WHERE r.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("rag sandbox report not found")
        return _report_public(row)

    def get_latest_report(self, experiment_public_id: str) -> dict[str, Any] | None:
        with self.transaction() as connection:
            experiment_id = self._experiment_id(connection, experiment_public_id)
            row = connection.execute(
                self._report_select_sql()
                + " WHERE r.experiment_id=? ORDER BY r.report_version DESC LIMIT 1",
                (experiment_id,),
            ).fetchone()
        return _report_public(row) if row else None

    def list_reports(self, experiment_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            experiment_id = self._experiment_id(connection, experiment_public_id)
            rows = connection.execute(
                self._report_select_sql() + " WHERE r.experiment_id=? ORDER BY r.report_version",
                (experiment_id,),
            ).fetchall()
        return [_report_public(row) for row in rows]

    @staticmethod
    def _report_select_sql() -> str:
        return (
            "SELECT r.*, e.public_id AS experiment_public_id "
            "FROM rag_sandbox_reports r "
            "JOIN rag_sandbox_experiments e ON e.id = r.experiment_id"
        )

    # -- acceptances (append-only) -------------------------------------------------------------

    def add_acceptance(self, experiment_public_id: str, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            experiment_id = self._experiment_id(connection, experiment_public_id)
            report_id = self._report_row(connection, values["report_public_id"])["id"]
            connection.execute(
                """INSERT INTO rag_sandbox_acceptances(
                public_id, experiment_id, report_id, decision, reason, conditions_json,
                reviewer_admin_public_id, report_checksum_sha256, target_fingerprint)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    experiment_id,
                    report_id,
                    values["decision"],
                    values["reason"],
                    dumps_json(values.get("conditions", {})),
                    values["reviewer_admin_public_id"],
                    values["report_checksum_sha256"],
                    values["target_fingerprint"],
                ),
            )
        return self.get_acceptance(public_id)

    def get_acceptance(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._acceptance_select_sql() + " WHERE ac.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("rag sandbox acceptance not found")
        return _acceptance_public(row)

    def get_latest_acceptance(self, experiment_public_id: str) -> dict[str, Any] | None:
        with self.transaction() as connection:
            experiment_id = self._experiment_id(connection, experiment_public_id)
            row = connection.execute(
                self._acceptance_select_sql()
                + " WHERE ac.experiment_id=? ORDER BY ac.id DESC LIMIT 1",
                (experiment_id,),
            ).fetchone()
        return _acceptance_public(row) if row else None

    def list_acceptances(self, experiment_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            experiment_id = self._experiment_id(connection, experiment_public_id)
            rows = connection.execute(
                self._acceptance_select_sql() + " WHERE ac.experiment_id=? ORDER BY ac.id",
                (experiment_id,),
            ).fetchall()
        return [_acceptance_public(row) for row in rows]

    @staticmethod
    def _acceptance_select_sql() -> str:
        return (
            "SELECT ac.*, e.public_id AS experiment_public_id, "
            "r.public_id AS report_public_id "
            "FROM rag_sandbox_acceptances ac "
            "JOIN rag_sandbox_experiments e ON e.id = ac.experiment_id "
            "JOIN rag_sandbox_reports r ON r.id = ac.report_id"
        )

    # -- events (append-only) -------------------------------------------------------------------

    def record_event(self, experiment_public_id: str, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            experiment_id = self._experiment_id(connection, experiment_public_id)
            connection.execute(
                """INSERT INTO rag_sandbox_events(
                public_id, experiment_id, event_type, from_status, to_status, summary,
                metadata_json, performed_by_admin_public_id)
                VALUES (?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    experiment_id,
                    values["event_type"],
                    values.get("from_status"),
                    values.get("to_status"),
                    values.get("summary", ""),
                    dumps_json(values.get("metadata", {})),
                    values.get("performed_by_admin_public_id", "system"),
                ),
            )
        return self.get_event(public_id)

    def get_event(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._event_select_sql() + " WHERE ev.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("rag sandbox event not found")
        return _event_public(row)

    def list_events(
        self, experiment_public_id: str, *, limit: int = 100, offset: int = 0
    ) -> list[dict[str, Any]]:
        limit, offset = self.pagination(limit, offset)
        with self.transaction() as connection:
            experiment_id = self._experiment_id(connection, experiment_public_id)
            rows = connection.execute(
                self._event_select_sql()
                + " WHERE ev.experiment_id=? ORDER BY ev.id DESC LIMIT ? OFFSET ?",
                (experiment_id, limit, offset),
            ).fetchall()
        return [_event_public(row) for row in rows]

    @staticmethod
    def _event_select_sql() -> str:
        return (
            "SELECT ev.*, e.public_id AS experiment_public_id "
            "FROM rag_sandbox_events ev "
            "JOIN rag_sandbox_experiments e ON e.id = ev.experiment_id"
        )

    # -- deletion requests (append-only per transition) ------------------------------------------

    def request_deletion(self, experiment_public_id: str, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        code = f"RSD-{uuid4()}"
        with self.transaction() as connection:
            experiment_id = self._experiment_id(connection, experiment_public_id)
            connection.execute(
                """INSERT INTO rag_sandbox_deletion_requests(
                public_id, deletion_request_code, experiment_id, status,
                impact_preview_json, reason, requested_by_admin_public_id)
                VALUES (?,?,?,?,?,?,?)""",
                (
                    public_id,
                    code,
                    experiment_id,
                    "requested",
                    dumps_json(values.get("impact_preview", {})),
                    values["reason"],
                    values["requested_by_admin_public_id"],
                ),
            )
        return self.get_deletion_request(public_id)

    # Each transition status writes its own timestamp column; the fragment
    # below only ever selects among these 3 fixed, hardcoded-by-us column
    # names -- never built from caller input, so there is no injection
    # surface (mirrors Phase 12's identical pattern).
    _DELETION_TIMESTAMP_COLUMN = {
        "confirmed": "confirmed_at",
        "executed": "executed_at",
        "cancelled": "cancelled_at",
    }

    def _append_deletion_transition(
        self, deletion_request_code: str, *, status: str, confirmed_by_admin_public_id: str | None
    ) -> dict[str, Any]:
        timestamp_column = self._DELETION_TIMESTAMP_COLUMN[status]
        with self.transaction() as connection:
            latest = connection.execute(
                """SELECT experiment_id, impact_preview_json, reason, requested_by_admin_public_id
                FROM rag_sandbox_deletion_requests
                WHERE deletion_request_code=? ORDER BY id DESC LIMIT 1""",
                (deletion_request_code,),
            ).fetchone()
            if not latest:
                raise NotFoundError("rag sandbox deletion request not found")
            public_id = str(uuid4())
            connection.execute(
                f"""INSERT INTO rag_sandbox_deletion_requests(
                public_id, deletion_request_code, experiment_id, status,
                impact_preview_json, reason, requested_by_admin_public_id,
                confirmed_by_admin_public_id, {timestamp_column})
                VALUES (?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)""",
                (
                    public_id,
                    deletion_request_code,
                    latest["experiment_id"],
                    status,
                    latest["impact_preview_json"],
                    latest["reason"],
                    latest["requested_by_admin_public_id"],
                    confirmed_by_admin_public_id,
                ),
            )
        return self.get_deletion_request(public_id)

    def confirm_deletion(
        self, deletion_request_code: str, *, confirmed_by_admin_public_id: str
    ) -> dict[str, Any]:
        return self._append_deletion_transition(
            deletion_request_code,
            status="confirmed",
            confirmed_by_admin_public_id=confirmed_by_admin_public_id,
        )

    def execute_deletion(self, deletion_request_code: str) -> dict[str, Any]:
        return self._append_deletion_transition(
            deletion_request_code, status="executed", confirmed_by_admin_public_id=None
        )

    def cancel_deletion(self, deletion_request_code: str) -> dict[str, Any]:
        return self._append_deletion_transition(
            deletion_request_code, status="cancelled", confirmed_by_admin_public_id=None
        )

    def get_deletion_request(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._deletion_request_select_sql() + " WHERE d.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("rag sandbox deletion request not found")
        return _deletion_request_public(row)

    def get_latest_deletion_request_by_code(
        self, deletion_request_code: str
    ) -> dict[str, Any] | None:
        with self.transaction() as connection:
            row = connection.execute(
                self._deletion_request_select_sql()
                + " WHERE d.deletion_request_code=? ORDER BY d.id DESC LIMIT 1",
                (deletion_request_code,),
            ).fetchone()
        return _deletion_request_public(row) if row else None

    def get_latest_deletion_request(self, experiment_public_id: str) -> dict[str, Any] | None:
        with self.transaction() as connection:
            experiment_id = self._experiment_id(connection, experiment_public_id)
            row = connection.execute(
                self._deletion_request_select_sql()
                + " WHERE d.experiment_id=? ORDER BY d.id DESC LIMIT 1",
                (experiment_id,),
            ).fetchone()
        return _deletion_request_public(row) if row else None

    def list_deletion_requests(self, experiment_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            experiment_id = self._experiment_id(connection, experiment_public_id)
            rows = connection.execute(
                self._deletion_request_select_sql() + " WHERE d.experiment_id=? ORDER BY d.id",
                (experiment_id,),
            ).fetchall()
        return [_deletion_request_public(row) for row in rows]

    @staticmethod
    def _deletion_request_select_sql() -> str:
        return (
            "SELECT d.*, e.public_id AS experiment_public_id "
            "FROM rag_sandbox_deletion_requests d "
            "JOIN rag_sandbox_experiments e ON e.id = d.experiment_id"
        )
