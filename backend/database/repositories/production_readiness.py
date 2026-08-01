"""Phase 15 (this conversation's numbering) Text/NLP Final Production
Readiness repository. Mirrors `TrainingIncrementalRepository`'s exact
shape: one `_x_public(row)` formatter per table, `create_x`/`get_x`/
`list_x`/`update_x` method groups, `BaseRepository.transaction()`/
`.pagination()` reused verbatim. See
docs/production/phase15_text_nlp_production_readiness_plan.md.
"""

from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError, ValidationError


def _rag_promotion_request_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "promotion_code": row["promotion_code"],
        "rag_sandbox_experiment_public_id": row["experiment_public_id"],
        "rag_sandbox_report_public_id": row["report_public_id"],
        "knowledge_space_public_id": row["knowledge_space_public_id"],
        "selected_record_ids": loads_json(row["selected_record_ids_json"]),
        "selected_record_checksum_set_hash": row["selected_record_checksum_set_hash"],
        "chunking_configuration": loads_json(row["chunking_configuration_json"]),
        "embedding_assignment_key": row["embedding_assignment_key"],
        "retrieval_configuration": loads_json(row["retrieval_configuration_json"]),
        "generation_assignment_key": row["generation_assignment_key"],
        "citation_policy_version": row["citation_policy_version"],
        "grounding_policy_version": row["grounding_policy_version"],
        "injection_policy_version": row["injection_policy_version"],
        "commercial_use_context": row["commercial_use_context"],
        "resource_preview": loads_json(row["resource_preview_json"]),
        "target_fingerprint": row["target_fingerprint"],
        "status": row["status"],
        "requested_by_admin_public_id": row["requested_by_admin_public_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _rag_promotion_approval_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "promotion_request_public_id": row["promotion_request_public_id"],
        "status": row["status"],
        "approved_by_admin_id": row["approved_by_admin_id"],
        "approved_at": row["approved_at"],
        "expires_at": row["expires_at"],
        "conditions": loads_json(row["conditions_json"]),
        "target_fingerprint": row["target_fingerprint"],
        "requested_by_admin_public_id": row["requested_by_admin_public_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _rag_release_candidate_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "promotion_request_public_id": row["promotion_request_public_id"],
        "knowledge_source_public_id": row["knowledge_source_public_id"],
        "retrieval_profile_public_id": row["retrieval_profile_public_id"],
        "record_checksum_set_hash": row["record_checksum_set_hash"],
        "chunk_checksum_set_hash": row["chunk_checksum_set_hash"],
        "embedding_model_reference": row["embedding_model_reference"],
        "index_checksum_sha256": row["index_checksum_sha256"],
        "configuration_manifest": loads_json(row["configuration_manifest_json"]),
        "build_log": loads_json(row["build_log_json"]),
        "resource_usage": loads_json(row["resource_usage_json"]),
        "status": row["status"],
        "production_visible": bool(row["production_visible"]),
        "created_by_admin_public_id": row["created_by_admin_public_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _rag_validation_result_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "rag_release_candidate_public_id": row["rag_release_candidate_public_id"],
        "validation_type": row["validation_type"],
        "result_status": row["result_status"],
        "metrics": loads_json(row["metrics_json"]),
        "details": loads_json(row["details_json"]),
        "created_by_admin_public_id": row["created_by_admin_public_id"],
        "created_at": row["created_at"],
    }


def _rag_activation_event_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "rag_release_candidate_public_id": row["rag_release_candidate_public_id"],
        "event_type": row["event_type"],
        "previous_active_profile_public_id": row["previous_active_profile_public_id"],
        "summary": row["summary"],
        "metadata": loads_json(row["metadata_json"]),
        "performed_by_admin_public_id": row["performed_by_admin_public_id"],
        "created_at": row["created_at"],
    }


def _model_release_request_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "request_code": row["request_code"],
        "model_candidate_public_id": row["model_candidate_public_id"],
        "incremental_training_checkpoint_public_id": row["checkpoint_public_id"],
        "model_release_candidate_public_id": row["model_release_candidate_public_id"],
        "release_type": row["release_type"],
        "target_assignment_keys": loads_json(row["target_assignment_keys_json"]),
        "canary_requested": bool(row["canary_requested"]),
        "canary_percentage_or_scope": row["canary_percentage_or_scope"],
        "resource_preview": loads_json(row["resource_preview_json"]),
        "security_check_version": row["security_check_version"],
        "evaluation_policy_version": row["evaluation_policy_version"],
        "target_fingerprint": row["target_fingerprint"],
        "status": row["status"],
        "requested_by_admin_public_id": row["requested_by_admin_public_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _model_release_approval_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "release_request_public_id": row["release_request_public_id"],
        "checkpoint_checksum": row["checkpoint_checksum"],
        "tokenizer_checksum": row["tokenizer_checksum"],
        "config_checksum": row["config_checksum"],
        "manifest_checksum": row["manifest_checksum"],
        "evaluation_report_checksum": row["evaluation_report_checksum"],
        "training_report_checksum": row["training_report_checksum"],
        "security_report_checksum": row["security_report_checksum"],
        "target_assignment_keys": loads_json(row["target_assignment_keys_json"]),
        "canary_configuration": loads_json(row["canary_configuration_json"]),
        "status": row["status"],
        "approved_by_admin_id": row["approved_by_admin_id"],
        "approved_at": row["approved_at"],
        "expires_at": row["expires_at"],
        "conditions": loads_json(row["conditions_json"]),
        "target_fingerprint": row["target_fingerprint"],
        "requested_by_admin_public_id": row["requested_by_admin_public_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _model_activation_event_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "release_request_public_id": row["release_request_public_id"],
        "release_approval_public_id": row["release_approval_public_id"],
        "inference_model_assignment_public_id": row["inference_model_assignment_public_id"],
        "event_type": row["event_type"],
        "previous_assignment_snapshot": loads_json(row["previous_assignment_snapshot_json"]),
        "summary": row["summary"],
        "metadata": loads_json(row["metadata_json"]),
        "performed_by_admin_public_id": row["performed_by_admin_public_id"],
        "created_at": row["created_at"],
    }


def _model_post_activation_check_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "release_request_public_id": row["release_request_public_id"],
        "check_type": row["check_type"],
        "result_status": row["result_status"],
        "metrics": loads_json(row["metrics_json"]),
        "details": loads_json(row["details_json"]),
        "created_by_admin_public_id": row["created_by_admin_public_id"],
        "created_at": row["created_at"],
    }


def _rollback_plan_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "target_type": row["target_type"],
        "current_active_version": row["current_active_version"],
        "candidate_version": row["candidate_version"],
        "previous_assignment_snapshot": loads_json(row["previous_assignment_snapshot_json"]),
        "previous_rag_state_snapshot": loads_json(row["previous_rag_state_snapshot_json"]),
        "backup_reference": row["backup_reference"],
        "rollback_steps": loads_json(row["rollback_steps_json"]),
        "validation_steps": loads_json(row["validation_steps_json"]),
        "maximum_recovery_time_target_seconds": row["maximum_recovery_time_target_seconds"],
        "status": row["status"],
        "created_by_admin_public_id": row["created_by_admin_public_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _rollback_event_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "rollback_plan_public_id": row["rollback_plan_public_id"],
        "event_type": row["event_type"],
        "summary": row["summary"],
        "metadata": loads_json(row["metadata_json"]),
        "performed_by_admin_public_id": row["performed_by_admin_public_id"],
        "created_at": row["created_at"],
    }


def _artifact_security_check_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "artifact_type": row["artifact_type"],
        "artifact_reference": row["artifact_reference"],
        "result_status": row["result_status"],
        "checks": loads_json(row["checks_json"]),
        "findings": loads_json(row["findings_json"]),
        "created_by_admin_public_id": row["created_by_admin_public_id"],
        "created_at": row["created_at"],
    }


def _backup_readiness_check_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "check_type": row["check_type"],
        "result_status": row["result_status"],
        "latest_backup_filename": row["latest_backup_filename"],
        "latest_backup_age_seconds": row["latest_backup_age_seconds"],
        "details": loads_json(row["details_json"]),
        "created_by_admin_public_id": row["created_by_admin_public_id"],
        "created_at": row["created_at"],
    }


def _deployment_readiness_check_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "result_status": row["result_status"],
        "checks": loads_json(row["checks_json"]),
        "blocking_reasons": loads_json(row["blocking_reasons_json"]),
        "created_by_admin_public_id": row["created_by_admin_public_id"],
        "created_at": row["created_at"],
    }


def _regression_run_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "run_code": row["run_code"],
        "status": row["status"],
        "batch_plan": loads_json(row["batch_plan_json"]),
        "created_by_admin_public_id": row["created_by_admin_public_id"],
        "created_at": row["created_at"],
        "finalized_at": row["finalized_at"],
    }


def _regression_result_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "regression_run_public_id": row["regression_run_public_id"],
        "batch_name": row["batch_name"],
        "command": row["command"],
        "status": row["status"],
        "passed_count": row["passed_count"],
        "failed_count": row["failed_count"],
        "error_count": row["error_count"],
        "duration_seconds": row["duration_seconds"],
        "raw_summary": row["raw_summary"],
        "created_at": row["created_at"],
    }


def _readiness_report_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "report_version": row["report_version"],
        "report": loads_json(row["report_json"]),
        "report_checksum_sha256": row["report_checksum_sha256"],
        "recommendation": row["recommendation"],
        "finalized_by_admin_public_id": row["finalized_by_admin_public_id"],
        "finalized_at": row["finalized_at"],
        "created_at": row["created_at"],
    }


def _acceptance_review_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "production_readiness_report_public_id": row["report_public_id"],
        "decision": row["decision"],
        "reason": row["reason"],
        "conditions": loads_json(row["conditions_json"]),
        "reviewer_admin_public_id": row["reviewer_admin_public_id"],
        "reviewed_at": row["reviewed_at"],
        "report_checksum": row["report_checksum"],
        "active_model_checksum": row["active_model_checksum"],
        "active_rag_checksum": row["active_rag_checksum"],
        "target_fingerprint": row["target_fingerprint"],
        "created_at": row["created_at"],
    }


def _readiness_event_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "event_type": row["event_type"],
        "resource_type": row["resource_type"],
        "resource_public_id": row["resource_public_id"],
        "summary": row["summary"],
        "metadata": loads_json(row["metadata_json"]),
        "performed_by_admin_public_id": row["performed_by_admin_public_id"],
        "created_at": row["created_at"],
    }


class ProductionReadinessRepository(BaseRepository):
    # -- internal id-lookup helpers -------------------------------------------------

    def _rag_promotion_request_id(self, connection: sqlite3.Connection, public_id: str) -> int:
        row = connection.execute(
            "SELECT id FROM production_rag_promotion_requests WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("production RAG promotion request not found")
        return row["id"]

    def _rag_release_candidate_row(
        self, connection: sqlite3.Connection, public_id: str
    ) -> sqlite3.Row:
        row = connection.execute(
            self._rag_release_candidate_select_sql() + " WHERE c.public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("production RAG release candidate not found")
        return row

    def _model_release_request_id(self, connection: sqlite3.Connection, public_id: str) -> int:
        row = connection.execute(
            "SELECT id FROM production_model_release_requests WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("production model release request not found")
        return row["id"]

    def _rollback_plan_id(self, connection: sqlite3.Connection, public_id: str) -> int:
        row = connection.execute(
            "SELECT id FROM production_rollback_plans WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("production rollback plan not found")
        return row["id"]

    def _regression_run_id(self, connection: sqlite3.Connection, public_id: str) -> int:
        row = connection.execute(
            "SELECT id FROM production_regression_runs WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("production regression run not found")
        return row["id"]

    def _readiness_report_id(self, connection: sqlite3.Connection, public_id: str) -> int:
        row = connection.execute(
            "SELECT id FROM production_readiness_reports WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("production readiness report not found")
        return row["id"]

    # -- RAG promotion requests --------------------------------------------------------

    def create_rag_promotion_request(self, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            experiment_id = connection.execute(
                "SELECT id FROM rag_sandbox_experiments WHERE public_id=?",
                (values["rag_sandbox_experiment_public_id"],),
            ).fetchone()
            if not experiment_id:
                raise NotFoundError("rag sandbox experiment not found")
            report_id = connection.execute(
                "SELECT id FROM rag_sandbox_reports WHERE public_id=?",
                (values["rag_sandbox_report_public_id"],),
            ).fetchone()
            if not report_id:
                raise NotFoundError("rag sandbox report not found")
            space_row = connection.execute(
                "SELECT id FROM rag_knowledge_spaces WHERE public_id=?",
                (values["knowledge_space_public_id"],),
            ).fetchone()
            if not space_row:
                raise NotFoundError("rag knowledge space not found")
            connection.execute(
                """INSERT INTO production_rag_promotion_requests(
                public_id, promotion_code, rag_sandbox_experiment_id, rag_sandbox_report_id,
                knowledge_space_id, selected_record_ids_json, selected_record_checksum_set_hash,
                chunking_configuration_json, embedding_assignment_key,
                retrieval_configuration_json, generation_assignment_key, citation_policy_version,
                grounding_policy_version, injection_policy_version, commercial_use_context,
                resource_preview_json, target_fingerprint, requested_by_admin_public_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    values["promotion_code"],
                    experiment_id["id"],
                    report_id["id"],
                    space_row["id"],
                    dumps_json(values.get("selected_record_ids", [])),
                    values["selected_record_checksum_set_hash"],
                    dumps_json(values.get("chunking_configuration", {})),
                    values.get("embedding_assignment_key"),
                    dumps_json(values.get("retrieval_configuration", {})),
                    values.get("generation_assignment_key"),
                    values.get("citation_policy_version", "v1"),
                    values.get("grounding_policy_version", "v1"),
                    values.get("injection_policy_version", "v1"),
                    values.get("commercial_use_context", "unknown"),
                    dumps_json(values.get("resource_preview", {})),
                    values.get("target_fingerprint"),
                    values["requested_by_admin_public_id"],
                ),
            )
        return self.get_rag_promotion_request(public_id)

    def update_rag_promotion_request(
        self, public_id: str, fields: dict[str, Any]
    ) -> dict[str, Any]:
        if not fields:
            return self.get_rag_promotion_request(public_id)
        with self.transaction() as connection:
            self._rag_promotion_request_id(connection, public_id)
            assignments = ", ".join(f'"{key}"=?' for key in fields)
            connection.execute(
                f'UPDATE production_rag_promotion_requests SET {assignments}, '  # noqa: S608
                "updated_at=CURRENT_TIMESTAMP WHERE public_id=?",
                (*fields.values(), public_id),
            )
        return self.get_rag_promotion_request(public_id)

    def get_rag_promotion_request(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._rag_promotion_request_select_sql() + " WHERE r.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("production RAG promotion request not found")
        return _rag_promotion_request_public(row)

    def list_rag_promotion_requests(
        self, *, status: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        limit, offset = self.pagination(limit, offset)
        clauses, params = [], []
        if status:
            clauses.append("r.status=?")
            params.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.transaction() as connection:
            rows = connection.execute(
                self._rag_promotion_request_select_sql() + f" {where} "  # noqa: S608
                "ORDER BY r.id DESC LIMIT ? OFFSET ?",
                (*params, limit, offset),
            ).fetchall()
        return [_rag_promotion_request_public(row) for row in rows]

    @staticmethod
    def _rag_promotion_request_select_sql() -> str:
        return (
            "SELECT r.*, e.public_id AS experiment_public_id, "
            "rep.public_id AS report_public_id, ks.public_id AS knowledge_space_public_id "
            "FROM production_rag_promotion_requests r "
            "JOIN rag_sandbox_experiments e ON e.id = r.rag_sandbox_experiment_id "
            "JOIN rag_sandbox_reports rep ON rep.id = r.rag_sandbox_report_id "
            "JOIN rag_knowledge_spaces ks ON ks.id = r.knowledge_space_id"
        )

    # -- RAG promotion approvals ---------------------------------------------------------

    def create_rag_promotion_approval(
        self, promotion_request_public_id: str, values: dict[str, Any]
    ) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            request_id = self._rag_promotion_request_id(connection, promotion_request_public_id)
            connection.execute(
                """INSERT INTO production_rag_promotion_approvals(
                public_id, promotion_request_id, target_fingerprint,
                requested_by_admin_public_id)
                VALUES (?,?,?,?)""",
                (
                    public_id, request_id, values["target_fingerprint"],
                    values["requested_by_admin_public_id"],
                ),
            )
        return self.get_rag_promotion_approval(public_id)

    def approve_rag_promotion_approval(
        self, public_id: str, *, approved_by_admin_id: str, expires_at: str | None
    ) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT id, status FROM production_rag_promotion_approvals WHERE public_id=?",
                (public_id,),
            ).fetchone()
            if not row:
                raise NotFoundError("production RAG promotion approval not found")
            if row["status"] != "pending":
                raise ValidationError("only a pending approval may be approved")
            connection.execute(
                """UPDATE production_rag_promotion_approvals
                SET status='approved', approved_by_admin_id=?, approved_at=CURRENT_TIMESTAMP,
                expires_at=?, updated_at=CURRENT_TIMESTAMP WHERE public_id=?""",
                (approved_by_admin_id, expires_at, public_id),
            )
        return self.get_rag_promotion_approval(public_id)

    def mark_rag_promotion_approval_expired(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT id, status FROM production_rag_promotion_approvals WHERE public_id=?",
                (public_id,),
            ).fetchone()
            if not row:
                raise NotFoundError("production RAG promotion approval not found")
            if row["status"] == "approved":
                connection.execute(
                    """UPDATE production_rag_promotion_approvals
                    SET status='expired', updated_at=CURRENT_TIMESTAMP WHERE public_id=?""",
                    (public_id,),
                )
        return self.get_rag_promotion_approval(public_id)

    def get_rag_promotion_approval(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._rag_promotion_approval_select_sql() + " WHERE a.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("production RAG promotion approval not found")
        return _rag_promotion_approval_public(row)

    def get_latest_rag_promotion_approval(
        self, promotion_request_public_id: str
    ) -> dict[str, Any] | None:
        with self.transaction() as connection:
            request_id = self._rag_promotion_request_id(connection, promotion_request_public_id)
            row = connection.execute(
                self._rag_promotion_approval_select_sql()
                + " WHERE a.promotion_request_id=? ORDER BY a.id DESC LIMIT 1",
                (request_id,),
            ).fetchone()
        return _rag_promotion_approval_public(row) if row else None

    @staticmethod
    def _rag_promotion_approval_select_sql() -> str:
        return (
            "SELECT a.*, r.public_id AS promotion_request_public_id "
            "FROM production_rag_promotion_approvals a "
            "JOIN production_rag_promotion_requests r ON r.id = a.promotion_request_id"
        )

    # -- RAG release candidates -----------------------------------------------------------

    def create_rag_release_candidate(
        self, promotion_request_public_id: str, values: dict[str, Any]
    ) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            request_id = self._rag_promotion_request_id(connection, promotion_request_public_id)
            knowledge_source_id = None
            if values.get("knowledge_source_public_id"):
                row = connection.execute(
                    "SELECT id FROM rag_knowledge_sources WHERE public_id=?",
                    (values["knowledge_source_public_id"],),
                ).fetchone()
                knowledge_source_id = row["id"] if row else None
            retrieval_profile_id = None
            if values.get("retrieval_profile_public_id"):
                row = connection.execute(
                    "SELECT id FROM rag_retrieval_profiles WHERE public_id=?",
                    (values["retrieval_profile_public_id"],),
                ).fetchone()
                retrieval_profile_id = row["id"] if row else None
            connection.execute(
                """INSERT INTO production_rag_release_candidates(
                public_id, promotion_request_id, knowledge_source_id, retrieval_profile_id,
                record_checksum_set_hash, chunk_checksum_set_hash, embedding_model_reference,
                index_checksum_sha256, configuration_manifest_json, build_log_json,
                resource_usage_json, created_by_admin_public_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    public_id, request_id, knowledge_source_id, retrieval_profile_id,
                    values["record_checksum_set_hash"], values.get("chunk_checksum_set_hash"),
                    values.get("embedding_model_reference"), values.get("index_checksum_sha256"),
                    dumps_json(values.get("configuration_manifest", {})),
                    dumps_json(values.get("build_log", {})),
                    dumps_json(values.get("resource_usage", {})),
                    values["created_by_admin_public_id"],
                ),
            )
        return self.get_rag_release_candidate(public_id)

    def update_rag_release_candidate(
        self, public_id: str, fields: dict[str, Any]
    ) -> dict[str, Any]:
        if not fields:
            return self.get_rag_release_candidate(public_id)
        with self.transaction() as connection:
            self._rag_release_candidate_row(connection, public_id)
            assignments = ", ".join(f'"{key}"=?' for key in fields)
            connection.execute(
                f'UPDATE production_rag_release_candidates SET {assignments}, '  # noqa: S608
                "updated_at=CURRENT_TIMESTAMP WHERE public_id=?",
                (*fields.values(), public_id),
            )
        return self.get_rag_release_candidate(public_id)

    def get_rag_release_candidate(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = self._rag_release_candidate_row(connection, public_id)
        return _rag_release_candidate_public(row)

    def list_rag_release_candidates(self, promotion_request_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            request_id = self._rag_promotion_request_id(connection, promotion_request_public_id)
            rows = connection.execute(
                self._rag_release_candidate_select_sql()
                + " WHERE c.promotion_request_id=? ORDER BY c.id DESC",
                (request_id,),
            ).fetchall()
        return [_rag_release_candidate_public(row) for row in rows]

    @staticmethod
    def _rag_release_candidate_select_sql() -> str:
        return (
            "SELECT c.*, r.public_id AS promotion_request_public_id, "
            "ks.public_id AS knowledge_source_public_id, "
            "rp.public_id AS retrieval_profile_public_id "
            "FROM production_rag_release_candidates c "
            "JOIN production_rag_promotion_requests r ON r.id = c.promotion_request_id "
            "LEFT JOIN rag_knowledge_sources ks ON ks.id = c.knowledge_source_id "
            "LEFT JOIN rag_retrieval_profiles rp ON rp.id = c.retrieval_profile_id"
        )

    # -- RAG validation results (append-only) ----------------------------------------------

    def add_rag_validation_result(
        self, rag_release_candidate_public_id: str, values: dict[str, Any]
    ) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            candidate = self._rag_release_candidate_row(connection, rag_release_candidate_public_id)
            connection.execute(
                """INSERT INTO production_rag_validation_results(
                public_id, rag_release_candidate_id, validation_type, result_status,
                metrics_json, details_json, created_by_admin_public_id)
                VALUES (?,?,?,?,?,?,?)""",
                (
                    public_id, candidate["id"], values["validation_type"],
                    values["result_status"], dumps_json(values.get("metrics", {})),
                    dumps_json(values.get("details", {})),
                    values["created_by_admin_public_id"],
                ),
            )
        return self.get_rag_validation_result(public_id)

    def get_rag_validation_result(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._rag_validation_result_select_sql() + " WHERE v.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("production RAG validation result not found")
        return _rag_validation_result_public(row)

    def list_rag_validation_results(
        self, rag_release_candidate_public_id: str
    ) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            candidate = self._rag_release_candidate_row(
                connection, rag_release_candidate_public_id
            )
            rows = connection.execute(
                self._rag_validation_result_select_sql()
                + " WHERE v.rag_release_candidate_id=? ORDER BY v.id",
                (candidate["id"],),
            ).fetchall()
        return [_rag_validation_result_public(row) for row in rows]

    @staticmethod
    def _rag_validation_result_select_sql() -> str:
        return (
            "SELECT v.*, c.public_id AS rag_release_candidate_public_id "
            "FROM production_rag_validation_results v "
            "JOIN production_rag_release_candidates c ON c.id = v.rag_release_candidate_id"
        )

    # -- RAG activation events (append-only) -----------------------------------------------

    def record_rag_activation_event(
        self, rag_release_candidate_public_id: str, values: dict[str, Any]
    ) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            candidate = self._rag_release_candidate_row(connection, rag_release_candidate_public_id)
            approval_id = None
            if values.get("promotion_approval_public_id"):
                row = connection.execute(
                    "SELECT id FROM production_rag_promotion_approvals WHERE public_id=?",
                    (values["promotion_approval_public_id"],),
                ).fetchone()
                approval_id = row["id"] if row else None
            connection.execute(
                """INSERT INTO production_rag_activation_events(
                public_id, rag_release_candidate_id, promotion_approval_id, event_type,
                previous_active_profile_public_id, summary, metadata_json,
                performed_by_admin_public_id)
                VALUES (?,?,?,?,?,?,?,?)""",
                (
                    public_id, candidate["id"], approval_id, values["event_type"],
                    values.get("previous_active_profile_public_id"),
                    values.get("summary", ""), dumps_json(values.get("metadata", {})),
                    values["performed_by_admin_public_id"],
                ),
            )
        return self.get_rag_activation_event(public_id)

    def get_rag_activation_event(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._rag_activation_event_select_sql() + " WHERE e.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("production RAG activation event not found")
        return _rag_activation_event_public(row)

    def list_rag_activation_events(
        self, rag_release_candidate_public_id: str
    ) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            candidate = self._rag_release_candidate_row(
                connection, rag_release_candidate_public_id
            )
            rows = connection.execute(
                self._rag_activation_event_select_sql()
                + " WHERE e.rag_release_candidate_id=? ORDER BY e.id",
                (candidate["id"],),
            ).fetchall()
        return [_rag_activation_event_public(row) for row in rows]

    @staticmethod
    def _rag_activation_event_select_sql() -> str:
        return (
            "SELECT e.*, c.public_id AS rag_release_candidate_public_id "
            "FROM production_rag_activation_events e "
            "JOIN production_rag_release_candidates c ON c.id = e.rag_release_candidate_id"
        )

    # -- model release requests -------------------------------------------------------------

    def create_model_release_request(self, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            candidate_row = connection.execute(
                "SELECT id FROM core_model_versions WHERE public_id=?",
                (values["model_candidate_public_id"],),
            ).fetchone()
            if not candidate_row:
                raise NotFoundError("model candidate (core model version) not found")
            checkpoint_id = None
            if values.get("incremental_training_checkpoint_public_id"):
                row = connection.execute(
                    "SELECT id FROM incremental_training_checkpoints WHERE public_id=?",
                    (values["incremental_training_checkpoint_public_id"],),
                ).fetchone()
                checkpoint_id = row["id"] if row else None
            connection.execute(
                """INSERT INTO production_model_release_requests(
                public_id, request_code, model_candidate_core_model_version_id,
                incremental_training_checkpoint_id, release_type, target_assignment_keys_json,
                canary_requested, canary_percentage_or_scope, resource_preview_json,
                security_check_version, evaluation_policy_version, target_fingerprint,
                requested_by_admin_public_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    public_id, values["request_code"], candidate_row["id"], checkpoint_id,
                    values.get("release_type", "experimental"),
                    dumps_json(values.get("target_assignment_keys", [])),
                    int(values.get("canary_requested", True)),
                    values.get("canary_percentage_or_scope", "admin_diagnostic"),
                    dumps_json(values.get("resource_preview", {})),
                    values.get("security_check_version", "v1"),
                    values.get("evaluation_policy_version", "v1"),
                    values.get("target_fingerprint"),
                    values["requested_by_admin_public_id"],
                ),
            )
        return self.get_model_release_request(public_id)

    def update_model_release_request(
        self, public_id: str, fields: dict[str, Any]
    ) -> dict[str, Any]:
        if not fields:
            return self.get_model_release_request(public_id)
        with self.transaction() as connection:
            self._model_release_request_id(connection, public_id)
            assignments = ", ".join(f'"{key}"=?' for key in fields)
            connection.execute(
                f'UPDATE production_model_release_requests SET {assignments}, '  # noqa: S608
                "updated_at=CURRENT_TIMESTAMP WHERE public_id=?",
                (*fields.values(), public_id),
            )
        return self.get_model_release_request(public_id)

    def get_model_release_request(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._model_release_request_select_sql() + " WHERE r.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("production model release request not found")
        return _model_release_request_public(row)

    def list_model_release_requests(
        self, *, status: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        limit, offset = self.pagination(limit, offset)
        clauses, params = [], []
        if status:
            clauses.append("r.status=?")
            params.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.transaction() as connection:
            rows = connection.execute(
                self._model_release_request_select_sql() + f" {where} "  # noqa: S608
                "ORDER BY r.id DESC LIMIT ? OFFSET ?",
                (*params, limit, offset),
            ).fetchall()
        return [_model_release_request_public(row) for row in rows]

    @staticmethod
    def _model_release_request_select_sql() -> str:
        return (
            "SELECT r.*, cmv.public_id AS model_candidate_public_id, "
            "ckpt.public_id AS checkpoint_public_id, "
            "mrc.public_id AS model_release_candidate_public_id "
            "FROM production_model_release_requests r "
            "JOIN core_model_versions cmv ON cmv.id = r.model_candidate_core_model_version_id "
            "LEFT JOIN incremental_training_checkpoints ckpt "
            "ON ckpt.id = r.incremental_training_checkpoint_id "
            "LEFT JOIN model_release_candidates mrc ON mrc.id = r.model_release_candidate_id"
        )

    # -- model release approvals -------------------------------------------------------------

    def create_model_release_approval(
        self, release_request_public_id: str, values: dict[str, Any]
    ) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            request_id = self._model_release_request_id(connection, release_request_public_id)
            connection.execute(
                """INSERT INTO production_model_release_approvals(
                public_id, release_request_id, checkpoint_checksum, tokenizer_checksum,
                config_checksum, manifest_checksum, evaluation_report_checksum,
                training_report_checksum, security_report_checksum,
                target_assignment_keys_json, canary_configuration_json, target_fingerprint,
                requested_by_admin_public_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    public_id, request_id, values.get("checkpoint_checksum"),
                    values.get("tokenizer_checksum"), values.get("config_checksum"),
                    values.get("manifest_checksum"), values.get("evaluation_report_checksum"),
                    values.get("training_report_checksum"),
                    values.get("security_report_checksum"),
                    dumps_json(values.get("target_assignment_keys", [])),
                    dumps_json(values.get("canary_configuration", {})),
                    values["target_fingerprint"],
                    values["requested_by_admin_public_id"],
                ),
            )
        return self.get_model_release_approval(public_id)

    def approve_model_release_approval(
        self, public_id: str, *, approved_by_admin_id: str, expires_at: str | None
    ) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT id, status FROM production_model_release_approvals WHERE public_id=?",
                (public_id,),
            ).fetchone()
            if not row:
                raise NotFoundError("production model release approval not found")
            if row["status"] != "pending":
                raise ValidationError("only a pending approval may be approved")
            connection.execute(
                """UPDATE production_model_release_approvals
                SET status='approved', approved_by_admin_id=?, approved_at=CURRENT_TIMESTAMP,
                expires_at=?, updated_at=CURRENT_TIMESTAMP WHERE public_id=?""",
                (approved_by_admin_id, expires_at, public_id),
            )
        return self.get_model_release_approval(public_id)

    def mark_model_release_approval_expired(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT id, status FROM production_model_release_approvals WHERE public_id=?",
                (public_id,),
            ).fetchone()
            if not row:
                raise NotFoundError("production model release approval not found")
            if row["status"] == "approved":
                connection.execute(
                    """UPDATE production_model_release_approvals
                    SET status='expired', updated_at=CURRENT_TIMESTAMP WHERE public_id=?""",
                    (public_id,),
                )
        return self.get_model_release_approval(public_id)

    def get_model_release_approval(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._model_release_approval_select_sql() + " WHERE a.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("production model release approval not found")
        return _model_release_approval_public(row)

    def get_latest_model_release_approval(
        self, release_request_public_id: str
    ) -> dict[str, Any] | None:
        with self.transaction() as connection:
            request_id = self._model_release_request_id(connection, release_request_public_id)
            row = connection.execute(
                self._model_release_approval_select_sql()
                + " WHERE a.release_request_id=? ORDER BY a.id DESC LIMIT 1",
                (request_id,),
            ).fetchone()
        return _model_release_approval_public(row) if row else None

    @staticmethod
    def _model_release_approval_select_sql() -> str:
        return (
            "SELECT a.*, r.public_id AS release_request_public_id "
            "FROM production_model_release_approvals a "
            "JOIN production_model_release_requests r ON r.id = a.release_request_id"
        )

    # -- model activation events (append-only) ----------------------------------------------

    def record_model_activation_event(
        self, release_request_public_id: str, values: dict[str, Any]
    ) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            request_id = self._model_release_request_id(connection, release_request_public_id)
            approval_id = None
            if values.get("release_approval_public_id"):
                row = connection.execute(
                    "SELECT id FROM production_model_release_approvals WHERE public_id=?",
                    (values["release_approval_public_id"],),
                ).fetchone()
                approval_id = row["id"] if row else None
            assignment_id = None
            if values.get("inference_model_assignment_public_id"):
                row = connection.execute(
                    "SELECT id FROM inference_model_assignments WHERE public_id=?",
                    (values["inference_model_assignment_public_id"],),
                ).fetchone()
                assignment_id = row["id"] if row else None
            connection.execute(
                """INSERT INTO production_model_activation_events(
                public_id, release_request_id, release_approval_id,
                inference_model_assignment_id, event_type,
                previous_assignment_snapshot_json, summary, metadata_json,
                performed_by_admin_public_id)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    public_id, request_id, approval_id, assignment_id, values["event_type"],
                    dumps_json(values.get("previous_assignment_snapshot", {})),
                    values.get("summary", ""), dumps_json(values.get("metadata", {})),
                    values["performed_by_admin_public_id"],
                ),
            )
        return self.get_model_activation_event(public_id)

    def get_model_activation_event(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._model_activation_event_select_sql() + " WHERE e.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("production model activation event not found")
        return _model_activation_event_public(row)

    def list_model_activation_events(self, release_request_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            request_id = self._model_release_request_id(connection, release_request_public_id)
            rows = connection.execute(
                self._model_activation_event_select_sql()
                + " WHERE e.release_request_id=? ORDER BY e.id",
                (request_id,),
            ).fetchall()
        return [_model_activation_event_public(row) for row in rows]

    @staticmethod
    def _model_activation_event_select_sql() -> str:
        return (
            "SELECT e.*, r.public_id AS release_request_public_id, "
            "a.public_id AS release_approval_public_id, "
            "asn.public_id AS inference_model_assignment_public_id "
            "FROM production_model_activation_events e "
            "JOIN production_model_release_requests r ON r.id = e.release_request_id "
            "LEFT JOIN production_model_release_approvals a ON a.id = e.release_approval_id "
            "LEFT JOIN inference_model_assignments asn ON asn.id = e.inference_model_assignment_id"
        )

    # -- model post-activation checks (append-only) ------------------------------------------

    def add_model_post_activation_check(
        self, release_request_public_id: str, values: dict[str, Any]
    ) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            request_id = self._model_release_request_id(connection, release_request_public_id)
            connection.execute(
                """INSERT INTO production_model_post_activation_checks(
                public_id, release_request_id, check_type, result_status, metrics_json,
                details_json, created_by_admin_public_id)
                VALUES (?,?,?,?,?,?,?)""",
                (
                    public_id, request_id, values["check_type"], values["result_status"],
                    dumps_json(values.get("metrics", {})), dumps_json(values.get("details", {})),
                    values["created_by_admin_public_id"],
                ),
            )
        return self.get_model_post_activation_check(public_id)

    def get_model_post_activation_check(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._model_post_activation_check_select_sql() + " WHERE c.public_id=?",
                (public_id,),
            ).fetchone()
        if not row:
            raise NotFoundError("production model post-activation check not found")
        return _model_post_activation_check_public(row)

    def list_model_post_activation_checks(
        self, release_request_public_id: str
    ) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            request_id = self._model_release_request_id(connection, release_request_public_id)
            rows = connection.execute(
                self._model_post_activation_check_select_sql()
                + " WHERE c.release_request_id=? ORDER BY c.id",
                (request_id,),
            ).fetchall()
        return [_model_post_activation_check_public(row) for row in rows]

    @staticmethod
    def _model_post_activation_check_select_sql() -> str:
        return (
            "SELECT c.*, r.public_id AS release_request_public_id "
            "FROM production_model_post_activation_checks c "
            "JOIN production_model_release_requests r ON r.id = c.release_request_id"
        )

    # -- rollback plans -----------------------------------------------------------------------

    def create_rollback_plan(self, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            connection.execute(
                """INSERT INTO production_rollback_plans(
                public_id, target_type, current_active_version, candidate_version,
                previous_assignment_snapshot_json, previous_rag_state_snapshot_json,
                backup_reference, rollback_steps_json, validation_steps_json,
                maximum_recovery_time_target_seconds, created_by_admin_public_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    public_id, values["target_type"], values.get("current_active_version"),
                    values.get("candidate_version"),
                    dumps_json(values.get("previous_assignment_snapshot", {})),
                    dumps_json(values.get("previous_rag_state_snapshot", {})),
                    values.get("backup_reference"),
                    dumps_json(values.get("rollback_steps", [])),
                    dumps_json(values.get("validation_steps", [])),
                    values.get("maximum_recovery_time_target_seconds", 900),
                    values["created_by_admin_public_id"],
                ),
            )
        return self.get_rollback_plan(public_id)

    def update_rollback_plan_status(self, public_id: str, status: str) -> dict[str, Any]:
        with self.transaction() as connection:
            self._rollback_plan_id(connection, public_id)
            connection.execute(
                "UPDATE production_rollback_plans SET status=?, "
                "updated_at=CURRENT_TIMESTAMP WHERE public_id=?",
                (status, public_id),
            )
        return self.get_rollback_plan(public_id)

    def get_rollback_plan(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM production_rollback_plans WHERE public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("production rollback plan not found")
        return _rollback_plan_public(row)

    def list_rollback_plans(
        self, *, target_type: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        limit, offset = self.pagination(limit, offset)
        clauses, params = [], []
        if target_type:
            clauses.append("target_type=?")
            params.append(target_type)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.transaction() as connection:
            rows = connection.execute(
                f"SELECT * FROM production_rollback_plans {where} "  # noqa: S608
                "ORDER BY id DESC LIMIT ? OFFSET ?",
                (*params, limit, offset),
            ).fetchall()
        return [_rollback_plan_public(row) for row in rows]

    # -- rollback events (append-only) ---------------------------------------------------------

    def record_rollback_event(
        self, rollback_plan_public_id: str, values: dict[str, Any]
    ) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            plan_id = self._rollback_plan_id(connection, rollback_plan_public_id)
            connection.execute(
                """INSERT INTO production_rollback_events(
                public_id, rollback_plan_id, event_type, summary, metadata_json,
                performed_by_admin_public_id)
                VALUES (?,?,?,?,?,?)""",
                (
                    public_id, plan_id, values["event_type"], values.get("summary", ""),
                    dumps_json(values.get("metadata", {})),
                    values["performed_by_admin_public_id"],
                ),
            )
        return self.get_rollback_event(public_id)

    def get_rollback_event(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._rollback_event_select_sql() + " WHERE e.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("production rollback event not found")
        return _rollback_event_public(row)

    def list_rollback_events(self, rollback_plan_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            plan_id = self._rollback_plan_id(connection, rollback_plan_public_id)
            rows = connection.execute(
                self._rollback_event_select_sql() + " WHERE e.rollback_plan_id=? ORDER BY e.id",
                (plan_id,),
            ).fetchall()
        return [_rollback_event_public(row) for row in rows]

    @staticmethod
    def _rollback_event_select_sql() -> str:
        return (
            "SELECT e.*, p.public_id AS rollback_plan_public_id "
            "FROM production_rollback_events e "
            "JOIN production_rollback_plans p ON p.id = e.rollback_plan_id"
        )

    # -- artifact security checks (append-only) -------------------------------------------------

    def add_artifact_security_check(self, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            connection.execute(
                """INSERT INTO production_artifact_security_checks(
                public_id, artifact_type, artifact_reference, result_status, checks_json,
                findings_json, created_by_admin_public_id)
                VALUES (?,?,?,?,?,?,?)""",
                (
                    public_id, values["artifact_type"], values["artifact_reference"],
                    values["result_status"], dumps_json(values.get("checks", {})),
                    dumps_json(values.get("findings", [])),
                    values["created_by_admin_public_id"],
                ),
            )
        return self.get_artifact_security_check(public_id)

    def get_artifact_security_check(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM production_artifact_security_checks WHERE public_id=?",
                (public_id,),
            ).fetchone()
        if not row:
            raise NotFoundError("production artifact security check not found")
        return _artifact_security_check_public(row)

    def list_artifact_security_checks(
        self, *, artifact_type: str | None = None, limit: int = 100, offset: int = 0
    ) -> list[dict[str, Any]]:
        limit, offset = self.pagination(limit, offset)
        clauses, params = [], []
        if artifact_type:
            clauses.append("artifact_type=?")
            params.append(artifact_type)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.transaction() as connection:
            rows = connection.execute(
                f"SELECT * FROM production_artifact_security_checks {where} "  # noqa: S608
                "ORDER BY id DESC LIMIT ? OFFSET ?",
                (*params, limit, offset),
            ).fetchall()
        return [_artifact_security_check_public(row) for row in rows]

    # -- backup readiness checks (append-only) --------------------------------------------------

    def add_backup_readiness_check(self, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            connection.execute(
                """INSERT INTO production_backup_readiness_checks(
                public_id, check_type, result_status, latest_backup_filename,
                latest_backup_age_seconds, details_json, created_by_admin_public_id)
                VALUES (?,?,?,?,?,?,?)""",
                (
                    public_id, values["check_type"], values["result_status"],
                    values.get("latest_backup_filename"),
                    values.get("latest_backup_age_seconds"),
                    dumps_json(values.get("details", {})),
                    values["created_by_admin_public_id"],
                ),
            )
        return self.get_backup_readiness_check(public_id)

    def get_backup_readiness_check(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM production_backup_readiness_checks WHERE public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("production backup readiness check not found")
        return _backup_readiness_check_public(row)

    def get_latest_backup_readiness_check(self, check_type: str) -> dict[str, Any] | None:
        with self.transaction() as connection:
            row = connection.execute(
                """SELECT * FROM production_backup_readiness_checks WHERE check_type=?
                ORDER BY id DESC LIMIT 1""",
                (check_type,),
            ).fetchone()
        return _backup_readiness_check_public(row) if row else None

    def list_backup_readiness_checks(
        self, *, check_type: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        limit, offset = self.pagination(limit, offset)
        clauses, params = [], []
        if check_type:
            clauses.append("check_type=?")
            params.append(check_type)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.transaction() as connection:
            rows = connection.execute(
                f"SELECT * FROM production_backup_readiness_checks {where} "  # noqa: S608
                "ORDER BY id DESC LIMIT ? OFFSET ?",
                (*params, limit, offset),
            ).fetchall()
        return [_backup_readiness_check_public(row) for row in rows]

    # -- deployment readiness checks (append-only) ----------------------------------------------

    def add_deployment_readiness_check(self, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            connection.execute(
                """INSERT INTO production_deployment_readiness_checks(
                public_id, result_status, checks_json, blocking_reasons_json,
                created_by_admin_public_id)
                VALUES (?,?,?,?,?)""",
                (
                    public_id, values["result_status"], dumps_json(values.get("checks", {})),
                    dumps_json(values.get("blocking_reasons", [])),
                    values["created_by_admin_public_id"],
                ),
            )
        return self.get_deployment_readiness_check(public_id)

    def get_deployment_readiness_check(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM production_deployment_readiness_checks WHERE public_id=?",
                (public_id,),
            ).fetchone()
        if not row:
            raise NotFoundError("production deployment readiness check not found")
        return _deployment_readiness_check_public(row)

    def get_latest_deployment_readiness_check(self) -> dict[str, Any] | None:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM production_deployment_readiness_checks ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return _deployment_readiness_check_public(row) if row else None

    def list_deployment_readiness_checks(
        self, *, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        limit, offset = self.pagination(limit, offset)
        with self.transaction() as connection:
            rows = connection.execute(
                "SELECT * FROM production_deployment_readiness_checks "
                "ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [_deployment_readiness_check_public(row) for row in rows]

    # -- regression runs/results -----------------------------------------------------------------

    def create_regression_run(self, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            connection.execute(
                """INSERT INTO production_regression_runs(
                public_id, run_code, batch_plan_json, created_by_admin_public_id)
                VALUES (?,?,?,?)""",
                (
                    public_id, values["run_code"], dumps_json(values.get("batch_plan", [])),
                    values["created_by_admin_public_id"],
                ),
            )
        return self.get_regression_run(public_id)

    def update_regression_run_status(self, public_id: str, status: str) -> dict[str, Any]:
        with self.transaction() as connection:
            self._regression_run_id(connection, public_id)
            finalized = ", finalized_at=CURRENT_TIMESTAMP" if status != "in_progress" else ""
            connection.execute(
                f"UPDATE production_regression_runs SET status=?{finalized} "  # noqa: S608
                "WHERE public_id=?",
                (status, public_id),
            )
        return self.get_regression_run(public_id)

    def get_regression_run(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM production_regression_runs WHERE public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("production regression run not found")
        return _regression_run_public(row)

    def list_regression_runs(self, *, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        limit, offset = self.pagination(limit, offset)
        with self.transaction() as connection:
            rows = connection.execute(
                "SELECT * FROM production_regression_runs ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [_regression_run_public(row) for row in rows]

    def add_regression_result(
        self, regression_run_public_id: str, values: dict[str, Any]
    ) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            run_id = self._regression_run_id(connection, regression_run_public_id)
            connection.execute(
                """INSERT INTO production_regression_results(
                public_id, regression_run_id, batch_name, command, status, passed_count,
                failed_count, error_count, duration_seconds, raw_summary)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    public_id, run_id, values["batch_name"], values["command"],
                    values["status"], values.get("passed_count", 0),
                    values.get("failed_count", 0), values.get("error_count", 0),
                    values.get("duration_seconds"), values.get("raw_summary", ""),
                ),
            )
        return self.get_regression_result(public_id)

    def get_regression_result(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._regression_result_select_sql() + " WHERE r.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("production regression result not found")
        return _regression_result_public(row)

    def list_regression_results(self, regression_run_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            run_id = self._regression_run_id(connection, regression_run_public_id)
            rows = connection.execute(
                self._regression_result_select_sql()
                + " WHERE r.regression_run_id=? ORDER BY r.id",
                (run_id,),
            ).fetchall()
        return [_regression_result_public(row) for row in rows]

    def get_latest_regression_result_by_batch_prefix(self, prefix: str) -> dict[str, Any] | None:
        """Most recent regression result whose `batch_name` (stored as
        `"<category>:<batch_id>"`) starts with `prefix` -- used by
        deployment readiness (Phase 15A Step 22) to find the latest
        `browser_e2e:` batch outcome across all regression runs, not just
        the current one.
        """
        with self.transaction() as connection:
            row = connection.execute(
                self._regression_result_select_sql()
                + " WHERE r.batch_name LIKE ? ESCAPE '\\' ORDER BY r.id DESC LIMIT 1",
                (prefix.replace("%", "\\%").replace("_", "\\_") + "%",),
            ).fetchone()
        return _regression_result_public(row) if row else None

    @staticmethod
    def _regression_result_select_sql() -> str:
        return (
            "SELECT r.*, run.public_id AS regression_run_public_id "
            "FROM production_regression_results r "
            "JOIN production_regression_runs run ON run.id = r.regression_run_id"
        )

    # -- readiness reports (append-only, versioned) ----------------------------------------------

    def add_readiness_report(self, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            next_version = connection.execute(
                "SELECT COALESCE(MAX(report_version), 0) + 1 FROM production_readiness_reports"
            ).fetchone()[0]
            connection.execute(
                """INSERT INTO production_readiness_reports(
                public_id, report_version, report_json, report_checksum_sha256, recommendation,
                finalized_by_admin_public_id)
                VALUES (?,?,?,?,?,?)""",
                (
                    public_id, next_version, dumps_json(values["report"]),
                    values["report_checksum_sha256"], values["recommendation"],
                    values["finalized_by_admin_public_id"],
                ),
            )
        return self.get_readiness_report(public_id)

    def get_readiness_report(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM production_readiness_reports WHERE public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("production readiness report not found")
        return _readiness_report_public(row)

    def get_latest_readiness_report(self) -> dict[str, Any] | None:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM production_readiness_reports ORDER BY report_version DESC LIMIT 1"
            ).fetchone()
        return _readiness_report_public(row) if row else None

    def list_readiness_reports(self, *, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        limit, offset = self.pagination(limit, offset)
        with self.transaction() as connection:
            rows = connection.execute(
                "SELECT * FROM production_readiness_reports ORDER BY report_version DESC "
                "LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [_readiness_report_public(row) for row in rows]

    # -- acceptance reviews (append-only) ------------------------------------------------------

    def add_acceptance_review(
        self, readiness_report_public_id: str, values: dict[str, Any]
    ) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            report_id = self._readiness_report_id(connection, readiness_report_public_id)
            connection.execute(
                """INSERT INTO production_acceptance_reviews(
                public_id, production_readiness_report_id, decision, reason, conditions_json,
                reviewer_admin_public_id, report_checksum, active_model_checksum,
                active_rag_checksum, target_fingerprint)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    public_id, report_id, values["decision"], values["reason"],
                    dumps_json(values.get("conditions", {})),
                    values["reviewer_admin_public_id"], values["report_checksum"],
                    values.get("active_model_checksum"), values.get("active_rag_checksum"),
                    values["target_fingerprint"],
                ),
            )
        return self.get_acceptance_review(public_id)

    def get_acceptance_review(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._acceptance_review_select_sql() + " WHERE v.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("production acceptance review not found")
        return _acceptance_review_public(row)

    def get_latest_acceptance_review(
        self, readiness_report_public_id: str
    ) -> dict[str, Any] | None:
        with self.transaction() as connection:
            report_id = self._readiness_report_id(connection, readiness_report_public_id)
            row = connection.execute(
                self._acceptance_review_select_sql()
                + " WHERE v.production_readiness_report_id=? ORDER BY v.id DESC LIMIT 1",
                (report_id,),
            ).fetchone()
        return _acceptance_review_public(row) if row else None

    def list_acceptance_reviews(self, readiness_report_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            report_id = self._readiness_report_id(connection, readiness_report_public_id)
            rows = connection.execute(
                self._acceptance_review_select_sql()
                + " WHERE v.production_readiness_report_id=? ORDER BY v.id",
                (report_id,),
            ).fetchall()
        return [_acceptance_review_public(row) for row in rows]

    @staticmethod
    def _acceptance_review_select_sql() -> str:
        return (
            "SELECT v.*, r.public_id AS report_public_id "
            "FROM production_acceptance_reviews v "
            "JOIN production_readiness_reports r ON r.id = v.production_readiness_report_id"
        )

    # -- readiness events (append-only, generic history log) --------------------------------------

    def record_readiness_event(self, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            connection.execute(
                """INSERT INTO production_readiness_events(
                public_id, event_type, resource_type, resource_public_id, summary,
                metadata_json, performed_by_admin_public_id)
                VALUES (?,?,?,?,?,?,?)""",
                (
                    public_id, values["event_type"], values["resource_type"],
                    values["resource_public_id"], values.get("summary", ""),
                    dumps_json(values.get("metadata", {})),
                    values["performed_by_admin_public_id"],
                ),
            )
        return self.get_readiness_event(public_id)

    def get_readiness_event(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM production_readiness_events WHERE public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("production readiness event not found")
        return _readiness_event_public(row)

    def list_readiness_events(self, *, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        limit, offset = self.pagination(limit, offset)
        with self.transaction() as connection:
            rows = connection.execute(
                "SELECT * FROM production_readiness_events ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [_readiness_event_public(row) for row in rows]

    # -- overview (Data Overview / System tile) --------------------------------------------------

    def overview_counts(self) -> dict[str, int]:
        with self.transaction() as connection:
            def count(sql: str, params: tuple = ()) -> int:
                return connection.execute(sql, params).fetchone()[0]

            return {
                "rag_promotions_awaiting_approval": count(
                    "SELECT COUNT(*) FROM production_rag_promotion_requests "
                    "WHERE status='awaiting_review'"
                ),
                "rag_candidates_awaiting_validation": count(
                    "SELECT COUNT(*) FROM production_rag_release_candidates "
                    "WHERE status IN ('built','validating')"
                ),
                "rag_activations_pending": count(
                    "SELECT COUNT(*) FROM production_rag_release_candidates "
                    "WHERE status='validated'"
                ),
                "model_releases_awaiting_validation": count(
                    "SELECT COUNT(*) FROM production_model_release_requests "
                    "WHERE status IN ('draft','awaiting_review')"
                ),
                "model_releases_awaiting_approval": count(
                    "SELECT COUNT(*) FROM production_model_release_requests "
                    "WHERE status='validated'"
                ),
                "canaries_running": count(
                    "SELECT COUNT(*) FROM production_model_release_requests WHERE status='canary'"
                ),
                "activation_failures": count(
                    "SELECT COUNT(*) FROM production_model_release_requests "
                    "WHERE status='activation_failed'"
                ) + count(
                    "SELECT COUNT(*) FROM production_rag_release_candidates WHERE status='failed'"
                ),
                "rollback_readiness_failures": count(
                    "SELECT COUNT(*) FROM production_rollback_plans WHERE status='failed'"
                ),
                "artifact_security_failures": count(
                    "SELECT COUNT(*) FROM production_artifact_security_checks "
                    "WHERE result_status='failed'"
                ),
                "backups_out_of_date": count(
                    "SELECT COUNT(*) FROM production_backup_readiness_checks "
                    "WHERE check_type='backup' AND result_status IN ('failed','not_configured')"
                ),
                "regression_batches_failing": count(
                    "SELECT COUNT(*) FROM production_regression_results WHERE status='failed'"
                ),
                # 0 if never assessed (that absence is already surfaced,
                # blocking, by deployment readiness) or if the latest
                # assessment says "encrypted"; 1 only if an assessment has
                # actually run and currently reports anything else
                # (not_encrypted/not_configured).
                "backups_not_encrypted": count(
                    "SELECT COUNT(*) FROM production_readiness_events "
                    "WHERE event_type='backup_encryption_assessed' "
                    "AND id=(SELECT MAX(id) FROM production_readiness_events "
                    "WHERE event_type='backup_encryption_assessed') "
                    "AND summary != 'result_status=encrypted'"
                ),
                "readiness_reports_awaiting_acceptance": count(
                    """SELECT COUNT(*) FROM production_readiness_reports r
                    WHERE NOT EXISTS (
                        SELECT 1 FROM production_acceptance_reviews a
                        WHERE a.production_readiness_report_id = r.id
                    )"""
                ),
            }


__all__ = ["ProductionReadinessRepository"]
