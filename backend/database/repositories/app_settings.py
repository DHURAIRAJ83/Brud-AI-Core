"""Application settings repository with strict serialization and validation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from backend.core.json_utils import dumps_json
from backend.database.repositories.base import BaseRepository, NotFoundError, ValidationError


def _now() -> str:
    return datetime.now(UTC).isoformat()


class SettingsRepository(BaseRepository):
    VALID_TYPES = {"string", "boolean", "integer", "float", "json"}

    def set(
        self,
        key: str,
        value: Any,
        *,
        value_type: str = "string",
        is_secret: bool = False,
        description: str | None = None,
    ) -> None:
        if value_type not in self.VALID_TYPES:
            raise ValidationError("unsupported setting value type")
        serialized = self._serialize(value, value_type)
        with self.transaction() as connection:
            connection.execute(
                """INSERT INTO app_settings(key,value,value_type,is_secret,description,updated_at)
                VALUES (?,?,?,?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,
                value_type=excluded.value_type,is_secret=excluded.is_secret,
                description=excluded.description,updated_at=excluded.updated_at""",
                (key, serialized, value_type, int(is_secret), description, _now()),
            )

    @staticmethod
    def _serialize(value: Any, value_type: str) -> str:
        try:
            if value_type == "boolean":
                if not isinstance(value, bool):
                    raise ValueError
                return "true" if value else "false"
            if value_type == "integer":
                if isinstance(value, bool) or not isinstance(value, int):
                    raise ValueError
                return str(value)
            if value_type == "float":
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise ValueError
                return str(float(value))
            if value_type == "json":
                return dumps_json(value)
            if not isinstance(value, str):
                raise ValueError
            return value
        except ValueError as exc:
            raise ValidationError(f"value does not match setting type {value_type}") from exc

    def get_safe(self, key: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT key,value,value_type,is_secret,description,updated_at "
                "FROM app_settings WHERE key=?",
                (key,),
            ).fetchone()
        if not row:
            raise NotFoundError("setting not found")
        return {
            "key": row["key"],
            "value": "[REDACTED]" if row["is_secret"] else row["value"],
            "value_type": row["value_type"],
            "is_secret": bool(row["is_secret"]),
            "description": row["description"],
            "updated_at": row["updated_at"],
        }
