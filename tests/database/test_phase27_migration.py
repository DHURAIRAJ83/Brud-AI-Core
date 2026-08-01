import sqlite3
from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.connection import database_connection
from backend.database.migrations import (
    _apply_v1,
    _apply_v2,
    _apply_v3,
    _apply_v4,
    _apply_v5,
    _apply_v6,
    _apply_v7,
    _apply_v8,
    _apply_v9,
    _apply_v10,
    _apply_v11,
    _apply_v12,
    _apply_v13,
    _apply_v14,
    _apply_v15,
    _apply_v16,
    _apply_v17,
    _apply_v18,
    _apply_v19,
    _apply_v20,
    _apply_v21,
    _apply_v22,
    _apply_v23,
    _apply_v24,
    _apply_v25,
    _apply_v26,
    current_schema_version,
    initialize_database,
    upgrade_database,
)
from backend.database.schema import SCHEMA_VERSION

PHASE27_TABLES = {
    "governance_review_items",
    "governance_review_issues",
    "governance_duplicate_groups",
    "governance_duplicate_group_members",
    "governance_conflict_groups",
    "governance_conflict_group_members",
    "governance_resolutions",
    "governance_target_approvals",
    "governance_review_events",
}

APPLY_THROUGH_V26 = (
    _apply_v1,
    _apply_v2,
    _apply_v3,
    _apply_v4,
    _apply_v5,
    _apply_v6,
    _apply_v7,
    _apply_v8,
    _apply_v9,
    _apply_v10,
    _apply_v11,
    _apply_v12,
    _apply_v13,
    _apply_v14,
    _apply_v15,
    _apply_v16,
    _apply_v17,
    _apply_v18,
    _apply_v19,
    _apply_v20,
    _apply_v21,
    _apply_v22,
    _apply_v23,
    _apply_v24,
    _apply_v25,
    _apply_v26,
)


def _existing_tables(connection) -> set[str]:
    return {
        row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }


def _insert_document(connection, public_id: str) -> int:
    connection.execute(
        """INSERT INTO document_sources(
            public_id, original_filename, stored_filename, document_type, mime_type,
            file_size_bytes, checksum_sha256, page_count, extraction_strategy, status,
            created_by_admin_public_id
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            public_id,
            "a.pdf",
            f"{public_id}-stored.pdf",
            "pdf",
            "application/pdf",
            1024,
            f"hash-{public_id}",
            1,
            "auto",
            "review_ready",
            "admin-1",
        ),
    )
    return connection.execute(
        "SELECT id FROM document_sources WHERE public_id=?", (public_id,)
    ).fetchone()[0]


def _insert_review_item(connection, public_id: str, entity_public_id: str) -> int:
    connection.execute(
        """INSERT INTO governance_review_items(public_id, review_code, entity_type,
        entity_public_id, created_by_admin_public_id) VALUES (?,?,?,?,?)""",
        (public_id, public_id.upper(), "document_page", entity_public_id, "admin-1"),
    )
    return connection.execute(
        "SELECT id FROM governance_review_items WHERE public_id=?", (public_id,)
    ).fetchone()[0]


def test_fresh_database_reaches_schema_27(tmp_path: Path) -> None:
    database = tmp_path / "fresh.db"
    initialize_database(database)
    assert current_schema_version(database) == SCHEMA_VERSION
    assert SCHEMA_VERSION >= 27
    with database_connection(database) as connection:
        assert PHASE27_TABLES <= _existing_tables(connection)
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert not list(connection.execute("PRAGMA foreign_key_check"))
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_schema_26_upgrades_to_27_and_preserves_existing_data(tmp_path: Path) -> None:
    database = tmp_path / "v26.db"
    with database_connection(database) as connection:
        for apply in APPLY_THROUGH_V26:
            apply(connection)
        _insert_document(connection, "00000000-0000-0000-0000-000000000d27")
        connection.commit()
    assert current_schema_version(database) == 26

    settings = Settings(
        database_path=database,
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
    )
    version, _backup, integrity = upgrade_database(settings)
    assert version == SCHEMA_VERSION
    assert SCHEMA_VERSION >= 27
    assert integrity == "ok"

    with database_connection(database) as connection:
        assert PHASE27_TABLES <= _existing_tables(connection)
        assert not list(connection.execute("PRAGMA foreign_key_check"))
        row = connection.execute(
            "SELECT original_filename FROM document_sources WHERE public_id=?",
            ("00000000-0000-0000-0000-000000000d27",),
        ).fetchone()
        assert row["original_filename"] == "a.pdf"


def test_governance_review_items_requires_valid_entity_type_status_priority(
    tmp_path: Path,
) -> None:
    database = tmp_path / "check.db"
    initialize_database(database)
    with database_connection(database) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO governance_review_items(public_id, review_code, entity_type,
                entity_public_id, created_by_admin_public_id) VALUES (?,?,?,?,?)""",
                ("ri-bad", "RI-BAD", "not_a_real_entity", "doc-page-1", "admin-1"),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO governance_review_items(public_id, review_code, entity_type,
                entity_public_id, status, created_by_admin_public_id) VALUES (?,?,?,?,?,?)""",
                ("ri-bad2", "RI-BAD2", "document_page", "doc-page-1", "not_a_status", "admin-1"),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO governance_review_items(public_id, review_code, entity_type,
                entity_public_id, priority, created_by_admin_public_id)
                VALUES (?,?,?,?,?,?)""",
                ("ri-bad3", "RI-BAD3", "document_page", "doc-page-1", "urgentish", "admin-1"),
            )
        connection.execute(
            """INSERT INTO governance_review_items(public_id, review_code, entity_type,
            entity_public_id, created_by_admin_public_id) VALUES (?,?,?,?,?)""",
            ("ri-1", "RI-1", "document_page", "doc-page-1", "admin-1"),
        )
        connection.commit()
        row = connection.execute(
            "SELECT status, priority FROM governance_review_items WHERE public_id=?", ("ri-1",)
        ).fetchone()
        assert row["status"] == "open"
        assert row["priority"] == "normal"


def test_governance_review_items_unique_open_item_per_entity(tmp_path: Path) -> None:
    database = tmp_path / "unique.db"
    initialize_database(database)
    with database_connection(database) as connection:
        connection.execute(
            """INSERT INTO governance_review_items(public_id, review_code, entity_type,
            entity_public_id, created_by_admin_public_id) VALUES (?,?,?,?,?)""",
            ("ri-2", "RI-2", "document_page", "doc-page-2", "admin-1"),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO governance_review_items(public_id, review_code, entity_type,
                entity_public_id, created_by_admin_public_id) VALUES (?,?,?,?,?)""",
                ("ri-3", "RI-3", "document_page", "doc-page-2", "admin-1"),
            )


def test_governance_review_issues_severity_and_blocking_are_independent(
    tmp_path: Path,
) -> None:
    database = tmp_path / "issues.db"
    initialize_database(database)
    with database_connection(database) as connection:
        item_id = _insert_review_item(connection, "ri-4", "doc-page-4")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO governance_review_issues(public_id, review_item_id, issue_code,
                issue_category, severity, message, detector) VALUES (?,?,?,?,?,?,?)""",
                ("iss-bad", item_id, "X1", "not_a_category", "critical", "msg", "det"),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO governance_review_issues(public_id, review_item_id, issue_code,
                issue_category, severity, message, detector) VALUES (?,?,?,?,?,?,?)""",
                ("iss-bad2", item_id, "X1", "language_quality", "fatal", "msg", "det"),
            )
        connection.execute(
            """INSERT INTO governance_review_issues(public_id, review_item_id, issue_code,
            issue_category, severity, is_blocking, message, detector)
            VALUES (?,?,?,?,?,?,?,?)""",
            ("iss-1", item_id, "X1", "language_quality", "warning", 0, "msg", "det"),
        )
        connection.execute(
            """INSERT INTO governance_review_issues(public_id, review_item_id, issue_code,
            issue_category, severity, is_blocking, message, detector)
            VALUES (?,?,?,?,?,?,?,?)""",
            ("iss-2", item_id, "X2", "rights_restriction", "info", 1, "msg", "det"),
        )
        connection.commit()
        rows = {
            row["public_id"]: row["is_blocking"]
            for row in connection.execute(
                "SELECT public_id, is_blocking FROM governance_review_issues"
            )
        }
        assert rows["iss-1"] == 0
        assert rows["iss-2"] == 1


def test_governance_review_issues_facts_are_append_only_but_resolved_at_is_not(
    tmp_path: Path,
) -> None:
    database = tmp_path / "issues_append.db"
    initialize_database(database)
    with database_connection(database) as connection:
        item_id = _insert_review_item(connection, "ri-5", "doc-page-5")
        connection.execute(
            """INSERT INTO governance_review_issues(public_id, review_item_id, issue_code,
            issue_category, severity, message, detector) VALUES (?,?,?,?,?,?,?)""",
            ("iss-3", item_id, "X1", "language_quality", "warning", "msg", "det"),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE governance_review_issues SET severity='critical' WHERE public_id=?",
                ("iss-3",),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("DELETE FROM governance_review_issues WHERE public_id=?", ("iss-3",))
        connection.execute(
            "UPDATE governance_review_issues SET resolved_at=CURRENT_TIMESTAMP WHERE public_id=?",
            ("iss-3",),
        )
        connection.commit()
        row = connection.execute(
            "SELECT resolved_at FROM governance_review_issues WHERE public_id=?", ("iss-3",)
        ).fetchone()
        assert row["resolved_at"] is not None


def test_governance_duplicate_group_membership_prevents_duplicate_rows(
    tmp_path: Path,
) -> None:
    database = tmp_path / "dupe_groups.db"
    initialize_database(database)
    with database_connection(database) as connection:
        connection.execute(
            """INSERT INTO governance_duplicate_groups(public_id, group_code, duplicate_type,
            match_reason) VALUES (?,?,?,?)""",
            ("dg-1", "DG-1", "exact", "identical content hash"),
        )
        group_id = connection.execute(
            "SELECT id FROM governance_duplicate_groups WHERE public_id=?", ("dg-1",)
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO governance_duplicate_group_members(group_id, entity_type,
            entity_public_id, role) VALUES (?,?,?,?)""",
            (group_id, "manual_data_record", "mdr-1", "canonical"),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO governance_duplicate_group_members(group_id, entity_type,
                entity_public_id, role) VALUES (?,?,?,?)""",
                (group_id, "manual_data_record", "mdr-1", "member"),
            )


def test_governance_resolutions_require_a_group_and_are_append_only(tmp_path: Path) -> None:
    database = tmp_path / "resolutions.db"
    initialize_database(database)
    with database_connection(database) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO governance_resolutions(public_id, resolution_action,
                resolution_reason, performed_by_admin_public_id) VALUES (?,?,?,?)""",
                ("res-bad", "keep_all", "no group given", "admin-1"),
            )
        connection.execute(
            """INSERT INTO governance_duplicate_groups(public_id, group_code, duplicate_type,
            match_reason) VALUES (?,?,?,?)""",
            ("dg-2", "DG-2", "normalized", "same normalized text"),
        )
        group_id = connection.execute(
            "SELECT id FROM governance_duplicate_groups WHERE public_id=?", ("dg-2",)
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO governance_resolutions(public_id, duplicate_group_id,
            resolution_action, resolution_reason, performed_by_admin_public_id)
            VALUES (?,?,?,?,?)""",
            ("res-1", group_id, "not_a_duplicate", "different senses", "admin-1"),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE governance_resolutions SET resolution_reason='changed' WHERE public_id=?",
                ("res-1",),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("DELETE FROM governance_resolutions WHERE public_id=?", ("res-1",))


def test_governance_target_approvals_are_append_only_new_row_per_decision(
    tmp_path: Path,
) -> None:
    database = tmp_path / "approvals.db"
    initialize_database(database)
    with database_connection(database) as connection:
        item_id = _insert_review_item(connection, "ri-6", "doc-page-6")
        connection.execute(
            """INSERT INTO governance_target_approvals(public_id, review_item_id, entity_type,
            entity_public_id, target_use, decision, decision_code,
            decided_by_admin_public_id) VALUES (?,?,?,?,?,?,?,?)""",
            ("ta-1", item_id, "document_page", "doc-page-6", "rag", "blocked",
             "RIGHTS_UNVERIFIED", "admin-1"),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE governance_target_approvals SET decision='allowed' WHERE public_id=?",
                ("ta-1",),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "DELETE FROM governance_target_approvals WHERE public_id=?", ("ta-1",)
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO governance_target_approvals(public_id, review_item_id,
                entity_type, entity_public_id, target_use, decision, decision_code,
                decided_by_admin_public_id) VALUES (?,?,?,?,?,?,?,?)""",
                ("ta-bad", item_id, "document_page", "doc-page-6", "rag", "not_a_decision",
                 "CODE", "admin-1"),
            )


def test_governance_review_events_are_append_only(tmp_path: Path) -> None:
    database = tmp_path / "events.db"
    initialize_database(database)
    with database_connection(database) as connection:
        item_id = _insert_review_item(connection, "ri-7", "doc-page-7")
        connection.execute(
            """INSERT INTO governance_review_events(public_id, review_item_id, event_type,
            performed_by_admin_public_id) VALUES (?,?,?,?)""",
            ("gev-1", item_id, "review_item_created", "admin-1"),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE governance_review_events SET notes='changed' WHERE public_id=?",
                ("gev-1",),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "DELETE FROM governance_review_events WHERE public_id=?", ("gev-1",)
            )
