"""Repository for the Phase 6 (Data Studio) unified governance layer:
``governance_review_items``, ``governance_review_issues``,
``governance_duplicate_groups``/``_members``,
``governance_conflict_groups``/``_members``, ``governance_resolutions``,
``governance_target_approvals``, ``governance_review_events``.

This is an *additive* layer above six existing, independently-owned
entity tables (see
docs/data_studio/phase6_quality_duplicate_conflict_approval_plan.md
section 3) -- it never writes to `document_pages`, `manual_data_records`,
`semantic_chunks`, `structured_record_candidates`, `document_candidates`,
or `dataset_records` directly. Entities are referenced polymorphically
via `(entity_type, entity_public_id)`, mirroring
`backend/database/repositories/source_records.py`'s convention.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from uuid import uuid4

from backend.core.json_utils import loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError

INTERNAL = {
    "id",
    "review_item_id",
    "group_id",
    "duplicate_group_id",
    "conflict_group_id",
}


def public_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("governance row not found")
    data = dict(row)
    for key in list(data):
        if key in INTERNAL:
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    return data


class GovernanceRepository(BaseRepository):
    @contextmanager
    def transaction(self, *, immediate: bool = True) -> Iterator[sqlite3.Connection]:
        with super().transaction(immediate=immediate) as connection:
            yield connection

    # --- governance_review_items -------------------------------------

    def next_review_code(self, connection: sqlite3.Connection) -> str:
        return self._next_code(connection, "governance_review_items", "review_code", "REV")

    def create_review_item(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO governance_review_items(
            public_id, review_code, entity_type, entity_public_id,
            entity_revision_public_id, source_public_id, document_public_id,
            page_public_id, priority, assigned_admin_public_id, created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["review_code"],
                values["entity_type"],
                values["entity_public_id"],
                values.get("entity_revision_public_id"),
                values.get("source_public_id"),
                values.get("document_public_id"),
                values.get("page_public_id"),
                values.get("priority", "normal"),
                values.get("assigned_admin_public_id"),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def review_item(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM governance_review_items WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("governance review item not found")
        return row

    def review_item_by_id(self, connection: sqlite3.Connection, item_id: int) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM governance_review_items WHERE id=?", (item_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("governance review item not found")
        return row

    def find_open_review_item(
        self, connection: sqlite3.Connection, entity_type: str, entity_public_id: str
    ) -> sqlite3.Row | None:
        return connection.execute(
            """SELECT * FROM governance_review_items
            WHERE entity_type=? AND entity_public_id=?
            AND status NOT IN ('resolved','rejected','archived')
            ORDER BY id DESC LIMIT 1""",
            (entity_type, entity_public_id),
        ).fetchone()

    def list_review_items(
        self,
        connection: sqlite3.Connection,
        *,
        status: str | None = None,
        priority: str | None = None,
        entity_type: str | None = None,
        assigned_admin_public_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[sqlite3.Row], int]:
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status=?")
            params.append(status)
        if priority:
            clauses.append("priority=?")
            params.append(priority)
        if entity_type:
            clauses.append("entity_type=?")
            params.append(entity_type)
        if assigned_admin_public_id:
            clauses.append("assigned_admin_public_id=?")
            params.append(assigned_admin_public_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        total = connection.execute(
            f"SELECT COUNT(*) FROM governance_review_items {where}",  # noqa: S608
            params,
        ).fetchone()[0]
        rows = connection.execute(
            f"SELECT * FROM governance_review_items {where} "  # noqa: S608
            "ORDER BY CASE priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 "
            "WHEN 'normal' THEN 2 ELSE 3 END, created_at DESC, id DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
        return rows, total

    def update_review_item(
        self, connection: sqlite3.Connection, item_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        assignments = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE governance_review_items SET {assignments},"  # noqa: S608
            "updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (*fields.values(), item_id),
        )

    def review_queue_counts(self, connection: sqlite3.Connection) -> dict[str, int]:
        rows = connection.execute(
            "SELECT status, COUNT(*) AS count FROM governance_review_items GROUP BY status"
        ).fetchall()
        return {row["status"]: row["count"] for row in rows}

    # --- governance_review_issues --------------------------------------

    def create_issue(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO governance_review_issues(
            public_id, review_item_id, issue_code, issue_category, severity,
            is_blocking, blocking_targets_json, message, details_json, detector,
            detector_version)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["review_item_id"],
                values["issue_code"],
                values["issue_category"],
                values["severity"],
                1 if values.get("is_blocking") else 0,
                values.get("blocking_targets_json", "[]"),
                values["message"],
                values.get("details_json", "{}"),
                values["detector"],
                values.get("detector_version", "v1"),
            ),
        )
        return public_id

    def issues_for_item(
        self, connection: sqlite3.Connection, review_item_id: int, *, open_only: bool = False
    ) -> list[sqlite3.Row]:
        query = "SELECT * FROM governance_review_issues WHERE review_item_id=?"
        if open_only:
            query += " AND resolved_at IS NULL"
        query += " ORDER BY created_at DESC, id DESC"
        return connection.execute(query, (review_item_id,)).fetchall()

    def resolve_issue(self, connection: sqlite3.Connection, public_id: str) -> None:
        connection.execute(
            "UPDATE governance_review_issues SET resolved_at=CURRENT_TIMESTAMP WHERE public_id=?",
            (public_id,),
        )

    # --- governance_duplicate_groups / members --------------------------

    def next_group_code(self, connection: sqlite3.Connection, kind: str) -> str:
        table = (
            "governance_duplicate_groups" if kind == "duplicate" else "governance_conflict_groups"
        )
        prefix = "DUP" if kind == "duplicate" else "CFL"
        return self._next_code(connection, table, "group_code", prefix)

    def create_duplicate_group(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO governance_duplicate_groups(
            public_id, group_code, duplicate_type, canonical_entity_type,
            canonical_entity_public_id, match_reason, match_value)
            VALUES (?,?,?,?,?,?,?)""",
            (
                public_id,
                values["group_code"],
                values["duplicate_type"],
                values.get("canonical_entity_type"),
                values.get("canonical_entity_public_id"),
                values["match_reason"],
                values.get("match_value"),
            ),
        )
        return public_id

    def duplicate_group(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM governance_duplicate_groups WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("duplicate group not found")
        return row

    def add_duplicate_member(
        self,
        connection: sqlite3.Connection,
        group_id: int,
        entity_type: str,
        entity_public_id: str,
        *,
        role: str = "member",
    ) -> None:
        connection.execute(
            """INSERT OR IGNORE INTO governance_duplicate_group_members(
            group_id, entity_type, entity_public_id, role) VALUES (?,?,?,?)""",
            (group_id, entity_type, entity_public_id, role),
        )

    def duplicate_group_members(
        self, connection: sqlite3.Connection, group_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM governance_duplicate_group_members WHERE group_id=? ORDER BY id",
            (group_id,),
        ).fetchall()

    def find_open_duplicate_group_for_entity(
        self, connection: sqlite3.Connection, entity_type: str, entity_public_id: str
    ) -> sqlite3.Row | None:
        return connection.execute(
            """SELECT g.* FROM governance_duplicate_groups g
            JOIN governance_duplicate_group_members m ON m.group_id = g.id
            WHERE g.status='open' AND m.entity_type=? AND m.entity_public_id=?
            ORDER BY g.id DESC LIMIT 1""",
            (entity_type, entity_public_id),
        ).fetchone()

    def list_duplicate_groups(
        self, connection: sqlite3.Connection, *, status: str | None = None
    ) -> list[sqlite3.Row]:
        if status:
            return connection.execute(
                "SELECT * FROM governance_duplicate_groups WHERE status=? "
                "ORDER BY created_at DESC, id DESC",
                (status,),
            ).fetchall()
        return connection.execute(
            "SELECT * FROM governance_duplicate_groups ORDER BY created_at DESC, id DESC"
        ).fetchall()

    def resolve_duplicate_group(self, connection: sqlite3.Connection, group_id: int) -> None:
        connection.execute(
            "UPDATE governance_duplicate_groups SET status='resolved', "
            "resolved_at=CURRENT_TIMESTAMP WHERE id=?",
            (group_id,),
        )

    # --- governance_conflict_groups / members ----------------------------

    def create_conflict_group(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO governance_conflict_groups(
            public_id, group_code, conflict_type, match_reason, match_value)
            VALUES (?,?,?,?,?)""",
            (
                public_id,
                values["group_code"],
                values["conflict_type"],
                values["match_reason"],
                values.get("match_value"),
            ),
        )
        return public_id

    def conflict_group(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM governance_conflict_groups WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("conflict group not found")
        return row

    def add_conflict_member(
        self,
        connection: sqlite3.Connection,
        group_id: int,
        entity_type: str,
        entity_public_id: str,
        *,
        role: str = "member",
    ) -> None:
        connection.execute(
            """INSERT OR IGNORE INTO governance_conflict_group_members(
            group_id, entity_type, entity_public_id, role) VALUES (?,?,?,?)""",
            (group_id, entity_type, entity_public_id, role),
        )

    def conflict_group_members(
        self, connection: sqlite3.Connection, group_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM governance_conflict_group_members WHERE group_id=? ORDER BY id",
            (group_id,),
        ).fetchall()

    def find_open_conflict_group_for_entity(
        self, connection: sqlite3.Connection, entity_type: str, entity_public_id: str
    ) -> sqlite3.Row | None:
        return connection.execute(
            """SELECT g.* FROM governance_conflict_groups g
            JOIN governance_conflict_group_members m ON m.group_id = g.id
            WHERE g.status='open' AND m.entity_type=? AND m.entity_public_id=?
            ORDER BY g.id DESC LIMIT 1""",
            (entity_type, entity_public_id),
        ).fetchone()

    def list_conflict_groups(
        self, connection: sqlite3.Connection, *, status: str | None = None
    ) -> list[sqlite3.Row]:
        if status:
            return connection.execute(
                "SELECT * FROM governance_conflict_groups WHERE status=? "
                "ORDER BY created_at DESC, id DESC",
                (status,),
            ).fetchall()
        return connection.execute(
            "SELECT * FROM governance_conflict_groups ORDER BY created_at DESC, id DESC"
        ).fetchall()

    def resolve_conflict_group(self, connection: sqlite3.Connection, group_id: int) -> None:
        connection.execute(
            "UPDATE governance_conflict_groups SET status='resolved', "
            "resolved_at=CURRENT_TIMESTAMP WHERE id=?",
            (group_id,),
        )

    # --- governance_resolutions -------------------------------------------

    def create_resolution(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO governance_resolutions(
            public_id, duplicate_group_id, conflict_group_id, resolution_action,
            resolution_reason, selected_entities_json, created_revision_ids_json,
            performed_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values.get("duplicate_group_id"),
                values.get("conflict_group_id"),
                values["resolution_action"],
                values["resolution_reason"],
                values.get("selected_entities_json", "[]"),
                values.get("created_revision_ids_json", "[]"),
                values["performed_by_admin_public_id"],
            ),
        )
        return public_id

    def resolutions_for_duplicate_group(
        self, connection: sqlite3.Connection, group_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM governance_resolutions WHERE duplicate_group_id=? "
            "ORDER BY created_at DESC, id DESC",
            (group_id,),
        ).fetchall()

    def resolutions_for_conflict_group(
        self, connection: sqlite3.Connection, group_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM governance_resolutions WHERE conflict_group_id=? "
            "ORDER BY created_at DESC, id DESC",
            (group_id,),
        ).fetchall()

    # --- governance_target_approvals --------------------------------------

    def create_target_approval(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO governance_target_approvals(
            public_id, review_item_id, entity_type, entity_public_id, target_use,
            decision, decision_code, blocking_issue_ids_json, warnings_json,
            required_actions_json, is_override, override_reason,
            decided_by_admin_public_id, expires_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["review_item_id"],
                values["entity_type"],
                values["entity_public_id"],
                values["target_use"],
                values["decision"],
                values["decision_code"],
                values.get("blocking_issue_ids_json", "[]"),
                values.get("warnings_json", "[]"),
                values.get("required_actions_json", "[]"),
                1 if values.get("is_override") else 0,
                values.get("override_reason"),
                values["decided_by_admin_public_id"],
                values.get("expires_at"),
            ),
        )
        return public_id

    def latest_target_approval(
        self,
        connection: sqlite3.Connection,
        entity_type: str,
        entity_public_id: str,
        target_use: str,
    ) -> sqlite3.Row | None:
        return connection.execute(
            """SELECT * FROM governance_target_approvals
            WHERE entity_type=? AND entity_public_id=? AND target_use=?
            ORDER BY decided_at DESC, id DESC LIMIT 1""",
            (entity_type, entity_public_id, target_use),
        ).fetchone()

    def target_approvals_for_entity(
        self, connection: sqlite3.Connection, entity_type: str, entity_public_id: str
    ) -> list[sqlite3.Row]:
        return connection.execute(
            """SELECT * FROM governance_target_approvals
            WHERE entity_type=? AND entity_public_id=?
            ORDER BY target_use, decided_at DESC, id DESC""",
            (entity_type, entity_public_id),
        ).fetchall()

    def target_approval_history(
        self,
        connection: sqlite3.Connection,
        entity_type: str,
        entity_public_id: str,
        target_use: str,
    ) -> list[sqlite3.Row]:
        return connection.execute(
            """SELECT * FROM governance_target_approvals
            WHERE entity_type=? AND entity_public_id=? AND target_use=?
            ORDER BY decided_at DESC, id DESC""",
            (entity_type, entity_public_id, target_use),
        ).fetchall()

    # --- governance_review_events ------------------------------------------

    def create_event(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO governance_review_events(
            public_id, review_item_id, event_type, performed_by_admin_public_id,
            notes, metadata_json)
            VALUES (?,?,?,?,?,?)""",
            (
                public_id,
                values["review_item_id"],
                values["event_type"],
                values["performed_by_admin_public_id"],
                values.get("notes", ""),
                values.get("metadata_json", "{}"),
            ),
        )
        return public_id

    def events_for_item(
        self, connection: sqlite3.Connection, review_item_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM governance_review_events WHERE review_item_id=? "
            "ORDER BY created_at DESC, id DESC",
            (review_item_id,),
        ).fetchall()

    # --- shared helpers ------------------------------------------------------

    def _next_code(
        self, connection: sqlite3.Connection, table: str, column: str, prefix: str
    ) -> str:
        rows = connection.execute(
            f"SELECT {column} FROM {table} WHERE {column} LIKE ?",  # noqa: S608
            (f"{prefix}-%",),
        ).fetchall()
        max_number = 0
        for row in rows:
            suffix = row[0].removeprefix(f"{prefix}-")
            if suffix.isdigit():
                max_number = max(max_number, int(suffix))
        return f"{prefix}-{max_number + 1:04d}"
