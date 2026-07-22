"""Shared repository safety primitives."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from backend.database.connection import database_connection


class RepositoryError(RuntimeError):
    """Controlled base exception for persistence failures."""


class NotFoundError(RepositoryError):
    """Requested public entity does not exist."""


class ConflictError(RepositoryError):
    """Requested change conflicts with an existing entity or immutable state."""


class ValidationError(RepositoryError):
    """Requested repository operation violates a lifecycle rule."""


class BaseRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with database_connection(self.database_path) as connection:
            try:
                connection.execute("BEGIN")
                yield connection
                connection.commit()
            except sqlite3.IntegrityError as exc:
                connection.rollback()
                raise ConflictError(str(exc)) from exc
            except ValidationError:
                connection.rollback()
                columns = {row[1] for row in connection.execute("PRAGMA table_info(audit_logs)")}
                if "public_id" in columns:
                    connection.execute(
                        """INSERT INTO audit_logs(action,actor,details,public_id,event_type,
                        actor_type,outcome,metadata_json) VALUES (?,?,?,?,?,?,?,?)""",
                        (
                            "repository_validation_failure",
                            "system",
                            "{}",
                            str(uuid4()),
                            "repository_validation_failure",
                            "system",
                            "warning",
                            "{}",
                        ),
                    )
                    connection.commit()
                raise
            except Exception:
                connection.rollback()
                raise

    @staticmethod
    def pagination(limit: int, offset: int) -> tuple[int, int]:
        if not 1 <= limit <= 100 or offset < 0:
            raise ValidationError("limit must be 1..100 and offset must be non-negative")
        return limit, offset
