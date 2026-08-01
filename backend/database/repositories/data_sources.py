"""Repository for the Phase 2 (Data Studio) Source, Rights & Usage
Registry: ``data_sources``, ``source_rights``,
``source_verification_events``, ``source_usage_decisions``, and
``source_record_links``. See
``docs/data_studio/phase2_source_rights_registry_plan.md`` for why this
is a new, general-purpose registry rather than an extension of Phase
19/20's corpus-pipeline-scoped ``corpus_source_registries``/
``corpus_source_licences``.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from uuid import uuid4

from backend.core.json_utils import loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError

INTERNAL = {"id", "data_source_id"}


def public_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("data source registry row not found")
    data = dict(row)
    for key in list(data):
        if key in INTERNAL:
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    return data


class DataSourceRepository(BaseRepository):
    """Defaults to ``immediate=True``: every method here reads the current
    row and then conditionally writes within the same transaction, and none
    of its callers in the service layer nest a second ``transaction()``
    inside an already-open one (see ``BaseRepository.transaction`` for why
    this matters under concurrent access)."""

    @contextmanager
    def transaction(self, *, immediate: bool = True) -> Iterator[sqlite3.Connection]:
        with super().transaction(immediate=immediate) as connection:
            yield connection

    # --- data_sources ---------------------------------------------------

    def create_source(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO data_sources(
            public_id,source_code,title,source_type,owner_name,author_name,publisher_name,
            organization_name,source_url,source_reference,publication_year,edition,
            language_codes_json,description,knowledge_risk,fact_dependency,
            verification_required,independent_reviewer_required,
            internal_rag_policy_allows_unknown_rights,acquired_at,created_by_admin_public_id,
            status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["source_code"],
                values["title"],
                values["source_type"],
                values.get("owner_name"),
                values.get("author_name"),
                values.get("publisher_name"),
                values.get("organization_name"),
                values.get("source_url"),
                values.get("source_reference"),
                values.get("publication_year"),
                values.get("edition"),
                values.get("language_codes_json", "[]"),
                values.get("description", ""),
                values.get("knowledge_risk", "unknown"),
                values.get("fact_dependency", "unknown"),
                1 if values.get("verification_required") else 0,
                1 if values.get("independent_reviewer_required") else 0,
                1 if values.get("internal_rag_policy_allows_unknown_rights") else 0,
                values.get("acquired_at"),
                values["created_by_admin_public_id"],
                values.get("status", "draft"),
            ),
        )
        return public_id

    def source(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM data_sources WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("data source not found")
        return row

    def source_by_id(self, connection: sqlite3.Connection, source_id: int) -> sqlite3.Row:
        row = connection.execute("SELECT * FROM data_sources WHERE id=?", (source_id,)).fetchone()
        if not row:
            raise NotFoundError("data source not found")
        return row

    def source_by_code(
        self, connection: sqlite3.Connection, source_code: str
    ) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT * FROM data_sources WHERE source_code=?", (source_code,)
        ).fetchone()

    def list_sources(
        self,
        connection: sqlite3.Connection,
        *,
        status: str | None = None,
        source_type: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[sqlite3.Row], int]:
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status=?")
            params.append(status)
        if source_type:
            clauses.append("source_type=?")
            params.append(source_type)
        if search:
            clauses.append(
                "(title LIKE ? OR owner_name LIKE ? OR publisher_name LIKE ? "
                "OR source_code LIKE ? OR source_url LIKE ?)"
            )
            like = f"%{search}%"
            params.extend([like, like, like, like, like])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        total = connection.execute(
            f"SELECT COUNT(*) FROM data_sources {where}",
            params,  # noqa: S608
        ).fetchone()[0]
        rows = connection.execute(
            f"SELECT * FROM data_sources {where} "  # noqa: S608
            "ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
        return rows, total

    def update_source(
        self, connection: sqlite3.Connection, source_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE data_sources SET {columns}, updated_at=CURRENT_TIMESTAMP WHERE id=?",  # noqa: S608
            (*fields.values(), source_id),
        )

    # --- source_rights ---------------------------------------------------

    def rights_for_source(
        self, connection: sqlite3.Connection, source_id: int
    ) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT * FROM source_rights WHERE data_source_id=?", (source_id,)
        ).fetchone()

    def create_rights(
        self, connection: sqlite3.Connection, source_id: int, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO source_rights(
            public_id,data_source_id,rights_status,license_name,license_identifier,license_url,
            copyright_owner,permission_reference,permission_document_reference,
            permission_received_at,permission_expires_at,attribution_required,attribution_text,
            share_alike_required,modification_allowed,commercial_use_allowed,rag_use_allowed,
            training_use_allowed,evaluation_use_allowed,public_export_allowed,
            redistribution_allowed,internal_only,verification_status,review_notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                source_id,
                values.get("rights_status", "unknown"),
                values.get("license_name"),
                values.get("license_identifier"),
                values.get("license_url"),
                values.get("copyright_owner"),
                values.get("permission_reference"),
                values.get("permission_document_reference"),
                values.get("permission_received_at"),
                values.get("permission_expires_at"),
                1 if values.get("attribution_required") else 0,
                values.get("attribution_text"),
                1 if values.get("share_alike_required") else 0,
                1 if values.get("modification_allowed") else 0,
                1 if values.get("commercial_use_allowed") else 0,
                1 if values.get("rag_use_allowed") else 0,
                1 if values.get("training_use_allowed") else 0,
                1 if values.get("evaluation_use_allowed") else 0,
                1 if values.get("public_export_allowed") else 0,
                1 if values.get("redistribution_allowed") else 0,
                1 if values.get("internal_only") else 0,
                values.get("verification_status", "unverified"),
                values.get("review_notes", ""),
            ),
        )
        return public_id

    def update_rights(
        self, connection: sqlite3.Connection, rights_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE source_rights SET {columns}, updated_at=CURRENT_TIMESTAMP WHERE id=?",  # noqa: S608
            (*fields.values(), rights_id),
        )

    # --- source_verification_events (append-only) ------------------------

    def add_verification_event(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO source_verification_events(
            public_id,data_source_id,action,verification_status_after,
            performed_by_admin_public_id,evidence_reference,notes)
            VALUES (?,?,?,?,?,?,?)""",
            (
                public_id,
                values["data_source_id"],
                values["action"],
                values["verification_status_after"],
                values["performed_by_admin_public_id"],
                values.get("evidence_reference"),
                values.get("notes", ""),
            ),
        )
        return public_id

    def list_verification_events(
        self, connection: sqlite3.Connection, source_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM source_verification_events WHERE data_source_id=? "
            "ORDER BY created_at DESC, id DESC",
            (source_id,),
        ).fetchall()

    # --- source_usage_decisions (append-only) -----------------------------

    def add_usage_decision(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO source_usage_decisions(
            public_id,data_source_id,target_use,allowed,decision_code,blocking_reasons_json,
            warnings_json,required_actions_json,evaluated_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["data_source_id"],
                values["target_use"],
                1 if values["allowed"] else 0,
                values["decision_code"],
                values.get("blocking_reasons_json", "[]"),
                values.get("warnings_json", "[]"),
                values.get("required_actions_json", "[]"),
                values.get("evaluated_by_admin_public_id"),
            ),
        )
        return public_id

    def list_usage_decisions(
        self, connection: sqlite3.Connection, source_id: int, *, target_use: str | None = None
    ) -> list[sqlite3.Row]:
        if target_use:
            return connection.execute(
                "SELECT * FROM source_usage_decisions WHERE data_source_id=? AND target_use=? "
                "ORDER BY created_at DESC, id DESC",
                (source_id, target_use),
            ).fetchall()
        return connection.execute(
            "SELECT * FROM source_usage_decisions WHERE data_source_id=? "
            "ORDER BY created_at DESC, id DESC",
            (source_id,),
        ).fetchall()

    def latest_usage_decision(
        self, connection: sqlite3.Connection, source_id: int, target_use: str
    ) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT * FROM source_usage_decisions WHERE data_source_id=? AND target_use=? "
            "ORDER BY created_at DESC, id DESC LIMIT 1",
            (source_id, target_use),
        ).fetchone()

    # --- source_record_links (mutable, deletable) -------------------------

    def create_link(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO source_record_links(
            public_id,data_source_id,entity_type,entity_public_id,relationship_type,
            source_page,source_section,source_locator,created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["data_source_id"],
                values["entity_type"],
                values["entity_public_id"],
                values.get("relationship_type", "primary_source"),
                values.get("source_page"),
                values.get("source_section"),
                values.get("source_locator"),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def list_links(self, connection: sqlite3.Connection, source_id: int) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM source_record_links WHERE data_source_id=? "
            "ORDER BY created_at DESC, id DESC",
            (source_id,),
        ).fetchall()

    def links_for_entity(
        self, connection: sqlite3.Connection, entity_type: str, entity_public_id: str
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM source_record_links WHERE entity_type=? AND entity_public_id=? "
            "ORDER BY created_at DESC, id DESC",
            (entity_type, entity_public_id),
        ).fetchall()

    def link(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM source_record_links WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("source record link not found")
        return row

    def delete_link(self, connection: sqlite3.Connection, link_id: int) -> None:
        connection.execute("DELETE FROM source_record_links WHERE id=?", (link_id,))

    def link_count(self, connection: sqlite3.Connection, source_id: int) -> int:
        return connection.execute(
            "SELECT COUNT(*) FROM source_record_links WHERE data_source_id=?", (source_id,)
        ).fetchone()[0]
