"""Repository for MB-24: Brud Mini Brain Plugin & Tool Runtime
Governance Center.

Five tables, all MB-24's own: `mini_brain_plugins`,
`mini_brain_plugin_permissions` (one row per scope grant lifecycle),
`mini_brain_plugin_consents` (user consent records, hashed identity
only), `mini_brain_plugin_runtime_events` (append-only audit log --
issued execution tokens are recorded here as a hash only, never the
raw token), and `mini_brain_plugin_runtime_memory` (permanent,
insert-only rollup). MB-24 never writes to any other system's tables.
"""

from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError

_PLUGIN_INTERNAL = {"id"}
PLUGIN_JSON_FIELDS = (
    "requested_scopes", "allowed_domains", "filesystem_roots", "ui_components", "validation_report",
    "capability_classification", "sandbox_profile", "filesystem_policy", "network_policy",
    "permission_evaluation", "governance_report",
)
_PERMISSION_INTERNAL = {"id", "plugin_id"}
_CONSENT_INTERNAL = {"id", "plugin_id"}
_MEMORY_INTERNAL = {"id", "plugin_id"}


def public_plugin_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("plugin row not found")
    data = dict(row)
    for key in list(data):
        if key in _PLUGIN_INTERNAL:
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
        elif key in ("local_storage_usage", "cloud_storage_usage", "admin_reviewed"):
            data[key] = bool(data[key])
    return data


def public_permission_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("plugin permission row not found")
    data = dict(row)
    for key in list(data):
        if key in _PERMISSION_INTERNAL:
            data.pop(key)
    return data


def public_consent_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("plugin consent row not found")
    data = dict(row)
    for key in list(data):
        if key in _CONSENT_INTERNAL:
            data.pop(key)
        elif key == "consent_given":
            data[key] = bool(data[key])
    return data


def public_memory_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("plugin runtime memory row not found")
    data = dict(row)
    for key in list(data):
        if key in _MEMORY_INTERNAL:
            data.pop(key)
    return data


class MiniBrainPluginGovernanceRepository(BaseRepository):
    # -- plugins ------------------------------------------------------------

    def create_plugin(
        self, connection: sqlite3.Connection, *, plugin_id: str, name: str, version: str, author: str,
        description: str, entrypoint: str, requested_scopes: list[str], allowed_domains: list[str],
        filesystem_roots: list[str], ui_components: list[str], local_storage_usage: bool,
        cloud_storage_usage: bool, minimum_brud_version: str, signature_placeholder: str, homepage: str,
        support_url: str, manifest_checksum_sha256: str, registered_by_admin_public_id: str,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_plugins(
                public_id, plugin_id, name, version, author, description, entrypoint,
                requested_scopes_json, allowed_domains_json, filesystem_roots_json, ui_components_json,
                local_storage_usage, cloud_storage_usage, minimum_brud_version, signature_placeholder,
                homepage, support_url, manifest_checksum_sha256, registered_by_admin_public_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                public_id, plugin_id, name, version, author, description, entrypoint,
                dumps_json(requested_scopes), dumps_json(allowed_domains), dumps_json(filesystem_roots),
                dumps_json(ui_components), int(local_storage_usage), int(cloud_storage_usage),
                minimum_brud_version, signature_placeholder, homepage, support_url,
                manifest_checksum_sha256, registered_by_admin_public_id,
            ),
        )
        return public_id

    def get_plugin(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM mini_brain_plugins WHERE public_id=?", (public_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"plugin not found: {public_id}")
        return row

    def list_plugins(
        self, connection: sqlite3.Connection, *, limit: int, offset: int, status: str | None = None,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        if status:
            return connection.execute(
                "SELECT * FROM mini_brain_plugins WHERE status=? ORDER BY id DESC LIMIT ? OFFSET ?",
                (status, limit, offset),
            ).fetchall()
        return connection.execute(
            "SELECT * FROM mini_brain_plugins ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset),
        ).fetchall()

    def update_plugin(self, connection: sqlite3.Connection, public_id: str, fields: dict[str, Any]) -> sqlite3.Row:
        self.get_plugin(connection, public_id)
        json_columns = {f"{f}_json" for f in PLUGIN_JSON_FIELDS}
        set_clauses = []
        values: list[Any] = []
        for column, value in fields.items():
            set_clauses.append(f'"{column}"=?')
            values.append(dumps_json(value) if column in json_columns else value)
        set_clauses.append('"updated_at"=CURRENT_TIMESTAMP')
        values.append(public_id)
        connection.execute(
            f'UPDATE mini_brain_plugins SET {", ".join(set_clauses)} WHERE public_id=?', values,
        )
        return self.get_plugin(connection, public_id)

    # -- permissions ----------------------------------------------------------

    def create_permission(
        self, connection: sqlite3.Connection, *, plugin_id: int, scope_key: str, decision: str,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_plugin_permissions(public_id, plugin_id, scope_key, decision)
            VALUES (?, ?, ?, ?)""",
            (public_id, plugin_id, scope_key, decision),
        )
        return public_id

    def get_permission(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM mini_brain_plugin_permissions WHERE public_id=?", (public_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"plugin permission not found: {public_id}")
        return row

    def find_permission(self, connection: sqlite3.Connection, *, plugin_id: int, scope_key: str) -> sqlite3.Row | None:
        return connection.execute(
            """SELECT * FROM mini_brain_plugin_permissions WHERE plugin_id=? AND scope_key=?
            ORDER BY id DESC LIMIT 1""",
            (plugin_id, scope_key),
        ).fetchone()

    def list_permissions(
        self, connection: sqlite3.Connection, *, plugin_id: int, limit: int, offset: int,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            "SELECT * FROM mini_brain_plugin_permissions WHERE plugin_id=? ORDER BY id DESC LIMIT ? OFFSET ?",
            (plugin_id, limit, offset),
        ).fetchall()

    def update_permission(self, connection: sqlite3.Connection, public_id: str, fields: dict[str, Any]) -> sqlite3.Row:
        self.get_permission(connection, public_id)
        set_clauses = [f'"{column}"=?' for column in fields]
        values = list(fields.values())
        values.append(public_id)
        connection.execute(
            f'UPDATE mini_brain_plugin_permissions SET {", ".join(set_clauses)} WHERE public_id=?', values,
        )
        return self.get_permission(connection, public_id)

    def granted_permission_count(self, connection: sqlite3.Connection, *, plugin_id: int) -> int:
        return connection.execute(
            "SELECT COUNT(*) AS n FROM mini_brain_plugin_permissions WHERE plugin_id=? AND status='granted'",
            (plugin_id,),
        ).fetchone()["n"]

    # -- consents ------------------------------------------------------------

    def create_consent(
        self, connection: sqlite3.Connection, *, plugin_id: int, user_id_hash: str, scope_key: str,
        consent_given: bool, consent_at: str | None, expires_at: str | None,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_plugin_consents(
                public_id, plugin_id, user_id_hash, scope_key, consent_given, consent_at, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (public_id, plugin_id, user_id_hash, scope_key, int(consent_given), consent_at, expires_at),
        )
        return public_id

    def latest_consent(
        self, connection: sqlite3.Connection, *, plugin_id: int, user_id_hash: str, scope_key: str,
    ) -> sqlite3.Row | None:
        return connection.execute(
            """SELECT * FROM mini_brain_plugin_consents WHERE plugin_id=? AND user_id_hash=? AND scope_key=?
            AND revoked_at IS NULL ORDER BY id DESC LIMIT 1""",
            (plugin_id, user_id_hash, scope_key),
        ).fetchone()

    def list_consents(
        self, connection: sqlite3.Connection, *, plugin_id: int, limit: int, offset: int,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            "SELECT * FROM mini_brain_plugin_consents WHERE plugin_id=? ORDER BY id DESC LIMIT ? OFFSET ?",
            (plugin_id, limit, offset),
        ).fetchall()

    def consent_count(self, connection: sqlite3.Connection, *, plugin_id: int) -> int:
        return connection.execute(
            "SELECT COUNT(*) AS n FROM mini_brain_plugin_consents WHERE plugin_id=?", (plugin_id,),
        ).fetchone()["n"]

    # -- runtime events (append-only) ---------------------------------------------

    def create_event(
        self, connection: sqlite3.Connection, *, plugin_id: int | None, event_type: str,
        stage: str | None = None, message: str = "", metadata: dict[str, Any] | None = None,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_plugin_runtime_events(
                public_id, plugin_id, event_type, stage, message, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            (public_id, plugin_id, event_type, stage, message, dumps_json(metadata or {})),
        )
        return public_id

    def list_events(
        self, connection: sqlite3.Connection, *, plugin_id: int | None = None, limit: int, offset: int,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        if plugin_id is not None:
            return connection.execute(
                "SELECT * FROM mini_brain_plugin_runtime_events WHERE plugin_id=? ORDER BY id DESC LIMIT ? OFFSET ?",
                (plugin_id, limit, offset),
            ).fetchall()
        return connection.execute(
            "SELECT * FROM mini_brain_plugin_runtime_events ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset),
        ).fetchall()

    def event_count(self, connection: sqlite3.Connection, *, plugin_id: int) -> int:
        return connection.execute(
            "SELECT COUNT(*) AS n FROM mini_brain_plugin_runtime_events WHERE plugin_id=?", (plugin_id,),
        ).fetchone()["n"]

    # -- runtime memory (permanent, insert-only) -----------------------------------

    def create_memory(
        self, connection: sqlite3.Connection, *, plugin_id: int, final_status: str,
        total_permissions_granted: int, total_consents_recorded: int, total_runtime_events: int,
        risk_score: float | None, risk_level: str | None, recorded_by_admin_public_id: str,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_plugin_runtime_memory(
                public_id, plugin_id, final_status, total_permissions_granted, total_consents_recorded,
                total_runtime_events, risk_score, risk_level, recorded_by_admin_public_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                public_id, plugin_id, final_status, total_permissions_granted, total_consents_recorded,
                total_runtime_events, risk_score, risk_level, recorded_by_admin_public_id,
            ),
        )
        return public_id

    def list_memory(self, connection: sqlite3.Connection, *, limit: int, offset: int) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            "SELECT * FROM mini_brain_plugin_runtime_memory ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset),
        ).fetchall()


__all__ = [
    "MiniBrainPluginGovernanceRepository", "public_plugin_row", "public_permission_row", "public_consent_row",
    "public_memory_row", "PLUGIN_JSON_FIELDS",
]
