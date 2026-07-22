"""SQL repository for Phase 6 quality, versioning, build, and export data."""

from __future__ import annotations

import sqlite3
from typing import Any

from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError, ValidationError
from backend.database.repositories.dataset_admin import public_row


def _public(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    internal_ids = {
        "id",
        "dataset_record_id",
        "quality_assessment_id",
        "dataset_version_id",
        "build_job_id",
    }
    for key in list(data):
        if key in internal_ids:
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    return data


class DatasetQualityRepository(BaseRepository):
    """Parameterized SQL operations used by Phase 6 services."""

    def record(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            """SELECT r.*,s.public_id AS source_public_id,s.source_type,s.licence_status,
            s.name AS source_name,s.metadata_json AS source_metadata_json
            FROM dataset_records r LEFT JOIN dataset_sources s ON s.id=r.source_id
            WHERE r.public_id=?""",
            (public_id,),
        ).fetchone()
        if not row:
            raise NotFoundError("dataset record not found")
        return row

    def latest_assessment(
        self, connection: sqlite3.Connection, record_public_id: str
    ) -> sqlite3.Row | None:
        row = self.record(connection, record_public_id)
        return connection.execute(
            """SELECT * FROM dataset_quality_assessments
            WHERE dataset_record_id=? ORDER BY created_at DESC,id DESC LIMIT 1""",
            (row["id"],),
        ).fetchone()

    def assessment_by_public_id(
        self, connection: sqlite3.Connection, public_id: str
    ) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM dataset_quality_assessments WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("quality assessment not found")
        return row

    def insert_assessment(
        self,
        connection: sqlite3.Connection,
        *,
        public_id: str,
        record_id: int,
        ruleset: str,
        scores: dict[str, float],
        readiness: str,
        summary: dict[str, Any],
        assessed_by: str,
        issues: list[dict[str, Any]],
    ) -> str:
        connection.execute(
            """INSERT INTO dataset_quality_assessments(public_id,dataset_record_id,
            assessment_version,overall_score,completeness_score,structure_score,
            language_score,text_quality_score,duplication_score,safety_score,provenance_score,
            readiness_status,summary_json,assessed_by)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                record_id,
                ruleset,
                scores["overall"],
                scores["completeness"],
                scores["structure"],
                scores["language"],
                scores["text_quality"],
                scores["duplication"],
                scores["safety"],
                scores["provenance"],
                readiness,
                dumps_json(summary),
                assessed_by,
            ),
        )
        assessment_id = connection.execute(
            "SELECT id FROM dataset_quality_assessments WHERE public_id=?", (public_id,)
        ).fetchone()["id"]
        for issue in issues:
            connection.execute(
                """INSERT INTO dataset_quality_issues(public_id,quality_assessment_id,
                issue_code,severity,field_name,message,metadata_json)
                VALUES (?,?,?,?,?,?,?)""",
                (
                    issue["public_id"],
                    assessment_id,
                    issue["issue_code"],
                    issue["severity"],
                    issue.get("field_name"),
                    issue["message"],
                    dumps_json(issue.get("metadata", {})),
                ),
            )
        return public_id

    def assessment_issues(
        self, connection: sqlite3.Connection, assessment_public_id: str
    ) -> list[dict[str, Any]]:
        assessment = self.assessment_by_public_id(connection, assessment_public_id)
        rows = connection.execute(
            """SELECT public_id,issue_code,severity,field_name,message,metadata_json,created_at
            FROM dataset_quality_issues WHERE quality_assessment_id=?
            ORDER BY CASE severity WHEN 'blocking' THEN 1 WHEN 'error' THEN 2
            WHEN 'warning' THEN 3 ELSE 4 END,id""",
            (assessment["id"],),
        ).fetchall()
        return [_public(row) for row in rows]

    def selectable_records(
        self, connection: sqlite3.Connection, filters: dict[str, Any], limit: int
    ) -> list[sqlite3.Row]:
        clauses = [
            "r.status='approved'",
            "(s.licence_status IS NULL OR s.licence_status<>'rejected')",
        ]
        params: list[Any] = []
        mapping = {
            "source_public_id": "s.public_id",
            "source_type": "s.source_type",
            "language": "r.language",
            "record_type": "r.record_type",
        }
        for key, column in mapping.items():
            if filters.get(key):
                clauses.append(f"{column}=?")
                params.append(filters[key])
        rows = connection.execute(
            f"""SELECT r.*,s.public_id AS source_public_id,s.source_type,s.licence_status,
            s.name AS source_name FROM dataset_records r
            LEFT JOIN dataset_sources s ON s.id=r.source_id
            WHERE {" AND ".join(clauses)}
            ORDER BY r.content_hash,r.public_id LIMIT ?""",
            (*params, limit),
        ).fetchall()
        return list(rows)

    def create_version(
        self,
        connection: sqlite3.Connection,
        *,
        public_id: str,
        name: str,
        version: str,
        description: str | None,
        parent_id: int | None = None,
    ) -> str:
        connection.execute(
            """INSERT INTO dataset_versions(public_id,name,version,description,status,
            checksum_sha256,parent_dataset_version_id)
            VALUES (?,?,?,?,?,?,?)""",
            (public_id, name, version, description, "draft", "pending", parent_id),
        )
        return public_id

    def version(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM dataset_versions WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("dataset version not found")
        return row

    def build(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            """SELECT b.*,v.public_id AS dataset_version_public_id FROM dataset_build_jobs b
            JOIN dataset_versions v ON v.id=b.dataset_version_id WHERE b.public_id=?""",
            (public_id,),
        ).fetchone()
        if not row:
            raise NotFoundError("dataset build job not found")
        return row

    def create_build(
        self,
        connection: sqlite3.Connection,
        *,
        public_id: str,
        version_id: int,
        name: str,
        filters: dict[str, Any],
        split: dict[str, Any],
        created_by: str,
    ) -> str:
        connection.execute(
            """INSERT INTO dataset_build_jobs(public_id,dataset_version_id,name,status,
            selection_filters_json,split_configuration_json,deduplication_configuration_json,
            created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?,?)""",
            (
                public_id,
                version_id,
                name,
                "draft",
                dumps_json(filters),
                dumps_json(split),
                "{}",
                created_by,
            ),
        )
        self.add_build_event(connection, public_id, "build_created", None, "draft", None, {})
        return public_id

    def add_build_event(
        self,
        connection: sqlite3.Connection,
        build_public_id: str,
        event_type: str,
        previous: str | None,
        new: str | None,
        message: str | None,
        metadata: dict[str, Any],
    ) -> None:
        build = self.build(connection, build_public_id)
        connection.execute(
            """INSERT INTO dataset_build_events(build_job_id,event_type,previous_status,
            new_status,message,metadata_json) VALUES (?,?,?,?,?,?)""",
            (build["id"], event_type, previous, new, message, dumps_json(metadata)),
        )

    def build_events(
        self, connection: sqlite3.Connection, build_public_id: str
    ) -> list[dict[str, Any]]:
        build = self.build(connection, build_public_id)
        rows = connection.execute(
            """SELECT event_type,previous_status,new_status,message,metadata_json,created_at
            FROM dataset_build_events WHERE build_job_id=? ORDER BY created_at,id""",
            (build["id"],),
        ).fetchall()
        return [_public(row) for row in rows]

    def list_versions(self, connection: sqlite3.Connection, page: int, page_size: int):
        total = connection.execute("SELECT COUNT(*) FROM dataset_versions").fetchone()[0]
        rows = connection.execute(
            "SELECT * FROM dataset_versions ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?",
            (page_size, (page - 1) * page_size),
        ).fetchall()
        return [_public(row) for row in rows], total

    def list_builds(self, connection: sqlite3.Connection, page: int, page_size: int):
        total = connection.execute("SELECT COUNT(*) FROM dataset_build_jobs").fetchone()[0]
        rows = connection.execute(
            """SELECT b.*,v.public_id AS dataset_version_public_id FROM dataset_build_jobs b
            JOIN dataset_versions v ON v.id=b.dataset_version_id
            ORDER BY b.created_at DESC,b.id DESC LIMIT ? OFFSET ?""",
            (page_size, (page - 1) * page_size),
        ).fetchall()
        return [_public(row) for row in rows], total

    def list_exports(
        self, connection: sqlite3.Connection, version_public_id: str
    ) -> list[dict[str, Any]]:
        version = self.version(connection, version_public_id)
        rows = connection.execute(
            """SELECT public_id,export_format,status,safe_name,record_count,checksum_sha256,
            file_manifest_json,created_at,completed_at FROM dataset_exports
            WHERE dataset_version_id=? ORDER BY created_at DESC,id DESC""",
            (version["id"],),
        ).fetchall()
        return [_public(row) for row in rows]

    def export(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            """SELECT e.*,v.public_id AS dataset_version_public_id FROM dataset_exports e
            JOIN dataset_versions v ON v.id=e.dataset_version_id WHERE e.public_id=?""",
            (public_id,),
        ).fetchone()
        if not row:
            raise NotFoundError("dataset export not found")
        return row

    def public_record(self, row: sqlite3.Row) -> dict[str, Any]:
        return public_row(row)

    def require_draft_version(self, row: sqlite3.Row) -> None:
        if row["status"] != "draft":
            raise ValidationError("only draft dataset versions can be changed")
