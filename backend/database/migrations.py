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
    MIGRATION_004_NAME,
    MIGRATION_005_NAME,
    MIGRATION_006_NAME,
    MIGRATION_007_NAME,
    MIGRATION_008_NAME,
    MIGRATION_009_NAME,
    MIGRATION_010_NAME,
    MIGRATION_011_NAME,
    MIGRATION_012_NAME,
    MIGRATION_013_NAME,
    MIGRATION_014_NAME,
    MIGRATION_015_NAME,
    MIGRATION_016_NAME,
    MIGRATION_017_NAME,
    MIGRATION_018_NAME,
    MIGRATION_019_NAME,
    MIGRATION_020_NAME,
    MIGRATION_021_NAME,
    MIGRATION_022_NAME,
    MIGRATION_023_NAME,
    MIGRATION_024_NAME,
    MIGRATION_025_NAME,
    MIGRATION_026_NAME,
    MIGRATION_027_NAME,
    MIGRATION_028_NAME,
    MIGRATION_029_NAME,
    MIGRATION_030_NAME,
    MIGRATION_031_NAME,
    MIGRATION_032_NAME,
    MIGRATION_033_NAME,
    MIGRATION_034_NAME,
    MIGRATION_035_NAME,
    MIGRATION_036_NAME,
    MIGRATION_037_NAME,
    MIGRATION_038_NAME,
    MIGRATION_039_NAME,
    MIGRATION_040_NAME,
    MIGRATION_041_NAME,
    MIGRATION_042_NAME,
    MIGRATION_043_NAME,
    MIGRATION_044_NAME,
    PHASE2_COLUMNS,
    PHASE2_NEW_TABLES,
    PHASE3_SCHEMA,
    PHASE4_SCHEMA,
    PHASE5_SCHEMA,
    PHASE6_SCHEMA,
    PHASE7_SCHEMA,
    PHASE8_SCHEMA,
    PHASE9_SCHEMA,
    PHASE10_COLUMNS,
    PHASE10_SCHEMA,
    PHASE11_SCHEMA,
    PHASE12_SCHEMA,
    PHASE13_SCHEMA,
    PHASE14_SCHEMA,
    PHASE15_SCHEMA,
    PHASE16_SCHEMA,
    PHASE17_SCHEMA,
    PHASE18_SCHEMA,
    PHASE19_SCHEMA,
    PHASE20_COLUMNS,
    PHASE20_SCHEMA,
    PHASE21A_SCHEMA,
    PHASE22_COLUMNS,
    PHASE23_SCHEMA,
    PHASE24_SCHEMA,
    PHASE25_COLUMNS,
    PHASE25_SCHEMA,
    PHASE26_SCHEMA,
    PHASE27_SCHEMA,
    PHASE28_SCHEMA,
    PHASE29_COLUMNS,
    PHASE29_SCHEMA,
    PHASE30_SCHEMA,
    PHASE31_SCHEMA,
    PHASE32_COLUMNS,
    PHASE33_SCHEMA,
    PHASE34_COLUMNS,
    PHASE35_SCHEMA,
    PHASE36_SCHEMA,
    PHASE37_SCHEMA,
    PHASE38_SCHEMA,
    PHASE39_SCHEMA,
    PHASE40_SCHEMA,
    PHASE41_SCHEMA,
    PHASE42_SCHEMA,
    PHASE43_SCHEMA,
    PHASE44_SCHEMA,
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


def _apply_v4(connection: sqlite3.Connection) -> None:
    if connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (4,)).fetchone():
        return
    connection.executescript(PHASE4_SCHEMA)
    connection.execute(
        "INSERT INTO schema_migrations(version, name) VALUES (?, ?)", (4, MIGRATION_004_NAME)
    )
    connection.execute("PRAGMA user_version = 4")


def _apply_v5(connection: sqlite3.Connection) -> None:
    if connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (5,)).fetchone():
        return
    connection.executescript(PHASE5_SCHEMA)
    connection.execute(
        "INSERT INTO schema_migrations(version, name) VALUES (?, ?)", (5, MIGRATION_005_NAME)
    )
    connection.execute("PRAGMA user_version = 5")


def _apply_v6(connection: sqlite3.Connection) -> None:
    if connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (6,)).fetchone():
        return
    connection.executescript(PHASE6_SCHEMA)
    connection.execute(
        "INSERT INTO schema_migrations(version, name) VALUES (?, ?)", (6, MIGRATION_006_NAME)
    )
    connection.execute("PRAGMA user_version = 6")


def _apply_v7(connection: sqlite3.Connection) -> None:
    if connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (7,)).fetchone():
        return
    connection.executescript(PHASE7_SCHEMA)
    connection.execute(
        "INSERT INTO schema_migrations(version, name) VALUES (?, ?)", (7, MIGRATION_007_NAME)
    )
    connection.execute("PRAGMA user_version = 7")


def _apply_v8(connection: sqlite3.Connection) -> None:
    if connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (8,)).fetchone():
        return
    connection.executescript(PHASE8_SCHEMA)
    connection.execute(
        "INSERT INTO schema_migrations(version, name) VALUES (?, ?)", (8, MIGRATION_008_NAME)
    )
    connection.execute("PRAGMA user_version = 8")


def _apply_v9(connection: sqlite3.Connection) -> None:
    if connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (9,)).fetchone():
        return
    connection.executescript(PHASE9_SCHEMA)
    connection.execute(
        "INSERT INTO schema_migrations(version, name) VALUES (?, ?)", (9, MIGRATION_009_NAME)
    )
    connection.execute("PRAGMA user_version = 9")


def _apply_v10(connection: sqlite3.Connection) -> None:
    if connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (10,)).fetchone():
        return
    for table, columns in PHASE10_COLUMNS.items():
        for name, definition in columns:
            if not _has_column(connection, table, name):
                connection.execute(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {definition}')
    connection.executescript(PHASE10_SCHEMA)
    connection.execute(
        "INSERT INTO schema_migrations(version, name) VALUES (?, ?)", (10, MIGRATION_010_NAME)
    )
    connection.execute("PRAGMA user_version = 10")


def _apply_v11(connection: sqlite3.Connection) -> None:
    if connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (11,)).fetchone():
        return
    connection.executescript(PHASE11_SCHEMA)
    connection.execute(
        "INSERT INTO schema_migrations(version, name) VALUES (?, ?)", (11, MIGRATION_011_NAME)
    )
    connection.execute("PRAGMA user_version = 11")


def _apply_v12(connection: sqlite3.Connection) -> None:
    if connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (12,)).fetchone():
        return
    connection.executescript(PHASE12_SCHEMA)
    connection.execute(
        "INSERT INTO schema_migrations(version, name) VALUES (?, ?)", (12, MIGRATION_012_NAME)
    )
    connection.execute("PRAGMA user_version = 12")


def _apply_v13(connection: sqlite3.Connection) -> None:
    if connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (13,)).fetchone():
        return
    connection.executescript(PHASE13_SCHEMA)
    connection.execute(
        "INSERT INTO schema_migrations(version, name) VALUES (?, ?)", (13, MIGRATION_013_NAME)
    )
    connection.execute("PRAGMA user_version = 13")


def _apply_v14(connection: sqlite3.Connection) -> None:
    if connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (14,)).fetchone():
        return
    connection.executescript(PHASE14_SCHEMA)
    connection.execute(
        "INSERT INTO schema_migrations(version, name) VALUES (?, ?)", (14, MIGRATION_014_NAME)
    )
    connection.execute("PRAGMA user_version = 14")


def _apply_v15(connection: sqlite3.Connection) -> None:
    if connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (15,)).fetchone():
        return
    connection.executescript(PHASE15_SCHEMA)
    connection.execute(
        "INSERT INTO schema_migrations(version, name) VALUES (?, ?)", (15, MIGRATION_015_NAME)
    )
    connection.execute("PRAGMA user_version = 15")


def _apply_v16(connection: sqlite3.Connection) -> None:
    if connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (16,)).fetchone():
        return
    connection.executescript(PHASE16_SCHEMA)
    connection.execute(
        "INSERT INTO schema_migrations(version, name) VALUES (?, ?)", (16, MIGRATION_016_NAME)
    )
    connection.execute("PRAGMA user_version = 16")


def _apply_v17(connection: sqlite3.Connection) -> None:
    if connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (17,)).fetchone():
        return
    connection.executescript(PHASE17_SCHEMA)
    connection.execute(
        "INSERT INTO schema_migrations(version, name) VALUES (?, ?)", (17, MIGRATION_017_NAME)
    )
    connection.execute("PRAGMA user_version = 17")


def _apply_v18(connection: sqlite3.Connection) -> None:
    if connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (18,)).fetchone():
        return
    connection.executescript(PHASE18_SCHEMA)
    connection.execute(
        "INSERT INTO schema_migrations(version, name) VALUES (?, ?)", (18, MIGRATION_018_NAME)
    )
    connection.execute("PRAGMA user_version = 18")


def _apply_v19(connection: sqlite3.Connection) -> None:
    if connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (19,)).fetchone():
        return
    connection.executescript(PHASE19_SCHEMA)
    connection.execute(
        "INSERT INTO schema_migrations(version, name) VALUES (?, ?)", (19, MIGRATION_019_NAME)
    )
    connection.execute("PRAGMA user_version = 19")


def _apply_v20(connection: sqlite3.Connection) -> None:
    if connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (20,)).fetchone():
        return
    for table, columns in PHASE20_COLUMNS.items():
        for name, definition in columns:
            if not _has_column(connection, table, name):
                connection.execute(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {definition}')
    connection.executescript(PHASE20_SCHEMA)
    connection.execute(
        "INSERT INTO schema_migrations(version, name) VALUES (?, ?)", (20, MIGRATION_020_NAME)
    )
    connection.execute("PRAGMA user_version = 20")


def _apply_v21(connection: sqlite3.Connection) -> None:
    if connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (21,)).fetchone():
        return
    connection.executescript(PHASE21A_SCHEMA)
    connection.execute(
        "INSERT INTO schema_migrations(version, name) VALUES (?, ?)", (21, MIGRATION_021_NAME)
    )
    connection.execute("PRAGMA user_version = 21")


def _apply_v22(connection: sqlite3.Connection) -> None:
    if connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (22,)).fetchone():
        return
    for table, columns in PHASE22_COLUMNS.items():
        for name, definition in columns:
            if not _has_column(connection, table, name):
                connection.execute(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {definition}')
    connection.execute(
        "INSERT INTO schema_migrations(version, name) VALUES (?, ?)", (22, MIGRATION_022_NAME)
    )
    connection.execute("PRAGMA user_version = 22")


def _apply_v23(connection: sqlite3.Connection) -> None:
    if connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (23,)).fetchone():
        return
    connection.executescript(PHASE23_SCHEMA)
    connection.execute(
        "INSERT INTO schema_migrations(version, name) VALUES (?, ?)", (23, MIGRATION_023_NAME)
    )
    connection.execute("PRAGMA user_version = 23")


def _apply_v24(connection: sqlite3.Connection) -> None:
    if connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (24,)).fetchone():
        return
    connection.executescript(PHASE24_SCHEMA)
    connection.execute(
        "INSERT INTO schema_migrations(version, name) VALUES (?, ?)", (24, MIGRATION_024_NAME)
    )
    connection.execute("PRAGMA user_version = 24")


def _apply_v25(connection: sqlite3.Connection) -> None:
    if connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (25,)).fetchone():
        return
    for table, columns in PHASE25_COLUMNS.items():
        for name, definition in columns:
            if not _has_column(connection, table, name):
                connection.execute(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {definition}')
    connection.executescript(PHASE25_SCHEMA)
    connection.execute(
        "INSERT INTO schema_migrations(version, name) VALUES (?, ?)", (25, MIGRATION_025_NAME)
    )
    connection.execute("PRAGMA user_version = 25")


def _apply_v26(connection: sqlite3.Connection) -> None:
    if connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (26,)).fetchone():
        return
    connection.executescript(PHASE26_SCHEMA)
    connection.execute(
        "INSERT INTO schema_migrations(version, name) VALUES (?, ?)", (26, MIGRATION_026_NAME)
    )
    connection.execute("PRAGMA user_version = 26")


def _apply_v27(connection: sqlite3.Connection) -> None:
    if connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (27,)).fetchone():
        return
    connection.executescript(PHASE27_SCHEMA)
    connection.execute(
        "INSERT INTO schema_migrations(version, name) VALUES (?, ?)", (27, MIGRATION_027_NAME)
    )
    connection.execute("PRAGMA user_version = 27")


def _apply_v28(connection: sqlite3.Connection) -> None:
    if connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (28,)).fetchone():
        return
    connection.executescript(PHASE28_SCHEMA)
    connection.execute(
        "INSERT INTO schema_migrations(version, name) VALUES (?, ?)", (28, MIGRATION_028_NAME)
    )
    connection.execute("PRAGMA user_version = 28")


def _apply_v29(connection: sqlite3.Connection) -> None:
    if connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (29,)).fetchone():
        return
    for table, columns in PHASE29_COLUMNS.items():
        for name, definition in columns:
            if not _has_column(connection, table, name):
                connection.execute(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {definition}')
    connection.executescript(PHASE29_SCHEMA)
    connection.execute(
        "INSERT INTO schema_migrations(version, name) VALUES (?, ?)", (29, MIGRATION_029_NAME)
    )
    connection.execute("PRAGMA user_version = 29")


def _apply_v30(connection: sqlite3.Connection) -> None:
    if connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (30,)).fetchone():
        return
    connection.executescript(PHASE30_SCHEMA)
    connection.execute(
        "INSERT INTO schema_migrations(version, name) VALUES (?, ?)", (30, MIGRATION_030_NAME)
    )
    connection.execute("PRAGMA user_version = 30")


def _apply_v31(connection: sqlite3.Connection) -> None:
    if connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (31,)).fetchone():
        return
    connection.executescript(PHASE31_SCHEMA)
    connection.execute(
        "INSERT INTO schema_migrations(version, name) VALUES (?, ?)", (31, MIGRATION_031_NAME)
    )
    connection.execute("PRAGMA user_version = 31")


def _apply_v32(connection: sqlite3.Connection) -> None:
    if connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (32,)).fetchone():
        return
    for table, columns in PHASE32_COLUMNS.items():
        for name, definition in columns:
            if not _has_column(connection, table, name):
                connection.execute(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {definition}')
    connection.execute(
        "INSERT INTO schema_migrations(version, name) VALUES (?, ?)", (32, MIGRATION_032_NAME)
    )
    connection.execute("PRAGMA user_version = 32")


def _apply_v33(connection: sqlite3.Connection) -> None:
    if connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (33,)).fetchone():
        return
    connection.executescript(PHASE33_SCHEMA)
    connection.execute(
        "INSERT INTO schema_migrations(version, name) VALUES (?, ?)", (33, MIGRATION_033_NAME)
    )
    connection.execute("PRAGMA user_version = 33")


def _apply_v34(connection: sqlite3.Connection) -> None:
    if connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (34,)).fetchone():
        return
    for table, columns in PHASE34_COLUMNS.items():
        for name, definition in columns:
            if not _has_column(connection, table, name):
                connection.execute(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {definition}')
    connection.execute(
        "INSERT INTO schema_migrations(version, name) VALUES (?, ?)", (34, MIGRATION_034_NAME)
    )
    connection.execute("PRAGMA user_version = 34")


def _apply_v35(connection: sqlite3.Connection) -> None:
    if connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (35,)).fetchone():
        return
    connection.executescript(PHASE35_SCHEMA)
    connection.execute(
        "INSERT INTO schema_migrations(version, name) VALUES (?, ?)", (35, MIGRATION_035_NAME)
    )
    connection.execute("PRAGMA user_version = 35")


def _apply_v36(connection: sqlite3.Connection) -> None:
    if connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (36,)).fetchone():
        return
    connection.executescript(PHASE36_SCHEMA)
    connection.execute(
        "INSERT INTO schema_migrations(version, name) VALUES (?, ?)", (36, MIGRATION_036_NAME)
    )
    connection.execute("PRAGMA user_version = 36")


def _apply_v37(connection: sqlite3.Connection) -> None:
    if connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (37,)).fetchone():
        return
    connection.executescript(PHASE37_SCHEMA)
    connection.execute(
        "INSERT INTO schema_migrations(version, name) VALUES (?, ?)", (37, MIGRATION_037_NAME)
    )
    connection.execute("PRAGMA user_version = 37")


def _apply_v38(connection: sqlite3.Connection) -> None:
    if connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (38,)).fetchone():
        return
    connection.executescript(PHASE38_SCHEMA)
    connection.execute(
        "INSERT INTO schema_migrations(version, name) VALUES (?, ?)", (38, MIGRATION_038_NAME)
    )
    connection.execute("PRAGMA user_version = 38")


def _apply_v39(connection: sqlite3.Connection) -> None:
    if connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (39,)).fetchone():
        return
    connection.executescript(PHASE39_SCHEMA)
    connection.execute(
        "INSERT INTO schema_migrations(version, name) VALUES (?, ?)", (39, MIGRATION_039_NAME)
    )
    connection.execute("PRAGMA user_version = 39")


def _apply_v40(connection: sqlite3.Connection) -> None:
    if connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (40,)).fetchone():
        return
    connection.executescript(PHASE40_SCHEMA)
    connection.execute(
        "INSERT INTO schema_migrations(version, name) VALUES (?, ?)", (40, MIGRATION_040_NAME)
    )
    connection.execute("PRAGMA user_version = 40")


def _apply_v41(connection: sqlite3.Connection) -> None:
    if connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (41,)).fetchone():
        return
    connection.executescript(PHASE41_SCHEMA)
    connection.execute(
        "INSERT INTO schema_migrations(version, name) VALUES (?, ?)", (41, MIGRATION_041_NAME)
    )
    connection.execute("PRAGMA user_version = 41")


def _apply_v42(connection: sqlite3.Connection) -> None:
    if connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (42,)).fetchone():
        return
    connection.executescript(PHASE42_SCHEMA)
    connection.execute(
        "INSERT INTO schema_migrations(version, name) VALUES (?, ?)", (42, MIGRATION_042_NAME)
    )
    connection.execute("PRAGMA user_version = 42")


def _apply_v43(connection: sqlite3.Connection) -> None:
    if connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (43,)).fetchone():
        return
    connection.executescript(PHASE43_SCHEMA)
    connection.execute(
        "INSERT INTO schema_migrations(version, name) VALUES (?, ?)", (43, MIGRATION_043_NAME)
    )
    connection.execute("PRAGMA user_version = 43")


def _apply_v44(connection: sqlite3.Connection) -> None:
    if connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (44,)).fetchone():
        return
    connection.executescript(PHASE44_SCHEMA)
    connection.execute(
        "INSERT INTO schema_migrations(version, name) VALUES (?, ?)", (44, MIGRATION_044_NAME)
    )
    connection.execute("PRAGMA user_version = 44")


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
    """Initialize a fresh database or safely upgrade an existing one to the current schema."""

    database_path.parent.mkdir(parents=True, exist_ok=True)
    existed = database_path.exists() and database_path.stat().st_size > 0
    version = current_schema_version(database_path)
    if version > SCHEMA_VERSION:
        raise MigrationError(f"database schema {version} is newer than supported {SCHEMA_VERSION}")
    pre_v19_versions = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20}
    if version in pre_v19_versions and existed and auto_backup:
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
            _apply_v4(connection)
            _apply_v5(connection)
            _apply_v6(connection)
            _apply_v7(connection)
            _apply_v8(connection)
            _apply_v9(connection)
            _apply_v10(connection)
            _apply_v11(connection)
            _apply_v12(connection)
            _apply_v13(connection)
            _apply_v14(connection)
            _apply_v15(connection)
            _apply_v16(connection)
            _apply_v17(connection)
            _apply_v18(connection)
            _apply_v19(connection)
            _apply_v20(connection)
            _apply_v21(connection)
            _apply_v22(connection)
            _apply_v23(connection)
            _apply_v24(connection)
            _apply_v25(connection)
            _apply_v26(connection)
            _apply_v27(connection)
            _apply_v28(connection)
            _apply_v29(connection)
            _apply_v30(connection)
            _apply_v31(connection)
            _apply_v32(connection)
            _apply_v33(connection)
            _apply_v34(connection)
            _apply_v35(connection)
            _apply_v36(connection)
            _apply_v37(connection)
            _apply_v38(connection)
            _apply_v39(connection)
            _apply_v40(connection)
            _apply_v41(connection)
            _apply_v42(connection)
            _apply_v43(connection)
            _apply_v44(connection)
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
    if version in {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20}:
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
