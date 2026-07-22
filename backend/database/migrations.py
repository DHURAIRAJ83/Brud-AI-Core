"""Verified, additive SQLite migrations and backup command-line interface."""

import argparse
import hashlib
import json
import logging
import sqlite3
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from backend.core.config import Settings, get_settings
from backend.core.json_utils import dumps_json
from backend.database.connection import database_connection
from backend.database.schema import (
    INITIAL_SCHEMA,
    MIGRATION_002_NAME,
    MIGRATION_003_NAME,
    PHASE2_COLUMNS,
    PHASE2_NEW_TABLES,
    PHASE3_SCHEMA,
    SCHEMA_VERSION,
)

logger = logging.getLogger(__name__)


class MigrationError(RuntimeError):
    """Raised when a migration safety precondition or migration step fails."""


@dataclass(frozen=True)
class VerificationResult:
    integrity_check: str
    foreign_key_violations: list[tuple[object, ...]]

    @property
    def healthy(self) -> bool:
        return self.integrity_check == "ok" and not self.foreign_key_violations


@dataclass(frozen=True)
class BackupResult:
    filename: str
    path: Path
    source_checksum: str
    backup_checksum: str
    created_at: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def current_schema_version(database_path: Path) -> int:
    if not database_path.exists() or database_path.stat().st_size == 0:
        return 0
    with database_connection(database_path) as connection:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            ("schema_migrations",),
        ).fetchone()
        if not exists:
            return 0
        row = connection.execute(
            "SELECT COALESCE(MAX(version), 0) FROM schema_migrations"
        ).fetchone()
        return int(row[0])


def verify_database(database_path: Path) -> VerificationResult:
    if not database_path.is_file():
        raise MigrationError(f"database file does not exist: {database_path}")
    with database_connection(database_path) as connection:
        integrity_rows = connection.execute("PRAGMA integrity_check").fetchall()
        integrity = (
            "ok"
            if [row[0] for row in integrity_rows] == ["ok"]
            else "; ".join(str(row[0]) for row in integrity_rows)
        )
        foreign_keys = [tuple(row) for row in connection.execute("PRAGMA foreign_key_check")]
    result = VerificationResult(integrity, foreign_keys)
    if not result.healthy:
        raise MigrationError(
            f"database verification failed: integrity={integrity!r}, "
            f"foreign_key_violations={foreign_keys!r}"
        )
    return result


def create_verified_backup(database_path: Path, backup_dir: Path) -> BackupResult:
    """Create a consistent SQLite backup and prove it can be reopened and verified."""

    verify_database(database_path)
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
    backup_path = backup_dir / f"brud_ai_before_v{SCHEMA_VERSION}_{timestamp}.db"
    if backup_path.exists():
        raise MigrationError(f"refusing to overwrite backup: {backup_path.name}")
    with database_connection(database_path) as source:
        source.execute("PRAGMA wal_checkpoint(FULL)")
        source_checksum = sha256_file(database_path)
        destination = sqlite3.connect(backup_path)
        try:
            source.backup(destination)
            destination.commit()
        finally:
            destination.close()
    verify_database(backup_path)
    backup_checksum = sha256_file(backup_path)
    if backup_checksum != sha256_file(backup_path):
        raise MigrationError("backup checksum verification failed")
    return BackupResult(
        filename=backup_path.name,
        path=backup_path,
        source_checksum=source_checksum,
        backup_checksum=backup_checksum,
        created_at=datetime.now(UTC).isoformat(),
    )


def _has_column(connection: sqlite3.Connection, table: str, column: str) -> bool:
    return column in {row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')}


def _apply_v1(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.executescript(INITIAL_SCHEMA)
    connection.execute("INSERT OR IGNORE INTO schema_migrations(version) VALUES (?)", (1,))


def _populate_public_ids(connection: sqlite3.Connection, table: str) -> None:
    rows = connection.execute(f'SELECT id FROM "{table}" WHERE public_id IS NULL').fetchall()
    for row in rows:
        connection.execute(
            f'UPDATE "{table}" SET public_id = ? WHERE id = ?', (str(uuid4()), row[0])
        )


def _apply_v2(connection: sqlite3.Connection) -> None:
    if connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (2,)).fetchone():
        return
    for table, columns in PHASE2_COLUMNS.items():
        for name, definition in columns:
            if not _has_column(connection, table, name):
                connection.execute(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {definition}')
    connection.executescript(PHASE2_NEW_TABLES)
    for table in (
        "chat_sessions",
        "chat_messages",
        "dataset_sources",
        "dataset_records",
        "training_jobs",
        "model_registry",
        "audit_logs",
    ):
        _populate_public_ids(connection, table)
        connection.execute(
            f'CREATE UNIQUE INDEX IF NOT EXISTS "uq_{table}_public_id" ON "{table}"(public_id)'
        )
    legacy_records = connection.execute(
        "SELECT id, content FROM dataset_records WHERE content_hash IS NULL"
    ).fetchall()
    for row in legacy_records:
        content_hash = hashlib.sha256(row[1].encode("utf-8")).hexdigest()
        connection.execute(
            "UPDATE dataset_records SET content_hash = ? WHERE id = ?", (content_hash, row[0])
        )
    connection.execute(
        "UPDATE schema_migrations SET name = ? WHERE version = ? AND name IS NULL",
        ("001_phase1_foundation", 1),
    )
    connection.execute(
        "INSERT INTO schema_migrations(version, name) VALUES (?, ?)", (2, MIGRATION_002_NAME)
    )
    connection.executescript(
        """
        CREATE TRIGGER IF NOT EXISTS dataset_version_items_ready_update
        BEFORE UPDATE ON dataset_version_items
        WHEN (SELECT status FROM dataset_versions WHERE id = OLD.dataset_version_id) = 'ready'
        BEGIN SELECT RAISE(ABORT, 'ready dataset versions are immutable'); END;
        CREATE TRIGGER IF NOT EXISTS dataset_version_items_ready_delete
        BEFORE DELETE ON dataset_version_items
        WHEN (SELECT status FROM dataset_versions WHERE id = OLD.dataset_version_id) = 'ready'
        BEGIN SELECT RAISE(ABORT, 'ready dataset versions are immutable'); END;
        CREATE TRIGGER IF NOT EXISTS dataset_versions_ready_content_update
        BEFORE UPDATE OF manifest_json, record_count, language_distribution_json,
            split_distribution_json, checksum_sha256 ON dataset_versions
        WHEN OLD.status = 'ready'
        BEGIN SELECT RAISE(ABORT, 'ready dataset versions are immutable'); END;
        CREATE TRIGGER IF NOT EXISTS audit_logs_append_only_update
        BEFORE UPDATE ON audit_logs
        BEGIN SELECT RAISE(ABORT, 'audit logs are append-only'); END;
        CREATE TRIGGER IF NOT EXISTS audit_logs_append_only_delete
        BEFORE DELETE ON audit_logs
        BEGIN SELECT RAISE(ABORT, 'audit logs are append-only'); END;
        CREATE TRIGGER IF NOT EXISTS dataset_records_quality_insert
        BEFORE INSERT ON dataset_records
        WHEN NEW.quality_score IS NOT NULL AND (NEW.quality_score < 0 OR NEW.quality_score > 1)
        BEGIN SELECT RAISE(ABORT, 'quality score must be between 0 and 1'); END;
        CREATE TRIGGER IF NOT EXISTS dataset_records_quality_update
        BEFORE UPDATE OF quality_score ON dataset_records
        WHEN NEW.quality_score IS NOT NULL AND (NEW.quality_score < 0 OR NEW.quality_score > 1)
        BEGIN SELECT RAISE(ABORT, 'quality score must be between 0 and 1'); END;
        CREATE TRIGGER IF NOT EXISTS training_jobs_progress_insert
        BEFORE INSERT ON training_jobs
        WHEN NEW.progress < 0 OR NEW.progress > 1
        BEGIN SELECT RAISE(ABORT, 'training progress must be between 0 and 1'); END;
        CREATE TRIGGER IF NOT EXISTS training_jobs_progress_update
        BEFORE UPDATE OF progress ON training_jobs
        WHEN NEW.progress < 0 OR NEW.progress > 1
        BEGIN SELECT RAISE(ABORT, 'training progress must be between 0 and 1'); END;
        """
    )
    connection.execute("PRAGMA user_version = 2")


def _apply_v3(connection: sqlite3.Connection) -> None:
    if connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (3,)).fetchone():
        return
    connection.executescript(PHASE3_SCHEMA)
    connection.execute(
        "INSERT INTO schema_migrations(version, name) VALUES (?, ?)", (3, MIGRATION_003_NAME)
    )
    connection.execute("PRAGMA user_version = 3")


def _audit_migration(
    database_path: Path, action: str, outcome: str, metadata: dict[str, object]
) -> None:
    try:
        with database_connection(database_path) as connection:
            if not connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='audit_logs'"
            ).fetchone():
                return
            columns = {row[1] for row in connection.execute("PRAGMA table_info(audit_logs)")}
            if "public_id" in columns:
                connection.execute(
                    """INSERT INTO audit_logs(
                        action, actor, details, public_id, event_type, actor_type,
                        outcome, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        action,
                        "system",
                        "{}",
                        str(uuid4()),
                        action,
                        "system",
                        outcome,
                        dumps_json(metadata),
                    ),
                )
            else:
                connection.execute(
                    "INSERT INTO audit_logs(action, actor, details) VALUES (?, ?, ?)",
                    (action, "system", dumps_json(metadata)),
                )
            connection.commit()
    except (sqlite3.Error, ValueError):
        logger.exception("migration_audit_write_failed", extra={"action": action})


def initialize_database(
    database_path: Path,
    *,
    backup_dir: Path | None = None,
    auto_backup: bool = True,
    busy_timeout_ms: int = 5000,
    wal_enabled: bool = True,
) -> int:
    """Initialize a fresh database or safely upgrade an existing one to v2."""

    database_path.parent.mkdir(parents=True, exist_ok=True)
    existed = database_path.exists() and database_path.stat().st_size > 0
    version = current_schema_version(database_path)
    if version > SCHEMA_VERSION:
        raise MigrationError(f"database schema {version} is newer than supported {SCHEMA_VERSION}")
    if version in {1, 2} and existed and auto_backup:
        create_verified_backup(database_path, backup_dir or database_path.parent / "backups")
    with database_connection(
        database_path, busy_timeout_ms=busy_timeout_ms, wal_enabled=wal_enabled
    ) as connection:
        try:
            connection.execute("BEGIN")
            if version == 0:
                _apply_v1(connection)
            _apply_v2(connection)
            _apply_v3(connection)
            connection.commit()
        except Exception:
            connection.rollback()
            logger.exception("database_migration_failed")
            raise
    verify_database(database_path)
    logger.info("database_initialized", extra={"schema_version": SCHEMA_VERSION})
    return SCHEMA_VERSION


def upgrade_database(settings: Settings) -> tuple[int, BackupResult | None, str]:
    """Verify, back up when required, upgrade, and post-verify the configured database."""

    path = settings.resolved_database_path
    version = current_schema_version(path)
    backup: BackupResult | None = None
    if version == SCHEMA_VERSION:
        verification = verify_database(path)
        return version, None, verification.integrity_check
    if version in {1, 2}:
        try:
            verify_database(path)
        except Exception as exc:
            _audit_migration(
                path,
                "database_integrity_check_failure",
                "failure",
                {"error": type(exc).__name__, "target_version": SCHEMA_VERSION},
            )
            raise
        if not settings.database_auto_backup:
            raise MigrationError("automatic backup is required for an existing database upgrade")
        backup = create_verified_backup(path, settings.resolved_backup_dir)
        _audit_migration(path, "database_backup_created", "success", {"filename": backup.filename})
    _audit_migration(
        path, "database_migration_start", "success", {"target_version": SCHEMA_VERSION}
    )
    try:
        initialize_database(
            path,
            backup_dir=settings.resolved_backup_dir,
            auto_backup=False,
            busy_timeout_ms=settings.database_busy_timeout_ms,
            wal_enabled=settings.database_wal,
        )
        verification = verify_database(path)
    except Exception as exc:
        _audit_migration(
            path, "database_migration_failure", "failure", {"error": type(exc).__name__}
        )
        raise
    _audit_migration(
        path, "database_migration_success", "success", {"schema_version": SCHEMA_VERSION}
    )
    return SCHEMA_VERSION, backup, verification.integrity_check


def migration_status(database_path: Path) -> dict[str, object]:
    version = current_schema_version(database_path)
    applied: list[dict[str, object]] = []
    if version:
        with database_connection(database_path) as connection:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(schema_migrations)")}
            if "name" in columns:
                rows = connection.execute(
                    "SELECT version, name, applied_at FROM schema_migrations ORDER BY version"
                )
            else:
                rows = connection.execute(
                    "SELECT version, NULL AS name, applied_at "
                    "FROM schema_migrations ORDER BY version"
                )
            applied = [dict(row) for row in rows]
    return {
        "current_version": version,
        "target_version": SCHEMA_VERSION,
        "migration_status": "current" if version == SCHEMA_VERSION else "upgrade_required",
        "applied_migrations": applied,
    }


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Brud AI verified database migrations")
    parser.add_argument("command", choices=("status", "verify", "backup", "upgrade"))
    args = parser.parse_args(argv)
    settings = get_settings()
    try:
        if args.command == "status":
            print(json.dumps(migration_status(settings.resolved_database_path), default=str))
        elif args.command == "verify":
            print(json.dumps(asdict(verify_database(settings.resolved_database_path)), default=str))
        elif args.command == "backup":
            result = create_verified_backup(
                settings.resolved_database_path, settings.resolved_backup_dir
            )
            print(json.dumps({**asdict(result), "path": result.filename}, default=str))
        elif args.command == "upgrade":
            version, backup, integrity = upgrade_database(settings)
            print(
                json.dumps(
                    {
                        "schema_version": version,
                        "backup": (
                            {
                                "filename": backup.filename,
                                "source_checksum": backup.source_checksum,
                                "backup_checksum": backup.backup_checksum,
                            }
                            if backup
                            else None
                        ),
                        "integrity_check": integrity,
                        "post_migration_checksum": sha256_file(settings.resolved_database_path),
                    }
                )
            )
    except (MigrationError, sqlite3.Error, OSError) as exc:
        print(f"Database migration error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
