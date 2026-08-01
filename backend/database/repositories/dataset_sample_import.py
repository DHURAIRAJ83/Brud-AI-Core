"""Repository for the Phase 12 Approved Sample Import, Quarantine, File
Safety, PII & Data Quality Validation workflow: sample imports,
approvals, files, (append-only) download/extraction events, (append-
only) scan results, records, record issues, (append-only) reviews,
(append-only) reports, (append-only) events, and (append-only)
deletion-request transitions.

Never writes to `dataset_records`/`manual_data_records`/
`semantic_chunks`/`structured_record_candidates`/any RAG/training/
evaluation table, and never mutates the Phase 11 verification case it
links to (read-only input). See
docs/sample_import/phase12_sample_import_quarantine_plan.md.
"""

from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError, ValidationError


def _sample_import_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "sample_import_code": row["sample_import_code"],
        "verification_case_public_id": row["verification_case_public_id"],
        "candidate_public_id": row["candidate_public_id"],
        "provider_public_id": row["provider_public_id"],
        "status": row["status"],
        "current_stage": row["current_stage"],
        "purpose": row["purpose"],
        "dataset_version": row["dataset_version"],
        "revision": row["revision"],
        "selection_method": row["selection_method"],
        "selection_seed": row["selection_seed"],
        "source_split": row["source_split"],
        "source_file": row["source_file"],
        "row_start": row["row_start"],
        "row_end": row["row_end"],
        "requested_count": row["requested_count"],
        "actual_count": row["actual_count"],
        "expected_modality": row["expected_modality"],
        "quarantine_relative_path": row["quarantine_relative_path"],
        "quarantine_bytes_used": row["quarantine_bytes_used"],
        "rag_sandbox_eligible": (
            None if row["rag_sandbox_eligible"] is None else bool(row["rag_sandbox_eligible"])
        ),
        "training_assessment_status": row["training_assessment_status"],
        "report": loads_json(row["report_json"]),
        "requested_by_admin_public_id": row["requested_by_admin_public_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "started_at": row["started_at"],
        "finalized_at": row["finalized_at"],
        "cancelled_at": row["cancelled_at"],
        "expired_at": row["expired_at"],
        "deleted_at": row["deleted_at"],
        "locked_at": row["locked_at"],
    }


def _approval_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "sample_import_public_id": row["sample_import_public_id"],
        "verification_case_public_id": row["verification_case_public_id"],
        "candidate_public_id": row["candidate_public_id"],
        "provider_public_id": row["provider_public_id"],
        "approved_by_admin_id": row["approved_by_admin_id"],
        "approved_at": row["approved_at"],
        "expires_at": row["expires_at"],
        "purpose": row["purpose"],
        "requested_record_limit": row["requested_record_limit"],
        "approved_record_limit": row["approved_record_limit"],
        "requested_byte_limit": row["requested_byte_limit"],
        "approved_byte_limit": row["approved_byte_limit"],
        "allowed_file_ids": loads_json(row["allowed_file_ids_json"]),
        "allowed_file_patterns": loads_json(row["allowed_file_patterns_json"]),
        "allowed_formats": loads_json(row["allowed_formats_json"]),
        "expected_modality": row["expected_modality"],
        "expected_languages": loads_json(row["expected_languages_json"]),
        "expected_tasks": loads_json(row["expected_tasks_json"]),
        "dataset_version": row["dataset_version"],
        "revision": row["revision"],
        "source_checksum": row["source_checksum"],
        "target_fingerprint": row["target_fingerprint"],
        "approval_reason": row["approval_reason"],
        "conditions": loads_json(row["conditions_json"]),
        "status": row["status"],
        "requested_by_admin_public_id": row["requested_by_admin_public_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _file_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "sample_import_public_id": row["sample_import_public_id"],
        "source_file_id": row["source_file_id"],
        "original_filename": row["original_filename"],
        "safe_filename": row["safe_filename"],
        "relative_path": row["relative_path"],
        "declared_format": row["declared_format"],
        "detected_mime": row["detected_mime"],
        "detected_signature": row["detected_signature"],
        "size_bytes": row["size_bytes"],
        "checksum": row["checksum"],
        "encoding": row["encoding"],
        "compression_type": row["compression_type"],
        "container_format": row["container_format"],
        "status": row["status"],
        "blocked_class": row["blocked_class"],
        "rejection_reason": row["rejection_reason"],
        "is_archive": bool(row["is_archive"]),
        "archive_format": row["archive_format"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _download_event_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "sample_import_public_id": row["sample_import_public_id"],
        "file_public_id": row["file_public_id"],
        "event_type": row["event_type"],
        "source_url": row["source_url"],
        "resolved_domain": row["resolved_domain"],
        "bytes_downloaded": row["bytes_downloaded"],
        "byte_limit": row["byte_limit"],
        "checksum": row["checksum"],
        "http_status": row["http_status"],
        "error_reason": row["error_reason"],
        "started_at": row["started_at"],
        "completed_at": row["completed_at"],
        "performed_by_admin_public_id": row["performed_by_admin_public_id"],
        "created_at": row["created_at"],
    }


def _extraction_event_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "sample_import_public_id": row["sample_import_public_id"],
        "archive_file_public_id": row["archive_file_public_id"],
        "event_type": row["event_type"],
        "member_path": row["member_path"],
        "rejection_reason": row["rejection_reason"],
        "expanded_bytes": row["expanded_bytes"],
        "member_count": row["member_count"],
        "depth": row["depth"],
        "performed_by_admin_public_id": row["performed_by_admin_public_id"],
        "created_at": row["created_at"],
    }


def _scan_result_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "sample_import_public_id": row["sample_import_public_id"],
        "file_public_id": row["file_public_id"],
        "verdict": row["verdict"],
        "matched_signals": loads_json(row["matched_signals_json"]),
        "reason": row["reason"],
        "scanner_version": row["scanner_version"],
        "scanned_at": row["scanned_at"],
        "created_at": row["created_at"],
    }


def _record_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "sample_import_public_id": row["sample_import_public_id"],
        "source_file_public_id": row["source_file_public_id"],
        "source_row_or_page": row["source_row_or_page"],
        "modality": row["modality"],
        "language": row["language"],
        "task": row["task"],
        "raw_content": row["raw_content"],
        "normalized_content": row["normalized_content"],
        "structured_payload": loads_json(row["structured_payload_json"]),
        "source_checksum": row["source_checksum"],
        "record_checksum": row["record_checksum"],
        "parser_version": row["parser_version"],
        "normalizer_version": row["normalizer_version"],
        "ocr_derived": bool(row["ocr_derived"]),
        "status": row["status"],
        "created_at": row["created_at"],
    }


def _record_issue_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "sample_import_public_id": row["sample_import_public_id"],
        "record_public_id": row["record_public_id"],
        "file_public_id": row["file_public_id"],
        "issue_category": row["issue_category"],
        "issue_type": row["issue_type"],
        "status": row["status"],
        "severity": row["severity"],
        "confidence": row["confidence"],
        "location": loads_json(row["location_json"]),
        "related_group_id": row["related_group_id"],
        "contamination_reference": row["contamination_reference"],
        "reviewer_decision": row["reviewer_decision"],
        "reviewed_by": row["reviewed_by"],
        "reviewed_at": row["reviewed_at"],
        "review_reason": row["review_reason"],
        "detected_at": row["detected_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _review_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "sample_import_public_id": row["sample_import_public_id"],
        "target_type": row["target_type"],
        "target_id": row["target_id"],
        "decision": row["decision"],
        "reason": row["reason"],
        "derived_content_text": row["derived_content_text"],
        "derived_content_checksum": row["derived_content_checksum"],
        "conditions": loads_json(row["conditions_json"]),
        "reviewer_admin_public_id": row["reviewer_admin_public_id"],
        "reviewed_at": row["reviewed_at"],
        "created_at": row["created_at"],
    }


def _report_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "sample_import_public_id": row["sample_import_public_id"],
        "report_version": row["report_version"],
        "rag_sandbox_eligible": bool(row["rag_sandbox_eligible"]),
        "training_assessment_status": row["training_assessment_status"],
        "report": loads_json(row["report_json"]),
        "finalized_by_admin_public_id": row["finalized_by_admin_public_id"],
        "finalized_at": row["finalized_at"],
        "created_at": row["created_at"],
    }


def _event_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "sample_import_public_id": row["sample_import_public_id"],
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
        "sample_import_public_id": row["sample_import_public_id"],
        "status": row["status"],
        "lineage_impact_summary": loads_json(row["lineage_impact_summary_json"]),
        "reason": row["reason"],
        "requested_by_admin_public_id": row["requested_by_admin_public_id"],
        "requested_at": row["requested_at"],
        "confirmed_by_admin_public_id": row["confirmed_by_admin_public_id"],
        "confirmed_at": row["confirmed_at"],
        "executed_at": row["executed_at"],
        "cancelled_at": row["cancelled_at"],
        "created_at": row["created_at"],
    }


class DatasetSampleImportRepository(BaseRepository):
    # -- shared lookups ---------------------------------------------------------

    def _import_row(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT id, locked_at FROM external_dataset_sample_imports WHERE public_id=?",
            (public_id,),
        ).fetchone()
        if not row:
            raise NotFoundError("sample import not found")
        return row

    def _import_id(self, connection: sqlite3.Connection, public_id: str) -> int:
        return self._import_row(connection, public_id)["id"]

    def _require_unlocked_import(self, connection: sqlite3.Connection, public_id: str) -> int:
        row = self._import_row(connection, public_id)
        if row["locked_at"] is not None:
            raise ValidationError("sample import is finalized and locked")
        return row["id"]

    def _candidate_id(self, connection: sqlite3.Connection, candidate_public_id: str) -> int:
        row = connection.execute(
            "SELECT id FROM external_dataset_candidates WHERE public_id=?", (candidate_public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("dataset candidate not found")
        return row["id"]

    def _case_id(self, connection: sqlite3.Connection, case_public_id: str) -> int:
        row = connection.execute(
            "SELECT id FROM external_dataset_verification_cases WHERE public_id=?",
            (case_public_id,),
        ).fetchone()
        if not row:
            raise NotFoundError("verification case not found")
        return row["id"]

    def _provider_id(self, connection: sqlite3.Connection, provider_public_id: str) -> int | None:
        row = connection.execute(
            "SELECT id FROM external_data_providers WHERE public_id=?", (provider_public_id,)
        ).fetchone()
        return row["id"] if row else None

    def _file_id(self, connection: sqlite3.Connection, file_public_id: str) -> int:
        row = connection.execute(
            "SELECT id FROM external_dataset_sample_files WHERE public_id=?", (file_public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("sample file not found")
        return row["id"]

    def _record_id(self, connection: sqlite3.Connection, record_public_id: str) -> int:
        row = connection.execute(
            "SELECT id FROM external_dataset_sample_records WHERE public_id=?",
            (record_public_id,),
        ).fetchone()
        if not row:
            raise NotFoundError("sample record not found")
        return row["id"]

    # -- sample imports -----------------------------------------------------------

    def create_sample_import(self, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            case_id = self._case_id(connection, values["verification_case_public_id"])
            candidate_id = self._candidate_id(connection, values["candidate_public_id"])
            provider_id = None
            if values.get("provider_public_id"):
                provider_id = self._provider_id(connection, values["provider_public_id"])
            connection.execute(
                """INSERT INTO external_dataset_sample_imports(
                public_id, sample_import_code, verification_case_id, candidate_id, provider_id,
                purpose, dataset_version, revision, selection_method, selection_seed,
                source_split, source_file, row_start, row_end, requested_count,
                expected_modality, requested_by_admin_public_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    values["sample_import_code"],
                    case_id,
                    candidate_id,
                    provider_id,
                    values["purpose"],
                    values.get("dataset_version"),
                    values.get("revision"),
                    values["selection_method"],
                    values.get("selection_seed"),
                    values.get("source_split"),
                    values.get("source_file"),
                    values.get("row_start"),
                    values.get("row_end"),
                    values.get("requested_count", 0),
                    values.get("expected_modality", "text"),
                    values["requested_by_admin_public_id"],
                ),
            )
        return self.get_sample_import(public_id)

    def get_sample_import(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._import_select_sql() + " WHERE si.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("sample import not found")
        return _sample_import_public(row)

    def get_active_sample_import_for_case(self, case_public_id: str) -> dict[str, Any] | None:
        with self.transaction() as connection:
            row = connection.execute(
                self._import_select_sql()
                + """ WHERE vc.public_id=? AND si.status NOT IN (
                    'validated','validated_with_conditions','rejected','failed','cancelled',
                    'expired','withdrawn','deleted'
                ) ORDER BY si.id DESC LIMIT 1""",
                (case_public_id,),
            ).fetchone()
        return _sample_import_public(row) if row else None

    def list_sample_imports(
        self,
        *,
        status: str | None = None,
        candidate_public_id: str | None = None,
        verification_case_public_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        limit, offset = self.pagination(limit, offset)
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("si.status=?")
            params.append(status)
        if candidate_public_id:
            clauses.append("c.public_id=?")
            params.append(candidate_public_id)
        if verification_case_public_id:
            clauses.append("vc.public_id=?")
            params.append(verification_case_public_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.transaction() as connection:
            rows = connection.execute(
                self._import_select_sql() + f" {where} "  # noqa: S608
                "ORDER BY si.id DESC LIMIT ? OFFSET ?",
                (*params, limit, offset),
            ).fetchall()
        return [_sample_import_public(row) for row in rows]

    def update_sample_import(self, public_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        if not fields:
            return self.get_sample_import(public_id)
        with self.transaction() as connection:
            self._require_unlocked_import(connection, public_id)
            assignments = ", ".join(f'"{key}"=?' for key in fields)
            connection.execute(
                f'UPDATE external_dataset_sample_imports SET {assignments}, '  # noqa: S608
                "updated_at=CURRENT_TIMESTAMP WHERE public_id=?",
                (*fields.values(), public_id),
            )
        return self.get_sample_import(public_id)

    def lock_sample_import(
        self,
        public_id: str,
        *,
        report: dict[str, Any],
        rag_sandbox_eligible: bool,
        training_assessment_status: str,
        status: str = "validated",
    ) -> dict[str, Any]:
        """Sets `locked_at` exactly once, mirroring Phase 11's verification-
        case finalize -- refuses to run twice."""

        with self.transaction() as connection:
            self._require_unlocked_import(connection, public_id)
            connection.execute(
                """UPDATE external_dataset_sample_imports
                SET locked_at=CURRENT_TIMESTAMP, finalized_at=CURRENT_TIMESTAMP,
                report_json=?, rag_sandbox_eligible=?, training_assessment_status=?,
                status=?, updated_at=CURRENT_TIMESTAMP
                WHERE public_id=?""",
                (
                    dumps_json(report),
                    int(rag_sandbox_eligible),
                    training_assessment_status,
                    status,
                    public_id,
                ),
            )
        return self.get_sample_import(public_id)

    def overview_counts(self) -> dict[str, int]:
        """One aggregate pass for the Data Overview page's Phase 12
        metrics (Step 34) -- computed server-side, never by paging
        through every sample import client-side."""

        with self.transaction() as connection:
            awaiting_approval = connection.execute(
                "SELECT COUNT(*) FROM external_dataset_sample_imports WHERE status=?",
                ("awaiting_approval",),
            ).fetchone()[0]
            downloading = connection.execute(
                "SELECT COUNT(*) FROM external_dataset_sample_imports WHERE status=?",
                ("downloading",),
            ).fetchone()[0]
            in_quarantine = connection.execute(
                """SELECT COUNT(*) FROM external_dataset_sample_imports
                WHERE status IN ('quarantined','scanning','parsing')"""
            ).fetchone()[0]
            needs_review = connection.execute(
                "SELECT COUNT(*) FROM external_dataset_sample_imports WHERE status=?",
                ("needs_review",),
            ).fetchone()[0]
            blocked_by_pii = connection.execute(
                """SELECT COUNT(DISTINCT sample_import_id)
                FROM external_dataset_sample_record_issues
                WHERE issue_category='pii' AND status='blocked'"""
            ).fetchone()[0]
            blocked_by_security = connection.execute(
                """SELECT COUNT(DISTINCT sample_import_id) FROM external_dataset_sample_scan_results
                WHERE verdict='blocked'"""
            ).fetchone()[0]
            with_contamination = connection.execute(
                """SELECT COUNT(DISTINCT sample_import_id)
                FROM external_dataset_sample_record_issues
                WHERE issue_category='contamination' AND status='confirmed_overlap'"""
            ).fetchone()[0]
            rag_sandbox_eligible = connection.execute(
                """SELECT COUNT(*) FROM external_dataset_sample_imports
                WHERE rag_sandbox_eligible=1"""
            ).fetchone()[0]
            quarantine_bytes = connection.execute(
                """SELECT COALESCE(SUM(quarantine_bytes_used), 0)
                FROM external_dataset_sample_imports"""
            ).fetchone()[0]
        return {
            "sample_imports_awaiting_approval": awaiting_approval,
            "samples_downloading": downloading,
            "samples_in_quarantine": in_quarantine,
            "samples_needing_review": needs_review,
            "samples_blocked_by_pii": blocked_by_pii,
            "samples_blocked_by_security": blocked_by_security,
            "samples_with_contamination": with_contamination,
            "samples_eligible_for_rag_sandbox": rag_sandbox_eligible,
            "quarantine_storage_used_bytes": quarantine_bytes,
        }

    @staticmethod
    def _import_select_sql() -> str:
        return (
            "SELECT si.*, vc.public_id AS verification_case_public_id, "
            "c.public_id AS candidate_public_id, p.public_id AS provider_public_id "
            "FROM external_dataset_sample_imports si "
            "JOIN external_dataset_verification_cases vc ON vc.id = si.verification_case_id "
            "JOIN external_dataset_candidates c ON c.id = si.candidate_id "
            "LEFT JOIN external_data_providers p ON p.id = si.provider_id"
        )

    # -- approvals ------------------------------------------------------------------

    def create_approval(
        self, sample_import_public_id: str, values: dict[str, Any]
    ) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            sample_import_id = self._require_unlocked_import(connection, sample_import_public_id)
            case_id = self._case_id(connection, values["verification_case_public_id"])
            candidate_id = self._candidate_id(connection, values["candidate_public_id"])
            provider_id = None
            if values.get("provider_public_id"):
                provider_id = self._provider_id(connection, values["provider_public_id"])
            connection.execute(
                """INSERT INTO external_dataset_sample_import_approvals(
                public_id, sample_import_id, verification_case_id, candidate_id, provider_id,
                purpose, requested_record_limit, requested_byte_limit,
                allowed_file_ids_json, allowed_file_patterns_json, allowed_formats_json,
                expected_modality, expected_languages_json, expected_tasks_json,
                dataset_version, revision, source_checksum, target_fingerprint,
                requested_by_admin_public_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    sample_import_id,
                    case_id,
                    candidate_id,
                    provider_id,
                    values["purpose"],
                    values["requested_record_limit"],
                    values["requested_byte_limit"],
                    dumps_json(values.get("allowed_file_ids", [])),
                    dumps_json(values.get("allowed_file_patterns", [])),
                    dumps_json(values.get("allowed_formats", [])),
                    values.get("expected_modality", "text"),
                    dumps_json(values.get("expected_languages", [])),
                    dumps_json(values.get("expected_tasks", [])),
                    values.get("dataset_version"),
                    values.get("revision"),
                    values.get("source_checksum"),
                    values["target_fingerprint"],
                    values["requested_by_admin_public_id"],
                ),
            )
            connection.execute(
                "UPDATE external_dataset_sample_imports SET status='awaiting_approval', "
                "current_stage='approval', updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (sample_import_id,),
            )
        return self.get_approval(public_id)

    def approve_approval(
        self,
        public_id: str,
        *,
        approved_by_admin_id: str,
        approved_record_limit: int,
        approved_byte_limit: int,
        expires_at: str,
        approval_reason: str | None = None,
        conditions: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT id, sample_import_id, status FROM external_dataset_sample_import_approvals "
                "WHERE public_id=?",
                (public_id,),
            ).fetchone()
            if not row:
                raise NotFoundError("sample import approval not found")
            if row["status"] != "pending":
                raise ValidationError("only a pending approval may be approved")
            connection.execute(
                """UPDATE external_dataset_sample_import_approvals SET status='approved',
                approved_by_admin_id=?, approved_at=CURRENT_TIMESTAMP, expires_at=?,
                approved_record_limit=?, approved_byte_limit=?, approval_reason=?,
                conditions_json=?, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                (
                    approved_by_admin_id,
                    expires_at,
                    approved_record_limit,
                    approved_byte_limit,
                    approval_reason,
                    dumps_json(conditions or {}),
                    row["id"],
                ),
            )
            connection.execute(
                "UPDATE external_dataset_sample_imports SET status='approved', "
                "updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (row["sample_import_id"],),
            )
        return self.get_approval(public_id)

    def reject_approval(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT id, sample_import_id, status FROM external_dataset_sample_import_approvals "
                "WHERE public_id=?",
                (public_id,),
            ).fetchone()
            if not row:
                raise NotFoundError("sample import approval not found")
            if row["status"] != "pending":
                raise ValidationError("only a pending approval may be rejected")
            connection.execute(
                "UPDATE external_dataset_sample_import_approvals SET status='rejected', "
                "updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (row["id"],),
            )
            connection.execute(
                "UPDATE external_dataset_sample_imports SET status='rejected', "
                "updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (row["sample_import_id"],),
            )
        return self.get_approval(public_id)

    def expire_approval(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT id, status FROM external_dataset_sample_import_approvals WHERE public_id=?",
                (public_id,),
            ).fetchone()
            if not row:
                raise NotFoundError("sample import approval not found")
            if row["status"] != "approved":
                raise ValidationError("only an approved approval may expire")
            connection.execute(
                "UPDATE external_dataset_sample_import_approvals SET status='expired', "
                "updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (row["id"],),
            )
        return self.get_approval(public_id)

    def get_approval(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._approval_select_sql() + " WHERE a.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("sample import approval not found")
        return _approval_public(row)

    def get_latest_approval(self, sample_import_public_id: str) -> dict[str, Any] | None:
        with self.transaction() as connection:
            sample_import_id = self._import_id(connection, sample_import_public_id)
            row = connection.execute(
                self._approval_select_sql()
                + " WHERE a.sample_import_id=? ORDER BY a.id DESC LIMIT 1",
                (sample_import_id,),
            ).fetchone()
        return _approval_public(row) if row else None

    def list_approvals(self, sample_import_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            sample_import_id = self._import_id(connection, sample_import_public_id)
            rows = connection.execute(
                self._approval_select_sql() + " WHERE a.sample_import_id=? ORDER BY a.id",
                (sample_import_id,),
            ).fetchall()
        return [_approval_public(row) for row in rows]

    @staticmethod
    def _approval_select_sql() -> str:
        return (
            "SELECT a.*, si.public_id AS sample_import_public_id, "
            "vc.public_id AS verification_case_public_id, c.public_id AS candidate_public_id, "
            "p.public_id AS provider_public_id "
            "FROM external_dataset_sample_import_approvals a "
            "JOIN external_dataset_sample_imports si ON si.id = a.sample_import_id "
            "JOIN external_dataset_verification_cases vc ON vc.id = a.verification_case_id "
            "JOIN external_dataset_candidates c ON c.id = a.candidate_id "
            "LEFT JOIN external_data_providers p ON p.id = a.provider_id"
        )

    # -- files ------------------------------------------------------------------------

    def add_file(self, sample_import_public_id: str, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            sample_import_id = self._import_id(connection, sample_import_public_id)
            connection.execute(
                """INSERT INTO external_dataset_sample_files(
                public_id, sample_import_id, source_file_id, original_filename, safe_filename,
                relative_path, declared_format, is_archive, archive_format)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    sample_import_id,
                    values.get("source_file_id"),
                    values["original_filename"],
                    values["safe_filename"],
                    values["relative_path"],
                    values.get("declared_format"),
                    int(bool(values.get("is_archive", False))),
                    values.get("archive_format"),
                ),
            )
        return self.get_file(public_id)

    def update_file(self, public_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        if not fields:
            return self.get_file(public_id)
        with self.transaction() as connection:
            self._file_id(connection, public_id)
            assignments = ", ".join(f'"{key}"=?' for key in fields)
            connection.execute(
                f'UPDATE external_dataset_sample_files SET {assignments}, '  # noqa: S608
                "updated_at=CURRENT_TIMESTAMP WHERE public_id=?",
                (*fields.values(), public_id),
            )
        return self.get_file(public_id)

    def get_file(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._file_select_sql() + " WHERE f.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("sample file not found")
        return _file_public(row)

    def list_files(
        self, sample_import_public_id: str, *, status: str | None = None
    ) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            sample_import_id = self._import_id(connection, sample_import_public_id)
            clauses = ["f.sample_import_id=?"]
            params: list[Any] = [sample_import_id]
            if status:
                clauses.append("f.status=?")
                params.append(status)
            rows = connection.execute(
                self._file_select_sql()
                + f" WHERE {' AND '.join(clauses)} ORDER BY f.id",  # noqa: S608
                params,
            ).fetchall()
        return [_file_public(row) for row in rows]

    @staticmethod
    def _file_select_sql() -> str:
        return (
            "SELECT f.*, si.public_id AS sample_import_public_id "
            "FROM external_dataset_sample_files f "
            "JOIN external_dataset_sample_imports si ON si.id = f.sample_import_id"
        )

    # -- download events (append-only) -------------------------------------------------

    def record_download_event(
        self, sample_import_public_id: str, values: dict[str, Any]
    ) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            sample_import_id = self._import_id(connection, sample_import_public_id)
            file_id = None
            if values.get("file_public_id"):
                file_id = self._file_id(connection, values["file_public_id"])
            connection.execute(
                """INSERT INTO external_dataset_sample_download_events(
                public_id, sample_import_id, file_id, event_type, source_url, resolved_domain,
                bytes_downloaded, byte_limit, checksum, http_status, error_reason, started_at,
                completed_at, performed_by_admin_public_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    sample_import_id,
                    file_id,
                    values["event_type"],
                    values.get("source_url"),
                    values.get("resolved_domain"),
                    values.get("bytes_downloaded", 0),
                    values.get("byte_limit"),
                    values.get("checksum"),
                    values.get("http_status"),
                    values.get("error_reason"),
                    values.get("started_at"),
                    values.get("completed_at"),
                    values["performed_by_admin_public_id"],
                ),
            )
        return self.get_download_event(public_id)

    def get_download_event(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._download_event_select_sql() + " WHERE d.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("download event not found")
        return _download_event_public(row)

    def list_download_events(self, sample_import_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            sample_import_id = self._import_id(connection, sample_import_public_id)
            rows = connection.execute(
                self._download_event_select_sql()
                + " WHERE d.sample_import_id=? ORDER BY d.id",
                (sample_import_id,),
            ).fetchall()
        return [_download_event_public(row) for row in rows]

    @staticmethod
    def _download_event_select_sql() -> str:
        return (
            "SELECT d.*, si.public_id AS sample_import_public_id, "
            "f.public_id AS file_public_id "
            "FROM external_dataset_sample_download_events d "
            "JOIN external_dataset_sample_imports si ON si.id = d.sample_import_id "
            "LEFT JOIN external_dataset_sample_files f ON f.id = d.file_id"
        )

    # -- extraction events (append-only) -----------------------------------------------

    def record_extraction_event(
        self, sample_import_public_id: str, values: dict[str, Any]
    ) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            sample_import_id = self._import_id(connection, sample_import_public_id)
            archive_file_id = self._file_id(connection, values["archive_file_public_id"])
            connection.execute(
                """INSERT INTO external_dataset_sample_extraction_events(
                public_id, sample_import_id, archive_file_id, event_type, member_path,
                rejection_reason, expanded_bytes, member_count, depth,
                performed_by_admin_public_id)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    sample_import_id,
                    archive_file_id,
                    values["event_type"],
                    values.get("member_path"),
                    values.get("rejection_reason"),
                    values.get("expanded_bytes"),
                    values.get("member_count"),
                    values.get("depth"),
                    values["performed_by_admin_public_id"],
                ),
            )
        return self.get_extraction_event(public_id)

    def get_extraction_event(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._extraction_event_select_sql() + " WHERE e.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("extraction event not found")
        return _extraction_event_public(row)

    def list_extraction_events(self, sample_import_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            sample_import_id = self._import_id(connection, sample_import_public_id)
            rows = connection.execute(
                self._extraction_event_select_sql()
                + " WHERE e.sample_import_id=? ORDER BY e.id",
                (sample_import_id,),
            ).fetchall()
        return [_extraction_event_public(row) for row in rows]

    @staticmethod
    def _extraction_event_select_sql() -> str:
        return (
            "SELECT e.*, si.public_id AS sample_import_public_id, "
            "f.public_id AS archive_file_public_id "
            "FROM external_dataset_sample_extraction_events e "
            "JOIN external_dataset_sample_imports si ON si.id = e.sample_import_id "
            "JOIN external_dataset_sample_files f ON f.id = e.archive_file_id"
        )

    # -- scan results (append-only) ------------------------------------------------------

    def record_scan_result(
        self, sample_import_public_id: str, values: dict[str, Any]
    ) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            sample_import_id = self._import_id(connection, sample_import_public_id)
            file_id = self._file_id(connection, values["file_public_id"])
            connection.execute(
                """INSERT INTO external_dataset_sample_scan_results(
                public_id, sample_import_id, file_id, verdict, matched_signals_json, reason,
                scanner_version)
                VALUES (?,?,?,?,?,?,?)""",
                (
                    public_id,
                    sample_import_id,
                    file_id,
                    values["verdict"],
                    dumps_json(values.get("matched_signals", [])),
                    values.get("reason", ""),
                    values.get("scanner_version", ""),
                ),
            )
        return self.get_scan_result(public_id)

    def get_scan_result(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._scan_result_select_sql() + " WHERE s.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("scan result not found")
        return _scan_result_public(row)

    def list_scan_results(self, sample_import_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            sample_import_id = self._import_id(connection, sample_import_public_id)
            rows = connection.execute(
                self._scan_result_select_sql() + " WHERE s.sample_import_id=? ORDER BY s.id",
                (sample_import_id,),
            ).fetchall()
        return [_scan_result_public(row) for row in rows]

    @staticmethod
    def _scan_result_select_sql() -> str:
        return (
            "SELECT s.*, si.public_id AS sample_import_public_id, "
            "f.public_id AS file_public_id "
            "FROM external_dataset_sample_scan_results s "
            "JOIN external_dataset_sample_imports si ON si.id = s.sample_import_id "
            "JOIN external_dataset_sample_files f ON f.id = s.file_id"
        )

    # -- records ------------------------------------------------------------------------

    def add_record(self, sample_import_public_id: str, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            sample_import_id = self._import_id(connection, sample_import_public_id)
            source_file_id = self._file_id(connection, values["source_file_public_id"])
            connection.execute(
                """INSERT INTO external_dataset_sample_records(
                public_id, sample_import_id, source_file_id, source_row_or_page, modality,
                language, task, raw_content, normalized_content, structured_payload_json,
                source_checksum, record_checksum, parser_version, normalizer_version,
                ocr_derived, status)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    sample_import_id,
                    source_file_id,
                    values.get("source_row_or_page"),
                    values.get("modality", "text"),
                    values.get("language"),
                    values.get("task"),
                    values.get("raw_content", ""),
                    values.get("normalized_content", ""),
                    dumps_json(values.get("structured_payload", {})),
                    values["source_checksum"],
                    values["record_checksum"],
                    values.get("parser_version", ""),
                    values.get("normalizer_version", ""),
                    int(bool(values.get("ocr_derived", False))),
                    values.get("status", "pending"),
                ),
            )
        return self.get_record(public_id)

    def update_record_status(self, public_id: str, status: str) -> dict[str, Any]:
        with self.transaction() as connection:
            self._record_id(connection, public_id)
            connection.execute(
                "UPDATE external_dataset_sample_records SET status=? WHERE public_id=?",
                (status, public_id),
            )
        return self.get_record(public_id)

    def get_record(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._record_select_sql() + " WHERE r.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("sample record not found")
        return _record_public(row)

    def list_records(
        self,
        sample_import_public_id: str,
        *,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        limit, offset = self.pagination(limit, offset)
        with self.transaction() as connection:
            sample_import_id = self._import_id(connection, sample_import_public_id)
            clauses = ["r.sample_import_id=?"]
            params: list[Any] = [sample_import_id]
            if status:
                clauses.append("r.status=?")
                params.append(status)
            rows = connection.execute(
                self._record_select_sql()
                + f" WHERE {' AND '.join(clauses)} "  # noqa: S608
                "ORDER BY r.id LIMIT ? OFFSET ?",
                (*params, limit, offset),
            ).fetchall()
        return [_record_public(row) for row in rows]

    @staticmethod
    def _record_select_sql() -> str:
        return (
            "SELECT r.*, si.public_id AS sample_import_public_id, "
            "f.public_id AS source_file_public_id "
            "FROM external_dataset_sample_records r "
            "JOIN external_dataset_sample_imports si ON si.id = r.sample_import_id "
            "JOIN external_dataset_sample_files f ON f.id = r.source_file_id"
        )

    # -- record issues ------------------------------------------------------------------

    def add_record_issue(
        self, sample_import_public_id: str, values: dict[str, Any]
    ) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            sample_import_id = self._import_id(connection, sample_import_public_id)
            record_id = None
            if values.get("record_public_id"):
                record_id = self._record_id(connection, values["record_public_id"])
            file_id = None
            if values.get("file_public_id"):
                file_id = self._file_id(connection, values["file_public_id"])
            connection.execute(
                """INSERT INTO external_dataset_sample_record_issues(
                public_id, sample_import_id, record_id, file_id, issue_category, issue_type,
                status, severity, confidence, location_json, related_group_id,
                contamination_reference)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    sample_import_id,
                    record_id,
                    file_id,
                    values["issue_category"],
                    values["issue_type"],
                    values["status"],
                    values.get("severity"),
                    values.get("confidence"),
                    dumps_json(values.get("location", {})),
                    values.get("related_group_id"),
                    values.get("contamination_reference"),
                ),
            )
        return self.get_record_issue(public_id)

    def review_record_issue(
        self,
        public_id: str,
        *,
        reviewer_decision: str,
        reviewed_by: str,
        review_reason: str,
    ) -> dict[str, Any]:
        if not review_reason or not review_reason.strip():
            raise ValidationError("a non-empty review reason is required")
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT id FROM external_dataset_sample_record_issues WHERE public_id=?",
                (public_id,),
            ).fetchone()
            if not row:
                raise NotFoundError("record issue not found")
            connection.execute(
                """UPDATE external_dataset_sample_record_issues SET reviewer_decision=?,
                reviewed_by=?, reviewed_at=CURRENT_TIMESTAMP, review_reason=?,
                updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                (reviewer_decision, reviewed_by, review_reason, row["id"]),
            )
        return self.get_record_issue(public_id)

    def get_record_issue(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._record_issue_select_sql() + " WHERE i.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("record issue not found")
        return _record_issue_public(row)

    def list_record_issues(
        self,
        sample_import_public_id: str,
        *,
        issue_category: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            sample_import_id = self._import_id(connection, sample_import_public_id)
            clauses = ["i.sample_import_id=?"]
            params: list[Any] = [sample_import_id]
            if issue_category:
                clauses.append("i.issue_category=?")
                params.append(issue_category)
            if status:
                clauses.append("i.status=?")
                params.append(status)
            rows = connection.execute(
                self._record_issue_select_sql()
                + f" WHERE {' AND '.join(clauses)} ORDER BY i.id",  # noqa: S608
                params,
            ).fetchall()
        return [_record_issue_public(row) for row in rows]

    @staticmethod
    def _record_issue_select_sql() -> str:
        return (
            "SELECT i.*, si.public_id AS sample_import_public_id, "
            "r.public_id AS record_public_id, f.public_id AS file_public_id "
            "FROM external_dataset_sample_record_issues i "
            "JOIN external_dataset_sample_imports si ON si.id = i.sample_import_id "
            "LEFT JOIN external_dataset_sample_records r ON r.id = i.record_id "
            "LEFT JOIN external_dataset_sample_files f ON f.id = i.file_id"
        )

    # -- reviews (append-only) -----------------------------------------------------------

    def add_review(self, sample_import_public_id: str, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            sample_import_id = self._import_id(connection, sample_import_public_id)
            connection.execute(
                """INSERT INTO external_dataset_sample_reviews(
                public_id, sample_import_id, target_type, target_id, decision, reason,
                derived_content_text, derived_content_checksum, conditions_json,
                reviewer_admin_public_id)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    sample_import_id,
                    values["target_type"],
                    values.get("target_id"),
                    values["decision"],
                    values["reason"],
                    values.get("derived_content_text"),
                    values.get("derived_content_checksum"),
                    dumps_json(values.get("conditions", {})),
                    values["reviewer_admin_public_id"],
                ),
            )
        return self.get_review(public_id)

    def get_review(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._review_select_sql() + " WHERE r.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("sample review not found")
        return _review_public(row)

    def list_reviews(self, sample_import_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            sample_import_id = self._import_id(connection, sample_import_public_id)
            rows = connection.execute(
                self._review_select_sql() + " WHERE r.sample_import_id=? ORDER BY r.id",
                (sample_import_id,),
            ).fetchall()
        return [_review_public(row) for row in rows]

    @staticmethod
    def _review_select_sql() -> str:
        return (
            "SELECT r.*, si.public_id AS sample_import_public_id "
            "FROM external_dataset_sample_reviews r "
            "JOIN external_dataset_sample_imports si ON si.id = r.sample_import_id"
        )

    # -- reports (append-only) -----------------------------------------------------------

    def add_report(self, sample_import_public_id: str, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            sample_import_id = self._import_id(connection, sample_import_public_id)
            next_version = (
                connection.execute(
                    "SELECT COALESCE(MAX(report_version), 0) + 1 "
                    "FROM external_dataset_sample_reports WHERE sample_import_id=?",
                    (sample_import_id,),
                ).fetchone()[0]
            )
            connection.execute(
                """INSERT INTO external_dataset_sample_reports(
                public_id, sample_import_id, report_version, rag_sandbox_eligible,
                training_assessment_status, report_json, finalized_by_admin_public_id)
                VALUES (?,?,?,?,?,?,?)""",
                (
                    public_id,
                    sample_import_id,
                    next_version,
                    int(values["rag_sandbox_eligible"]),
                    values["training_assessment_status"],
                    dumps_json(values.get("report", {})),
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
            raise NotFoundError("sample report not found")
        return _report_public(row)

    def get_latest_report(self, sample_import_public_id: str) -> dict[str, Any] | None:
        with self.transaction() as connection:
            sample_import_id = self._import_id(connection, sample_import_public_id)
            row = connection.execute(
                self._report_select_sql()
                + " WHERE r.sample_import_id=? ORDER BY r.report_version DESC LIMIT 1",
                (sample_import_id,),
            ).fetchone()
        return _report_public(row) if row else None

    def list_reports(self, sample_import_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            sample_import_id = self._import_id(connection, sample_import_public_id)
            rows = connection.execute(
                self._report_select_sql()
                + " WHERE r.sample_import_id=? ORDER BY r.report_version",
                (sample_import_id,),
            ).fetchall()
        return [_report_public(row) for row in rows]

    @staticmethod
    def _report_select_sql() -> str:
        return (
            "SELECT r.*, si.public_id AS sample_import_public_id "
            "FROM external_dataset_sample_reports r "
            "JOIN external_dataset_sample_imports si ON si.id = r.sample_import_id"
        )

    # -- events (append-only) ------------------------------------------------------------

    def record_event(self, sample_import_public_id: str, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            sample_import_id = self._import_id(connection, sample_import_public_id)
            connection.execute(
                """INSERT INTO external_dataset_sample_events(
                public_id, sample_import_id, event_type, from_status, to_status, summary,
                metadata_json, performed_by_admin_public_id)
                VALUES (?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    sample_import_id,
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
                self._event_select_sql() + " WHERE e.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("sample event not found")
        return _event_public(row)

    def list_events(
        self, sample_import_public_id: str, *, limit: int = 100
    ) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            sample_import_id = self._import_id(connection, sample_import_public_id)
            rows = connection.execute(
                self._event_select_sql()
                + " WHERE e.sample_import_id=? ORDER BY e.id DESC LIMIT ?",
                (sample_import_id, limit),
            ).fetchall()
        return [_event_public(row) for row in rows]

    @staticmethod
    def _event_select_sql() -> str:
        return (
            "SELECT e.*, si.public_id AS sample_import_public_id "
            "FROM external_dataset_sample_events e "
            "JOIN external_dataset_sample_imports si ON si.id = e.sample_import_id"
        )

    # -- deletion requests (append-only transitions) --------------------------------------

    def request_deletion(
        self, sample_import_public_id: str, values: dict[str, Any]
    ) -> dict[str, Any]:
        public_id = str(uuid4())
        code = f"DR-{uuid4()}"
        with self.transaction() as connection:
            sample_import_id = self._import_id(connection, sample_import_public_id)
            connection.execute(
                """INSERT INTO external_dataset_sample_deletion_requests(
                public_id, deletion_request_code, sample_import_id, status,
                lineage_impact_summary_json, reason, requested_by_admin_public_id)
                VALUES (?,?,?,?,?,?,?)""",
                (
                    public_id,
                    code,
                    sample_import_id,
                    "requested",
                    dumps_json(values.get("lineage_impact_summary", {})),
                    values["reason"],
                    values["requested_by_admin_public_id"],
                ),
            )
        return self.get_deletion_request(public_id)

    # Each transition status writes its own timestamp column; the SQL
    # fragment choice below only ever selects among these 3 fixed,
    # hardcoded-by-us column names -- `status` is never used to build
    # arbitrary SQL text, so there is no injection surface.
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
                """SELECT sample_import_id, lineage_impact_summary_json, reason,
                requested_by_admin_public_id
                FROM external_dataset_sample_deletion_requests
                WHERE deletion_request_code=? ORDER BY id DESC LIMIT 1""",
                (deletion_request_code,),
            ).fetchone()
            if not latest:
                raise NotFoundError("deletion request not found")
            public_id = str(uuid4())
            connection.execute(
                f"""INSERT INTO external_dataset_sample_deletion_requests(
                public_id, deletion_request_code, sample_import_id, status,
                lineage_impact_summary_json, reason, requested_by_admin_public_id,
                confirmed_by_admin_public_id, {timestamp_column})
                VALUES (?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)""",
                (
                    public_id,
                    deletion_request_code,
                    latest["sample_import_id"],
                    status,
                    latest["lineage_impact_summary_json"],
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
            raise NotFoundError("deletion request not found")
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

    def mark_sample_import_deleted(self, public_id: str) -> dict[str, Any]:
        """The one deliberate exception to "no further mutation once
        locked" for sample imports -- deletion must remain possible on
        an already-finalized (`validated`/`validated_with_conditions`)
        import. Whitelisted to exactly `status`/`deleted_at`; never
        touches `report_json`/`rag_sandbox_eligible`/
        `training_assessment_status`, so the immutable report survives
        deletion unchanged."""

        with self.transaction() as connection:
            self._import_id(connection, public_id)
            connection.execute(
                """UPDATE external_dataset_sample_imports
                SET status='deleted', deleted_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP
                WHERE public_id=?""",
                (public_id,),
            )
        return self.get_sample_import(public_id)

    def get_latest_deletion_request(self, sample_import_public_id: str) -> dict[str, Any] | None:
        with self.transaction() as connection:
            sample_import_id = self._import_id(connection, sample_import_public_id)
            row = connection.execute(
                self._deletion_request_select_sql()
                + " WHERE d.sample_import_id=? ORDER BY d.id DESC LIMIT 1",
                (sample_import_id,),
            ).fetchone()
        return _deletion_request_public(row) if row else None

    def list_deletion_requests(self, sample_import_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            sample_import_id = self._import_id(connection, sample_import_public_id)
            rows = connection.execute(
                self._deletion_request_select_sql()
                + " WHERE d.sample_import_id=? ORDER BY d.id",
                (sample_import_id,),
            ).fetchall()
        return [_deletion_request_public(row) for row in rows]

    @staticmethod
    def _deletion_request_select_sql() -> str:
        return (
            "SELECT d.*, si.public_id AS sample_import_public_id "
            "FROM external_dataset_sample_deletion_requests d "
            "JOIN external_dataset_sample_imports si ON si.id = d.sample_import_id"
        )
