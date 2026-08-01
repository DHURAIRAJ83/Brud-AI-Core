"""Repository for the Phase 11 Licence Evidence, Terms Snapshot &
Dataset Verification workflow: verification cases, evidence
snapshots, evidence links, identity checks, permission assessments,
(append-only) verification reviews/events, withdrawal notices, and
upstream sources.

Never writes to `data_sources`/`source_rights`, any governance table,
or Phase 10's own `external_dataset_candidates` use-status columns --
a verification case only ever *links* to one existing Phase 10
candidate (read-only input), and a finalized case may at most *draft*
a Source & Rights proposal through the existing Admin Assistant
pipeline elsewhere. See
docs/data_verification/phase11_licence_evidence_verification_plan.md.
"""

from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError, ValidationError
from core_model.data_verification import ADMIN_ONLY_PERMISSION_STATUSES


def _case_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "verification_code": row["verification_code"],
        "candidate_public_id": row["candidate_public_id"],
        "search_session_public_id": row["search_session_public_id"],
        "status": row["status"],
        "verification_scope": row["verification_scope"],
        "requested_by_admin_public_id": row["requested_by_admin_public_id"],
        "assigned_reviewer_admin_public_id": row["assigned_reviewer_admin_public_id"],
        "current_stage": row["current_stage"],
        "identity_status": row["identity_status"],
        "evidence_status": row["evidence_status"],
        "licence_status": row["licence_status"],
        "declared_licence": row["declared_licence"],
        "normalized_licence_identifier": row["normalized_licence_identifier"],
        "terms_status": row["terms_status"],
        "upstream_status": row["upstream_status"],
        "permission_status": row["permission_status"],
        "conflict_count": row["conflict_count"],
        "warning_count": row["warning_count"],
        "blocking_reason_count": row["blocking_reason_count"],
        "approved_upstream_domains": loads_json(row["approved_upstream_domains_json"]),
        "report": loads_json(row["report_json"]),
        "verification_expiry_status": row["verification_expiry_status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "started_at": row["started_at"],
        "completed_at": row["completed_at"],
        "cancelled_at": row["cancelled_at"],
        "expired_at": row["expired_at"],
        "last_verified_at": row["last_verified_at"],
        "next_reverification_at": row["next_reverification_at"],
        "locked_at": row["locked_at"],
    }


def _evidence_snapshot_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "verification_case_public_id": row["verification_case_public_id"],
        "candidate_public_id": row["candidate_public_id"],
        "provider_public_id": row["provider_public_id"],
        "evidence_type": row["evidence_type"],
        "authority_level": row["authority_level"],
        "source_url": row["source_url"],
        "resolved_url": row["resolved_url"],
        "source_domain": row["source_domain"],
        "source_title": row["source_title"],
        "content_type": row["content_type"],
        "language": row["language"],
        "retrieval_status": row["retrieval_status"],
        "http_status": row["http_status"],
        "retrieved_at": row["retrieved_at"],
        "effective_date": row["effective_date"],
        "last_modified_at": row["last_modified_at"],
        "content_text": row["content_text"],
        "content_excerpt": row["content_excerpt"],
        "content_checksum": row["content_checksum"],
        "response_headers": loads_json(row["response_headers_json"]),
        "metadata": loads_json(row["metadata_json"]),
        "redaction_summary": loads_json(row["redaction_summary_json"]),
        "size_bytes": row["size_bytes"],
        "is_current": bool(row["is_current"]),
        "supersedes_evidence_public_id": row["supersedes_evidence_public_id"],
        "ocr_derived": bool(row["ocr_derived"]),
        "warnings": loads_json(row["warnings_json"]),
        "created_by_admin_public_id": row["created_by_admin_public_id"],
        "created_at": row["created_at"],
    }


def _evidence_link_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "evidence_snapshot_public_id": row["evidence_snapshot_public_id"],
        "linked_entity_type": row["linked_entity_type"],
        "linked_entity_id": row["linked_entity_id"],
        "link_role": row["link_role"],
        "created_at": row["created_at"],
    }


def _identity_check_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "verification_case_public_id": row["verification_case_public_id"],
        "candidate_public_id": row["candidate_public_id"],
        "signal_type": row["signal_type"],
        "expected_value": row["expected_value"],
        "observed_value": row["observed_value"],
        "matched": bool(row["matched"]),
        "reason": row["reason"],
        "evidence_snapshot_public_id": row["evidence_snapshot_public_id"],
        "assessed_at": row["assessed_at"],
        "created_at": row["created_at"],
    }


def _permission_assessment_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "verification_case_public_id": row["verification_case_public_id"],
        "candidate_public_id": row["candidate_public_id"],
        "permission_type": row["permission_type"],
        "status": row["status"],
        "decision_basis": row["decision_basis"],
        "evidence_snapshot_ids": loads_json(row["evidence_snapshot_ids_json"]),
        "conditions": loads_json(row["conditions_json"]),
        "warnings": loads_json(row["warnings_json"]),
        "blocking_reasons": loads_json(row["blocking_reasons_json"]),
        "assessed_by": row["assessed_by"],
        "assessed_at": row["assessed_at"],
        "reviewed_by": row["reviewed_by"],
        "reviewed_at": row["reviewed_at"],
        "reason": row["reason"],
        "evidence_checksum_set": loads_json(row["evidence_checksum_set_json"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _review_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "verification_case_public_id": row["verification_case_public_id"],
        "permission_assessment_public_id": row["permission_assessment_public_id"],
        "permission_type": row["permission_type"],
        "decision": row["decision"],
        "reason": row["reason"],
        "conditions": loads_json(row["conditions_json"]),
        "reviewer_admin_public_id": row["reviewer_admin_public_id"],
        "reviewed_at": row["reviewed_at"],
        "evidence_checksum_set": loads_json(row["evidence_checksum_set_json"]),
        "created_at": row["created_at"],
    }


def _event_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "verification_case_public_id": row["verification_case_public_id"],
        "event_type": row["event_type"],
        "summary": row["summary"],
        "metadata": loads_json(row["metadata_json"]),
        "conflict_type": row["conflict_type"],
        "conflict_severity": row["conflict_severity"],
        "evidence_ids": loads_json(row["evidence_ids_json"]),
        "resolution_status": row["resolution_status"],
        "resolution_reason": row["resolution_reason"],
        "resolved_by_admin_public_id": row["resolved_by_admin_public_id"],
        "resolved_at": row["resolved_at"],
        "performed_by_admin_public_id": row["performed_by_admin_public_id"],
        "created_at": row["created_at"],
    }


def _withdrawal_notice_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "verification_case_public_id": row["verification_case_public_id"],
        "candidate_public_id": row["candidate_public_id"],
        "notice_type": row["notice_type"],
        "source_url": row["source_url"],
        "notice_text": row["notice_text"],
        "received_at": row["received_at"],
        "effective_at": row["effective_at"],
        "recorded_by_admin_public_id": row["recorded_by_admin_public_id"],
        "impact_status": row["impact_status"],
        "impact_summary": loads_json(row["impact_summary_json"]),
        "created_at": row["created_at"],
    }


def _upstream_source_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "verification_case_public_id": row["verification_case_public_id"],
        "candidate_public_id": row["candidate_public_id"],
        "upstream_name": row["upstream_name"],
        "upstream_url": row["upstream_url"],
        "upstream_organization": row["upstream_organization"],
        "upstream_licence": row["upstream_licence"],
        "upstream_terms": row["upstream_terms"],
        "upstream_permission_status": row["upstream_permission_status"],
        "relationship_type": row["relationship_type"],
        "coverage_notes": row["coverage_notes"],
        "verification_status": row["verification_status"],
        "created_by_admin_public_id": row["created_by_admin_public_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


class DatasetVerificationRepository(BaseRepository):
    # -- shared lookups -------------------------------------------------------

    def _case_row(self, connection: sqlite3.Connection, case_public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT id, locked_at FROM external_dataset_verification_cases WHERE public_id=?",
            (case_public_id,),
        ).fetchone()
        if not row:
            raise NotFoundError("verification case not found")
        return row

    def _case_id(self, connection: sqlite3.Connection, case_public_id: str) -> int:
        return self._case_row(connection, case_public_id)["id"]

    def _require_unlocked_case(self, connection: sqlite3.Connection, case_public_id: str) -> int:
        row = self._case_row(connection, case_public_id)
        if row["locked_at"] is not None:
            raise ValidationError("verification case is finalized and locked")
        return row["id"]

    def _candidate_id(self, connection: sqlite3.Connection, candidate_public_id: str) -> int:
        row = connection.execute(
            "SELECT id FROM external_dataset_candidates WHERE public_id=?",
            (candidate_public_id,),
        ).fetchone()
        if not row:
            raise NotFoundError("dataset candidate not found")
        return row["id"]

    # -- verification cases ---------------------------------------------------

    def create_case(self, values: dict[str, Any]) -> dict[str, Any]:
        """Copies the candidate's own `declared_licence` in read-only,
        as of case-creation time -- Phase 10's candidate row is never
        modified, and this copy lets the case's own independent
        licence-verification state evolve without depending on the
        candidate row remaining unchanged for the life of the case."""

        public_id = str(uuid4())
        with self.transaction() as connection:
            candidate_id = self._candidate_id(connection, values["candidate_public_id"])
            candidate_row = connection.execute(
                "SELECT declared_licence FROM external_dataset_candidates WHERE id=?",
                (candidate_id,),
            ).fetchone()
            search_session_id = None
            if values.get("search_session_public_id"):
                session_row = connection.execute(
                    "SELECT id FROM external_dataset_search_sessions WHERE public_id=?",
                    (values["search_session_public_id"],),
                ).fetchone()
                if not session_row:
                    raise NotFoundError("search session not found")
                search_session_id = session_row["id"]
            connection.execute(
                """INSERT INTO external_dataset_verification_cases(
                public_id, verification_code, candidate_id, search_session_id,
                verification_scope, requested_by_admin_public_id, declared_licence)
                VALUES (?,?,?,?,?,?,?)""",
                (
                    public_id,
                    values["verification_code"],
                    candidate_id,
                    search_session_id,
                    values.get("verification_scope", ""),
                    values["requested_by_admin_public_id"],
                    candidate_row["declared_licence"],
                ),
            )
        return self.get_case(public_id)

    def get_case(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._case_select_sql() + " WHERE vc.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("verification case not found")
        return _case_public(row)

    def get_case_by_code(self, verification_code: str) -> dict[str, Any] | None:
        with self.transaction() as connection:
            row = connection.execute(
                self._case_select_sql() + " WHERE vc.verification_code=?", (verification_code,)
            ).fetchone()
        return _case_public(row) if row else None

    def get_active_case_for_candidate(self, candidate_public_id: str) -> dict[str, Any] | None:
        with self.transaction() as connection:
            row = connection.execute(
                self._case_select_sql()
                + """ WHERE c.public_id=? AND vc.status NOT IN (
                    'verified','verified_with_conditions','insufficient_evidence',
                    'conflicting_evidence','blocked','cancelled','expired','withdrawn'
                ) ORDER BY vc.id DESC LIMIT 1""",
                (candidate_public_id,),
            ).fetchone()
        return _case_public(row) if row else None

    def overview_counts(self) -> dict[str, int]:
        """One aggregate pass for the Data Overview page's 7 Phase 11
        metrics (Step 22) -- computed server-side via `COUNT(*)`, never
        by paging through every case client-side."""

        with self.transaction() as connection:
            awaiting = connection.execute(
                """SELECT COUNT(*) FROM external_dataset_verification_cases
                WHERE status IN ('draft','collecting_evidence')"""
            ).fetchone()[0]
            in_review = connection.execute(
                """SELECT COUNT(*) FROM external_dataset_verification_cases
                WHERE status IN ('needs_review','in_review')"""
            ).fetchone()[0]
            missing_licence = connection.execute(
                """SELECT COUNT(*) FROM external_dataset_verification_cases
                WHERE licence_status IN ('missing','unknown')"""
            ).fetchone()[0]
            conflicting = connection.execute(
                """SELECT COUNT(*) FROM external_dataset_verification_cases
                WHERE licence_status='conflicting' OR conflict_count>0"""
            ).fetchone()[0]
            training_approved = connection.execute(
                """SELECT COUNT(DISTINCT verification_case_id)
                FROM external_dataset_permission_assessments
                WHERE permission_type='training_use'
                AND status IN ('approved','approved_with_conditions')"""
            ).fetchone()[0]
            commercial_approved = connection.execute(
                """SELECT COUNT(DISTINCT verification_case_id)
                FROM external_dataset_permission_assessments
                WHERE permission_type='commercial_use'
                AND status IN ('approved','approved_with_conditions')"""
            ).fetchone()[0]
            expired = connection.execute(
                """SELECT COUNT(*) FROM external_dataset_verification_cases
                WHERE verification_expiry_status IN ('expired','source_changed')"""
            ).fetchone()[0]
        return {
            "candidates_awaiting_verification": awaiting,
            "verification_cases_in_review": in_review,
            "missing_licence_cases": missing_licence,
            "conflicting_evidence_cases": conflicting,
            "training_permission_approved": training_approved,
            "commercial_permission_approved": commercial_approved,
            "verification_expired": expired,
        }

    def list_cases(
        self,
        *,
        status: str | None = None,
        candidate_public_id: str | None = None,
        requested_by_admin_public_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        limit, offset = self.pagination(limit, offset)
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("vc.status=?")
            params.append(status)
        if candidate_public_id:
            clauses.append("c.public_id=?")
            params.append(candidate_public_id)
        if requested_by_admin_public_id:
            clauses.append("vc.requested_by_admin_public_id=?")
            params.append(requested_by_admin_public_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.transaction() as connection:
            rows = connection.execute(
                self._case_select_sql() + f" {where} "  # noqa: S608
                "ORDER BY vc.id DESC LIMIT ? OFFSET ?",
                (*params, limit, offset),
            ).fetchall()
        return [_case_public(row) for row in rows]

    def update_case(self, public_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        if not fields:
            return self.get_case(public_id)
        with self.transaction() as connection:
            self._require_unlocked_case(connection, public_id)
            assignments = ", ".join(f'"{key}"=?' for key in fields)
            connection.execute(
                f'UPDATE external_dataset_verification_cases SET {assignments}, '  # noqa: S608
                "updated_at=CURRENT_TIMESTAMP WHERE public_id=?",
                (*fields.values(), public_id),
            )
        return self.get_case(public_id)

    def lock_case(self, public_id: str, report: dict[str, Any]) -> dict[str, Any]:
        """Sets `locked_at` exactly once -- the one irreversible step
        that ends a case's mutable lifecycle and freezes its immutable
        `report_json`. Refuses to run twice."""

        with self.transaction() as connection:
            self._require_unlocked_case(connection, public_id)
            connection.execute(
                """UPDATE external_dataset_verification_cases
                SET locked_at=CURRENT_TIMESTAMP, report_json=?, updated_at=CURRENT_TIMESTAMP
                WHERE public_id=?""",
                (dumps_json(report), public_id),
            )
        return self.get_case(public_id)

    _REVERIFICATION_FIELDS = (
        "verification_expiry_status", "last_verified_at", "next_reverification_at",
    )

    def update_case_reverification_fields(
        self, public_id: str, fields: dict[str, Any]
    ) -> dict[str, Any]:
        """The second deliberate exception to "immutable once locked"
        (see `add_evidence_snapshot`'s `allow_locked_case`) -- restricted
        to exactly the 3 columns lazy reverification (Step 14) needs to
        update even on an already-finalized case. Any other key raises,
        so this can never become a general-purpose lock bypass."""

        if not fields:
            return self.get_case(public_id)
        unknown = set(fields) - set(self._REVERIFICATION_FIELDS)
        if unknown:
            raise ValidationError(f"not a reverification field: {sorted(unknown)}")
        with self.transaction() as connection:
            current = connection.execute(
                "SELECT id FROM external_dataset_verification_cases WHERE public_id=?", (public_id,)
            ).fetchone()
            if not current:
                raise NotFoundError("verification case not found")
            assignments = ", ".join(f'"{key}"=?' for key in fields)
            connection.execute(
                f'UPDATE external_dataset_verification_cases SET {assignments}, '  # noqa: S608
                "updated_at=CURRENT_TIMESTAMP WHERE public_id=?",
                (*fields.values(), public_id),
            )
        return self.get_case(public_id)

    @staticmethod
    def _case_select_sql() -> str:
        return (
            "SELECT vc.*, c.public_id AS candidate_public_id, "
            "s.public_id AS search_session_public_id "
            "FROM external_dataset_verification_cases vc "
            "JOIN external_dataset_candidates c ON c.id = vc.candidate_id "
            "LEFT JOIN external_dataset_search_sessions s ON s.id = vc.search_session_id"
        )

    # -- evidence snapshots ----------------------------------------------------

    def add_evidence_snapshot(
        self, case_public_id: str, values: dict[str, Any], *, allow_locked_case: bool = False
    ) -> dict[str, Any]:
        """`allow_locked_case=True` is the one deliberate, narrow
        exception to "no further evidence once locked" -- Step 14
        requires reverification to keep working on an already-
        finalized case (licence/terms can change after approval).
        Only `ExternalDatasetReverificationService` may pass it; every
        other caller uses the default, which still refuses once the
        case is locked."""

        public_id = str(uuid4())
        with self.transaction() as connection:
            case_id = (
                self._case_id(connection, case_public_id)
                if allow_locked_case
                else self._require_unlocked_case(connection, case_public_id)
            )
            candidate_id = self._candidate_id(connection, values["candidate_public_id"])
            provider_id = None
            if values.get("provider_public_id"):
                provider_row = connection.execute(
                    "SELECT id FROM external_data_providers WHERE public_id=?",
                    (values["provider_public_id"],),
                ).fetchone()
                provider_id = provider_row["id"] if provider_row else None
            supersedes_id = None
            if values.get("supersedes_evidence_public_id"):
                supersedes_row = connection.execute(
                    "SELECT id FROM external_dataset_evidence_snapshots WHERE public_id=?",
                    (values["supersedes_evidence_public_id"],),
                ).fetchone()
                if not supersedes_row:
                    raise NotFoundError("superseded evidence snapshot not found")
                supersedes_id = supersedes_row["id"]
            connection.execute(
                """INSERT INTO external_dataset_evidence_snapshots(
                public_id, verification_case_id, candidate_id, provider_id, evidence_type,
                authority_level, source_url, resolved_url, source_domain, source_title,
                content_type, language, retrieval_status, http_status, effective_date,
                last_modified_at, content_text, content_excerpt, content_checksum,
                response_headers_json, metadata_json, redaction_summary_json, size_bytes,
                supersedes_evidence_id, ocr_derived, warnings_json, created_by_admin_public_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    case_id,
                    candidate_id,
                    provider_id,
                    values["evidence_type"],
                    values["authority_level"],
                    values.get("source_url"),
                    values.get("resolved_url"),
                    values.get("source_domain"),
                    values.get("source_title"),
                    values["content_type"],
                    values.get("language"),
                    values.get("retrieval_status", "success"),
                    values.get("http_status"),
                    values.get("effective_date"),
                    values.get("last_modified_at"),
                    values.get("content_text", ""),
                    values.get("content_excerpt", ""),
                    values["content_checksum"],
                    dumps_json(values.get("response_headers", {})),
                    dumps_json(values.get("metadata", {})),
                    dumps_json(values.get("redaction_summary", {})),
                    values.get("size_bytes", 0),
                    supersedes_id,
                    int(bool(values.get("ocr_derived", False))),
                    dumps_json(values.get("warnings", [])),
                    values["created_by_admin_public_id"],
                ),
            )
            if supersedes_id is not None:
                connection.execute(
                    "UPDATE external_dataset_evidence_snapshots SET is_current=0 WHERE id=?",
                    (supersedes_id,),
                )
        return self.get_evidence_snapshot(public_id)

    def get_evidence_snapshot(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._evidence_snapshot_select_sql() + " WHERE es.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("evidence snapshot not found")
        return _evidence_snapshot_public(row)

    def list_evidence_snapshots(
        self,
        case_public_id: str,
        *,
        evidence_type: str | None = None,
        current_only: bool = False,
    ) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            case_id = self._case_id(connection, case_public_id)
            clauses = ["es.verification_case_id=?"]
            params: list[Any] = [case_id]
            if evidence_type:
                clauses.append("es.evidence_type=?")
                params.append(evidence_type)
            if current_only:
                clauses.append("es.is_current=1")
            rows = connection.execute(
                self._evidence_snapshot_select_sql()
                + f" WHERE {' AND '.join(clauses)} ORDER BY es.id",  # noqa: S608
                params,
            ).fetchall()
        return [_evidence_snapshot_public(row) for row in rows]

    @staticmethod
    def _evidence_snapshot_select_sql() -> str:
        return (
            "SELECT es.*, vc.public_id AS verification_case_public_id, "
            "c.public_id AS candidate_public_id, p.public_id AS provider_public_id, "
            "sup.public_id AS supersedes_evidence_public_id "
            "FROM external_dataset_evidence_snapshots es "
            "JOIN external_dataset_verification_cases vc ON vc.id = es.verification_case_id "
            "JOIN external_dataset_candidates c ON c.id = es.candidate_id "
            "LEFT JOIN external_data_providers p ON p.id = es.provider_id "
            "LEFT JOIN external_dataset_evidence_snapshots sup "
            "ON sup.id = es.supersedes_evidence_id"
        )

    # -- evidence links (polymorphic) ------------------------------------------

    def add_evidence_link(
        self,
        evidence_snapshot_public_id: str,
        *,
        linked_entity_type: str,
        linked_entity_id: int,
        link_role: str = "supports",
    ) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            snapshot_row = connection.execute(
                "SELECT id FROM external_dataset_evidence_snapshots WHERE public_id=?",
                (evidence_snapshot_public_id,),
            ).fetchone()
            if not snapshot_row:
                raise NotFoundError("evidence snapshot not found")
            connection.execute(
                """INSERT INTO external_dataset_evidence_links(
                public_id, evidence_snapshot_id, linked_entity_type, linked_entity_id, link_role)
                VALUES (?,?,?,?,?)
                ON CONFLICT(evidence_snapshot_id, linked_entity_type, linked_entity_id, link_role)
                DO NOTHING""",
                (public_id, snapshot_row["id"], linked_entity_type, linked_entity_id, link_role),
            )
            row = connection.execute(
                self._evidence_link_select_sql()
                + " WHERE el.evidence_snapshot_id=? AND el.linked_entity_type=? "
                "AND el.linked_entity_id=? AND el.link_role=?",
                (snapshot_row["id"], linked_entity_type, linked_entity_id, link_role),
            ).fetchone()
        return _evidence_link_public(row)

    def list_evidence_links_for_entity(
        self, linked_entity_type: str, linked_entity_id: int
    ) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            rows = connection.execute(
                self._evidence_link_select_sql()
                + " WHERE el.linked_entity_type=? AND el.linked_entity_id=? ORDER BY el.id",
                (linked_entity_type, linked_entity_id),
            ).fetchall()
        return [_evidence_link_public(row) for row in rows]

    def list_evidence_links_for_snapshot(
        self, evidence_snapshot_public_id: str
    ) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            snapshot_row = connection.execute(
                "SELECT id FROM external_dataset_evidence_snapshots WHERE public_id=?",
                (evidence_snapshot_public_id,),
            ).fetchone()
            if not snapshot_row:
                raise NotFoundError("evidence snapshot not found")
            rows = connection.execute(
                self._evidence_link_select_sql()
                + " WHERE el.evidence_snapshot_id=? ORDER BY el.id",
                (snapshot_row["id"],),
            ).fetchall()
        return [_evidence_link_public(row) for row in rows]

    @staticmethod
    def _evidence_link_select_sql() -> str:
        return (
            "SELECT el.*, es.public_id AS evidence_snapshot_public_id "
            "FROM external_dataset_evidence_links el "
            "JOIN external_dataset_evidence_snapshots es ON es.id = el.evidence_snapshot_id"
        )

    # -- identity checks --------------------------------------------------------

    def add_identity_check(self, case_public_id: str, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            case_id = self._require_unlocked_case(connection, case_public_id)
            candidate_id = self._candidate_id(connection, values["candidate_public_id"])
            evidence_snapshot_id = None
            if values.get("evidence_snapshot_public_id"):
                evidence_row = connection.execute(
                    "SELECT id FROM external_dataset_evidence_snapshots WHERE public_id=?",
                    (values["evidence_snapshot_public_id"],),
                ).fetchone()
                evidence_snapshot_id = evidence_row["id"] if evidence_row else None
            connection.execute(
                """INSERT INTO external_dataset_identity_checks(
                public_id, verification_case_id, candidate_id, signal_type, expected_value,
                observed_value, matched, reason, evidence_snapshot_id)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    case_id,
                    candidate_id,
                    values["signal_type"],
                    values.get("expected_value"),
                    values.get("observed_value"),
                    int(bool(values.get("matched", False))),
                    values.get("reason", ""),
                    evidence_snapshot_id,
                ),
            )
        return self.get_identity_check(public_id)

    def get_identity_check(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._identity_check_select_sql() + " WHERE ic.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("identity check not found")
        return _identity_check_public(row)

    def list_identity_checks(self, case_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            case_id = self._case_id(connection, case_public_id)
            rows = connection.execute(
                self._identity_check_select_sql()
                + " WHERE ic.verification_case_id=? ORDER BY ic.id",
                (case_id,),
            ).fetchall()
        return [_identity_check_public(row) for row in rows]

    @staticmethod
    def _identity_check_select_sql() -> str:
        return (
            "SELECT ic.*, vc.public_id AS verification_case_public_id, "
            "c.public_id AS candidate_public_id, "
            "es.public_id AS evidence_snapshot_public_id "
            "FROM external_dataset_identity_checks ic "
            "JOIN external_dataset_verification_cases vc ON vc.id = ic.verification_case_id "
            "JOIN external_dataset_candidates c ON c.id = ic.candidate_id "
            "LEFT JOIN external_dataset_evidence_snapshots es "
            "ON es.id = ic.evidence_snapshot_id"
        )

    # -- permission assessments ---------------------------------------------------

    def assess_permission(
        self, case_public_id: str, permission_type: str, values: dict[str, Any]
    ) -> dict[str, Any]:
        """Automated-only path: raises `ValidationError` if `values`
        tries to write one of the 4 admin-only statuses -- only
        `review_permission()` may ever write those."""

        status = values.get("status", "unknown")
        if status in ADMIN_ONLY_PERMISSION_STATUSES:
            raise ValidationError(
                "automated permission assessment cannot set an admin-only status"
            )
        public_id = str(uuid4())
        with self.transaction() as connection:
            case_id = self._require_unlocked_case(connection, case_public_id)
            candidate_id = self._candidate_id(connection, values["candidate_public_id"])
            existing = connection.execute(
                """SELECT public_id FROM external_dataset_permission_assessments
                WHERE verification_case_id=? AND permission_type=?""",
                (case_id, permission_type),
            ).fetchone()
            columns = {
                "status": status,
                "decision_basis": values.get("decision_basis", ""),
                "evidence_snapshot_ids_json": dumps_json(values.get("evidence_snapshot_ids", [])),
                "conditions_json": dumps_json(values.get("conditions", {})),
                "warnings_json": dumps_json(values.get("warnings", [])),
                "blocking_reasons_json": dumps_json(values.get("blocking_reasons", [])),
                "assessed_by": values.get("assessed_by", "system"),
            }
            if existing:
                assignments = ", ".join(f'"{key}"=?' for key in columns)
                connection.execute(
                    f'UPDATE external_dataset_permission_assessments SET {assignments}, '  # noqa: S608
                    "assessed_at=CURRENT_TIMESTAMP, reviewed_by=NULL, reviewed_at=NULL, "
                    "reason=NULL, updated_at=CURRENT_TIMESTAMP "
                    "WHERE verification_case_id=? AND permission_type=?",
                    (*columns.values(), case_id, permission_type),
                )
                public_id = existing["public_id"]
            else:
                connection.execute(
                    """INSERT INTO external_dataset_permission_assessments(
                    public_id, verification_case_id, candidate_id, permission_type, status,
                    decision_basis, evidence_snapshot_ids_json, conditions_json, warnings_json,
                    blocking_reasons_json, assessed_by)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (public_id, case_id, candidate_id, permission_type, *columns.values()),
                )
        return self.get_permission_assessment(case_public_id, permission_type)

    def review_permission(
        self,
        case_public_id: str,
        permission_type: str,
        *,
        status: str,
        reviewed_by: str,
        reason: str,
        conditions: dict[str, Any] | None = None,
        evidence_checksum_set: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """The only method that may write one of the 4 admin-only
        statuses -- requires a non-empty `reason` and always writes a
        matching append-only `external_dataset_verification_reviews`
        row with the evidence checksum set captured at review time
        (for later stale-detection)."""

        if status not in ADMIN_ONLY_PERMISSION_STATUSES:
            raise ValidationError(f"'{status}' is not an admin-only permission status")
        if not reason or not reason.strip():
            raise ValidationError("a non-empty review reason is required")
        checksum_set = evidence_checksum_set or {}
        with self.transaction() as connection:
            case_id = self._require_unlocked_case(connection, case_public_id)
            existing = connection.execute(
                """SELECT id, public_id, candidate_id FROM external_dataset_permission_assessments
                WHERE verification_case_id=? AND permission_type=?""",
                (case_id, permission_type),
            ).fetchone()
            if not existing:
                raise NotFoundError(
                    "permission assessment must exist (run .assess() first) before review"
                )
            connection.execute(
                """UPDATE external_dataset_permission_assessments SET status=?,
                reviewed_by=?, reviewed_at=CURRENT_TIMESTAMP, reason=?,
                conditions_json=?, evidence_checksum_set_json=?, updated_at=CURRENT_TIMESTAMP
                WHERE id=?""",
                (
                    status,
                    reviewed_by,
                    reason,
                    dumps_json(conditions or {}),
                    dumps_json(checksum_set),
                    existing["id"],
                ),
            )
            connection.execute(
                """INSERT INTO external_dataset_verification_reviews(
                public_id, verification_case_id, permission_assessment_id, permission_type,
                decision, reason, conditions_json, reviewer_admin_public_id,
                evidence_checksum_set_json)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    str(uuid4()),
                    case_id,
                    existing["id"],
                    permission_type,
                    status,
                    reason,
                    dumps_json(conditions or {}),
                    reviewed_by,
                    dumps_json(checksum_set),
                ),
            )
        return self.get_permission_assessment(case_public_id, permission_type)

    def demote_permission_status(
        self, case_public_id: str, permission_type: str, *, new_status: str, reason: str
    ) -> dict[str, Any]:
        """The third deliberate exception to "immutable once locked"
        (see `add_evidence_snapshot`'s `allow_locked_case`) -- Step 14
        requires a prior admin approval to become review-required again
        when the underlying evidence changes, even on an already-
        finalized case. `new_status` must never be an admin-only status
        (an automatic demotion is a factual safety response to changed
        evidence, never itself a rights decision -- only `.review()`
        may grant/deny rights) and callers are responsible for only
        ever demoting to a strictly more conservative status, never
        promoting."""

        if new_status in ADMIN_ONLY_PERMISSION_STATUSES:
            raise ValidationError("reverification demotion cannot set an admin-only status")
        with self.transaction() as connection:
            case_id = self._case_id(connection, case_public_id)
            existing = connection.execute(
                """SELECT id FROM external_dataset_permission_assessments
                WHERE verification_case_id=? AND permission_type=?""",
                (case_id, permission_type),
            ).fetchone()
            if not existing:
                raise NotFoundError("permission assessment not found")
            connection.execute(
                """UPDATE external_dataset_permission_assessments SET status=?,
                decision_basis=decision_basis || ' | reverification: ' || ?,
                updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                (new_status, reason, existing["id"]),
            )
        return self.get_permission_assessment(case_public_id, permission_type)

    def get_permission_assessment(
        self, case_public_id: str, permission_type: str
    ) -> dict[str, Any] | None:
        with self.transaction() as connection:
            case_id = self._case_id(connection, case_public_id)
            row = connection.execute(
                self._permission_assessment_select_sql()
                + " WHERE pa.verification_case_id=? AND pa.permission_type=?",
                (case_id, permission_type),
            ).fetchone()
        return _permission_assessment_public(row) if row else None

    def list_permission_assessments(self, case_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            case_id = self._case_id(connection, case_public_id)
            rows = connection.execute(
                self._permission_assessment_select_sql()
                + " WHERE pa.verification_case_id=? ORDER BY pa.id",
                (case_id,),
            ).fetchall()
        return [_permission_assessment_public(row) for row in rows]

    @staticmethod
    def _permission_assessment_select_sql() -> str:
        return (
            "SELECT pa.*, vc.public_id AS verification_case_public_id, "
            "c.public_id AS candidate_public_id "
            "FROM external_dataset_permission_assessments pa "
            "JOIN external_dataset_verification_cases vc ON vc.id = pa.verification_case_id "
            "JOIN external_dataset_candidates c ON c.id = pa.candidate_id"
        )

    # -- verification reviews (append-only, read-only here) ------------------------

    def list_reviews(self, case_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            case_id = self._case_id(connection, case_public_id)
            rows = connection.execute(
                self._review_select_sql() + " WHERE r.verification_case_id=? ORDER BY r.id",
                (case_id,),
            ).fetchall()
        return [_review_public(row) for row in rows]

    @staticmethod
    def _review_select_sql() -> str:
        return (
            "SELECT r.*, vc.public_id AS verification_case_public_id, "
            "pa.public_id AS permission_assessment_public_id "
            "FROM external_dataset_verification_reviews r "
            "JOIN external_dataset_verification_cases vc ON vc.id = r.verification_case_id "
            "LEFT JOIN external_dataset_permission_assessments pa "
            "ON pa.id = r.permission_assessment_id"
        )

    # -- verification events (append-only) ------------------------------------------

    def record_event(self, case_public_id: str, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            case_id = self._case_id(connection, case_public_id)
            connection.execute(
                """INSERT INTO external_dataset_verification_events(
                public_id, verification_case_id, event_type, summary, metadata_json,
                conflict_type, conflict_severity, evidence_ids_json, resolution_status,
                resolution_reason, resolved_by_admin_public_id, resolved_at,
                performed_by_admin_public_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    case_id,
                    values["event_type"],
                    values.get("summary", ""),
                    dumps_json(values.get("metadata", {})),
                    values.get("conflict_type"),
                    values.get("conflict_severity"),
                    dumps_json(values.get("evidence_ids", [])),
                    values.get("resolution_status"),
                    values.get("resolution_reason"),
                    values.get("resolved_by_admin_public_id"),
                    values.get("resolved_at"),
                    values["performed_by_admin_public_id"],
                ),
            )
        return self.get_event(public_id)

    def get_event(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._event_select_sql() + " WHERE e.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("verification event not found")
        return _event_public(row)

    def list_events(self, case_public_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            case_id = self._case_id(connection, case_public_id)
            rows = connection.execute(
                self._event_select_sql()
                + " WHERE e.verification_case_id=? ORDER BY e.id DESC LIMIT ?",
                (case_id, limit),
            ).fetchall()
        return [_event_public(row) for row in rows]

    def list_conflict_events(self, case_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            case_id = self._case_id(connection, case_public_id)
            rows = connection.execute(
                self._event_select_sql()
                + " WHERE e.verification_case_id=? AND e.event_type=? ORDER BY e.id",
                (case_id, "conflict_detected"),
            ).fetchall()
        return [_event_public(row) for row in rows]

    @staticmethod
    def _event_select_sql() -> str:
        return (
            "SELECT e.*, vc.public_id AS verification_case_public_id "
            "FROM external_dataset_verification_events e "
            "JOIN external_dataset_verification_cases vc ON vc.id = e.verification_case_id"
        )

    # -- withdrawal notices (append-only) --------------------------------------------

    def record_withdrawal_notice(
        self, case_public_id: str, values: dict[str, Any]
    ) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            case_id = self._case_id(connection, case_public_id)
            candidate_id = self._candidate_id(connection, values["candidate_public_id"])
            connection.execute(
                """INSERT INTO external_dataset_withdrawal_notices(
                public_id, verification_case_id, candidate_id, notice_type, source_url,
                notice_text, effective_at, recorded_by_admin_public_id, impact_status,
                impact_summary_json)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    case_id,
                    candidate_id,
                    values["notice_type"],
                    values.get("source_url"),
                    values.get("notice_text", ""),
                    values.get("effective_at"),
                    values["recorded_by_admin_public_id"],
                    values.get("impact_status", "pending_assessment"),
                    dumps_json(values.get("impact_summary", {})),
                ),
            )
        return self.get_withdrawal_notice(public_id)

    def get_withdrawal_notice(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._withdrawal_notice_select_sql() + " WHERE w.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("withdrawal notice not found")
        return _withdrawal_notice_public(row)

    def list_withdrawal_notices(self, case_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            case_id = self._case_id(connection, case_public_id)
            rows = connection.execute(
                self._withdrawal_notice_select_sql()
                + " WHERE w.verification_case_id=? ORDER BY w.id DESC",
                (case_id,),
            ).fetchall()
        return [_withdrawal_notice_public(row) for row in rows]

    @staticmethod
    def _withdrawal_notice_select_sql() -> str:
        return (
            "SELECT w.*, vc.public_id AS verification_case_public_id, "
            "c.public_id AS candidate_public_id "
            "FROM external_dataset_withdrawal_notices w "
            "JOIN external_dataset_verification_cases vc ON vc.id = w.verification_case_id "
            "JOIN external_dataset_candidates c ON c.id = w.candidate_id"
        )

    # -- upstream sources -------------------------------------------------------------

    def add_upstream_source(self, case_public_id: str, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            case_id = self._require_unlocked_case(connection, case_public_id)
            candidate_id = self._candidate_id(connection, values["candidate_public_id"])
            connection.execute(
                """INSERT INTO external_dataset_upstream_sources(
                public_id, verification_case_id, candidate_id, upstream_name, upstream_url,
                upstream_organization, upstream_licence, upstream_terms,
                upstream_permission_status, relationship_type, coverage_notes,
                verification_status, created_by_admin_public_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    case_id,
                    candidate_id,
                    values["upstream_name"],
                    values.get("upstream_url"),
                    values.get("upstream_organization"),
                    values.get("upstream_licence"),
                    values.get("upstream_terms"),
                    values.get("upstream_permission_status", "unknown"),
                    values.get("relationship_type", "unknown"),
                    values.get("coverage_notes", ""),
                    values.get("verification_status", "not_verified"),
                    values["created_by_admin_public_id"],
                ),
            )
        return self.get_upstream_source(public_id)

    def update_upstream_source(self, public_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        if not fields:
            return self.get_upstream_source(public_id)
        with self.transaction() as connection:
            row = connection.execute(
                """SELECT us.id, vc.public_id AS case_public_id, vc.locked_at
                FROM external_dataset_upstream_sources us
                JOIN external_dataset_verification_cases vc
                ON vc.id = us.verification_case_id
                WHERE us.public_id=?""",
                (public_id,),
            ).fetchone()
            if not row:
                raise NotFoundError("upstream source not found")
            if row["locked_at"] is not None:
                raise ValidationError("verification case is finalized and locked")
            assignments = ", ".join(f'"{key}"=?' for key in fields)
            connection.execute(
                f'UPDATE external_dataset_upstream_sources SET {assignments}, '  # noqa: S608
                "updated_at=CURRENT_TIMESTAMP WHERE public_id=?",
                (*fields.values(), public_id),
            )
        return self.get_upstream_source(public_id)

    def get_upstream_source(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._upstream_source_select_sql() + " WHERE us.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("upstream source not found")
        return _upstream_source_public(row)

    def list_upstream_sources(self, case_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            case_id = self._case_id(connection, case_public_id)
            rows = connection.execute(
                self._upstream_source_select_sql()
                + " WHERE us.verification_case_id=? ORDER BY us.id",
                (case_id,),
            ).fetchall()
        return [_upstream_source_public(row) for row in rows]

    def unresolved_upstream_exists(self, case_public_id: str) -> bool:
        with self.transaction() as connection:
            case_id = self._case_id(connection, case_public_id)
            row = connection.execute(
                """SELECT 1 FROM external_dataset_upstream_sources
                WHERE verification_case_id=? AND verification_status != 'verified' LIMIT 1""",
                (case_id,),
            ).fetchone()
        return row is not None

    @staticmethod
    def _upstream_source_select_sql() -> str:
        return (
            "SELECT us.*, vc.public_id AS verification_case_public_id, "
            "c.public_id AS candidate_public_id "
            "FROM external_dataset_upstream_sources us "
            "JOIN external_dataset_verification_cases vc ON vc.id = us.verification_case_id "
            "JOIN external_dataset_candidates c ON c.id = us.candidate_id"
        )
