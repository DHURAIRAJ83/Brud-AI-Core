"""Repository for MB-27: Brud AI Secrets & Provider Settings UI.

Four tables, all MB-27's own: `mini_brain_provider_settings`,
`mini_brain_provider_secrets` (encrypted values only -- see below),
`mini_brain_provider_audit_events` (append-only), and
`mini_brain_provider_settings_memory` (permanent, insert-only). MB-27
never writes to any other system's tables.

**No `public_secret_row()` function exists here at all** -- there is
no "public" projection of the secrets table. `list_secrets()` returns
raw rows (including `encrypted_value`) because the service layer needs
them internally (to decrypt for a test-connection call, or to read
only `secret_name` for masking) -- but nothing in this file ever
strips/masks `encrypted_value` for external consumption, because
nothing in this file is meant to be called by a route handler
directly. Masking happens exclusively in the service, via
`core_model.mini_brain.provider_settings.secret_masker`.
"""

from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError

_SETTING_INTERNAL = {"id"}
_AUDIT_INTERNAL = {"id"}
_MEMORY_INTERNAL = {"id"}


def public_setting_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("provider setting row not found")
    data = dict(row)
    for key in list(data):
        if key in _SETTING_INTERNAL:
            data.pop(key)
        elif key == "config_json":
            data["config"] = loads_json(data.pop(key))
        elif key in ("enabled", "archived"):
            data[key] = bool(data[key])
    return data


def public_audit_event_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("provider audit event row not found")
    data = dict(row)
    for key in list(data):
        if key in _AUDIT_INTERNAL:
            data.pop(key)
        elif key == "changed_fields_json":
            data["changed_fields"] = loads_json(data.pop(key))
    return data


def public_memory_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("provider settings memory row not found")
    data = dict(row)
    for key in list(data):
        if key in _MEMORY_INTERNAL:
            data.pop(key)
    return data


class MiniBrainProviderSettingsRepository(BaseRepository):
    # -- settings ------------------------------------------------------------

    def create_setting(
        self, connection: sqlite3.Connection, *, provider_key: str, provider_type: str,
        enabled: bool, config: dict[str, Any],
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_provider_settings(
                public_id, provider_key, provider_type, enabled, config_json
            ) VALUES (?, ?, ?, ?, ?)""",
            (public_id, provider_key, provider_type, int(enabled), dumps_json(config)),
        )
        return public_id

    def get_setting(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM mini_brain_provider_settings WHERE public_id=?", (public_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"provider setting not found: {public_id}")
        return row

    def get_setting_by_provider_key(self, connection: sqlite3.Connection, provider_key: str) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT * FROM mini_brain_provider_settings WHERE provider_key=?", (provider_key,)
        ).fetchone()

    def list_settings(
        self, connection: sqlite3.Connection, *, provider_type: str | None = None,
        enabled: bool | None = None, include_archived: bool = False,
    ) -> list[sqlite3.Row]:
        clauses = []
        params: list[Any] = []
        if provider_type:
            clauses.append("provider_type=?")
            params.append(provider_type)
        if enabled is not None:
            clauses.append("enabled=?")
            params.append(int(enabled))
        if not include_archived:
            clauses.append("archived=0")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        return connection.execute(
            f"SELECT * FROM mini_brain_provider_settings {where} ORDER BY id", params
        ).fetchall()

    def update_setting(self, connection: sqlite3.Connection, public_id: str, fields: dict[str, Any]) -> sqlite3.Row:
        self.get_setting(connection, public_id)
        set_clauses = []
        values: list[Any] = []
        for column, value in fields.items():
            set_clauses.append(f'"{column}"=?')
            if column == "config_json":
                values.append(dumps_json(value))
            elif isinstance(value, bool):
                values.append(int(value))
            else:
                values.append(value)
        set_clauses.append('"updated_at"=CURRENT_TIMESTAMP')
        values.append(public_id)
        connection.execute(
            f'UPDATE mini_brain_provider_settings SET {", ".join(set_clauses)} WHERE public_id=?', values,
        )
        return self.get_setting(connection, public_id)

    def archive_setting(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        from datetime import UTC, datetime

        now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
        return self.update_setting(connection, public_id, {"archived": True, "archived_at": now, "enabled": False})

    # -- secrets (encrypted) -----------------------------------------------------

    def upsert_secret(
        self, connection: sqlite3.Connection, *, setting_public_id: str, secret_name: str, encrypted_value: str,
    ) -> str:
        existing = connection.execute(
            "SELECT public_id FROM mini_brain_provider_secrets WHERE setting_public_id=? AND secret_name=?",
            (setting_public_id, secret_name),
        ).fetchone()
        if existing:
            connection.execute(
                """UPDATE mini_brain_provider_secrets SET encrypted_value=?, updated_at=CURRENT_TIMESTAMP
                WHERE setting_public_id=? AND secret_name=?""",
                (encrypted_value, setting_public_id, secret_name),
            )
            return existing["public_id"]
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_provider_secrets(
                public_id, setting_public_id, secret_name, encrypted_value
            ) VALUES (?, ?, ?, ?)""",
            (public_id, setting_public_id, secret_name, encrypted_value),
        )
        return public_id

    def delete_secret(self, connection: sqlite3.Connection, *, setting_public_id: str, secret_name: str) -> bool:
        cursor = connection.execute(
            "DELETE FROM mini_brain_provider_secrets WHERE setting_public_id=? AND secret_name=?",
            (setting_public_id, secret_name),
        )
        return cursor.rowcount > 0

    def list_secrets(self, connection: sqlite3.Connection, *, setting_public_id: str) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM mini_brain_provider_secrets WHERE setting_public_id=? ORDER BY id",
            (setting_public_id,),
        ).fetchall()

    def get_secret(self, connection: sqlite3.Connection, *, setting_public_id: str, secret_name: str) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT * FROM mini_brain_provider_secrets WHERE setting_public_id=? AND secret_name=?",
            (setting_public_id, secret_name),
        ).fetchone()

    # -- audit events (append-only) -------------------------------------------------

    def create_audit_event(
        self, connection: sqlite3.Connection, *, provider_key: str, setting_public_id: str | None,
        action: str, admin_id: str | None, changed_fields: list[str],
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_provider_audit_events(
                public_id, provider_key, setting_public_id, action, admin_id, changed_fields_json
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            (public_id, provider_key, setting_public_id, action, admin_id, dumps_json(changed_fields)),
        )
        return public_id

    def list_audit_events(
        self, connection: sqlite3.Connection, *, provider_key: str | None = None, limit: int, offset: int,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        if provider_key:
            return connection.execute(
                """SELECT * FROM mini_brain_provider_audit_events WHERE provider_key=?
                ORDER BY id DESC LIMIT ? OFFSET ?""",
                (provider_key, limit, offset),
            ).fetchall()
        return connection.execute(
            "SELECT * FROM mini_brain_provider_audit_events ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()

    # -- settings memory (permanent, insert-only) ------------------------------------

    def create_memory(
        self, connection: sqlite3.Connection, *, provider_key: str, setting_public_id: str,
        event_type: str, recorded_by: str,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_provider_settings_memory(
                public_id, provider_key, setting_public_id, event_type, recorded_by
            ) VALUES (?, ?, ?, ?, ?)""",
            (public_id, provider_key, setting_public_id, event_type, recorded_by),
        )
        return public_id

    def list_memory(self, connection: sqlite3.Connection, *, limit: int, offset: int) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            "SELECT * FROM mini_brain_provider_settings_memory ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()


__all__ = [
    "MiniBrainProviderSettingsRepository",
    "public_setting_row",
    "public_audit_event_row",
    "public_memory_row",
]
