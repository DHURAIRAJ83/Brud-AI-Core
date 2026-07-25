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
    current_schema_version,
    initialize_database,
    sha256_file,
    upgrade_database,
)
from backend.database.schema import SCHEMA_VERSION

PHASE18_TABLES = {
    "feedback_policies",
    "feedback_subjects",
    "feedback_events",
    "feedback_classifications",
    "feedback_attachments",
    "feedback_review_queues",
    "feedback_review_assignments",
    "feedback_human_reviews",
    "feedback_corrected_responses",
    "feedback_privacy_findings",
    "feedback_safety_findings",
    "feedback_quality_assessments",
    "feedback_dataset_candidates",
    "feedback_candidate_versions",
    "feedback_candidate_issues",
    "feedback_candidate_approvals",
    "feedback_regression_suites",
    "feedback_regression_fixtures",
    "feedback_regression_runs",
    "feedback_regression_results",
    "feedback_model_comparisons",
    "feedback_improvement_reports",
    "feedback_manifests",
}

APPLY_THROUGH_V17 = (
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
)


def test_fresh_database_reaches_schema_18(tmp_path: Path) -> None:
    database = tmp_path / "fresh.db"
    initialize_database(database)
    assert current_schema_version(database) == SCHEMA_VERSION
    with database_connection(database) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert PHASE18_TABLES <= tables
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_migration_017_is_unchanged_in_isolation(tmp_path: Path) -> None:
    """Proves migration 017 still behaves exactly as it did before Phase 18 existed."""
    database = tmp_path / "v17_only.db"
    with database_connection(database) as connection:
        for apply in APPLY_THROUGH_V17:
            apply(connection)
        connection.commit()
    assert current_schema_version(database) == 17
    with database_connection(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 17
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {"conversation_memory_policies", "memory_items"} <= tables
        assert not (PHASE18_TABLES & tables)
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_schema_17_upgrades_to_18(tmp_path: Path) -> None:
    database = tmp_path / "v17.db"
    with database_connection(database) as connection:
        for apply in APPLY_THROUGH_V17:
            apply(connection)
        connection.execute(
            "INSERT INTO dataset_sources(name,source_type,status,public_id) VALUES (?,?,?,?)",
            ("Preserved Phase17 Row", "manual", "draft", "00000000-0000-0000-0000-000000000099"),
        )
        connection.commit()
    assert current_schema_version(database) == 17
    settings = Settings(
        database_path=database,
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
    )
    version, backup, integrity = upgrade_database(settings)
    assert version == SCHEMA_VERSION
    assert backup is not None and backup.path.is_file()
    assert sha256_file(backup.path) == backup.backup_checksum
    assert integrity == "ok"
    with database_connection(database) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        indexes = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='index'")
        }
        triggers = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='trigger'")
        }
        assert PHASE18_TABLES <= tables
        assert {
            "ix_feedback_events_subject",
            "ix_feedback_dataset_candidates_status",
            "ix_feedback_regression_runs_suite",
        } <= indexes
        assert {
            "feedback_subjects_immutable_update",
            "feedback_classifications_immutable_update",
            "feedback_attachments_immutable_update",
            "feedback_human_reviews_immutable_update",
            "feedback_privacy_findings_immutable_update",
            "feedback_safety_findings_immutable_update",
            "feedback_quality_assessments_immutable_update",
            "feedback_candidate_versions_immutable_update",
            "feedback_candidate_issues_immutable_update",
            "feedback_candidate_approvals_immutable_update",
            "feedback_regression_fixtures_immutable_update",
            "feedback_regression_results_immutable_update",
            "feedback_model_comparisons_immutable_update",
            "feedback_improvement_reports_immutable_update",
            "feedback_manifests_immutable_update",
        } <= triggers
        assert (
            connection.execute("SELECT name FROM dataset_sources").fetchone()[0]
            == "Preserved Phase17 Row"
        )
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_schema_18_upgrade_is_a_no_op(tmp_path: Path) -> None:
    database = tmp_path / "already_current.db"
    initialize_database(database)
    settings = Settings(
        database_path=database,
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
    )
    version, backup, integrity = upgrade_database(settings)
    assert version == SCHEMA_VERSION
    assert backup is None
    assert integrity == "ok"
    assert not (tmp_path / "backups").exists() or not list((tmp_path / "backups").iterdir())


def test_migration_18_is_idempotent(tmp_path: Path) -> None:
    database = tmp_path / "idempotent.db"
    initialize_database(database)
    initialize_database(database)
    initialize_database(database)
    with database_connection(database) as connection:
        rows = connection.execute(
            "SELECT COUNT(*) FROM schema_migrations WHERE version = 18"
        ).fetchone()
        assert rows[0] == 1
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_phase18_tables_indexes_and_triggers_are_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "first.db"
    second = tmp_path / "second.db"
    initialize_database(first)
    initialize_database(second)
    with database_connection(first) as a, database_connection(second) as b:
        objects_a = {
            (row[0], row[1])
            for row in a.execute(
                "SELECT type, name FROM sqlite_master WHERE type IN ('table','index','trigger')"
            )
        }
        objects_b = {
            (row[0], row[1])
            for row in b.execute(
                "SELECT type, name FROM sqlite_master WHERE type IN ('table','index','trigger')"
            )
        }
        assert objects_a == objects_b


def test_feedback_lifecycle_tables_are_mutable(tmp_path: Path) -> None:
    """policies/events/review queues/review assignments/dataset candidates/
    regression suites are lifecycle rows."""

    database = tmp_path / "mutable.db"
    initialize_database(database)
    with database_connection(database) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            """INSERT INTO feedback_policies(public_id,name,
            created_by_admin_public_id) VALUES (?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000m1", "policy",
                "00000000-0000-0000-0000-000000000001",
            ),
        )
        connection.commit()
        connection.execute(
            "UPDATE feedback_policies SET lifecycle_status='active' WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000m1",),
        )
        connection.commit()
        row = connection.execute(
            "SELECT lifecycle_status FROM feedback_policies WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000m1",),
        ).fetchone()
        assert row[0] == "active"


def test_feedback_corrected_responses_are_mutable(tmp_path: Path) -> None:
    """Deviation from a literal reading of the spec: a correction needs a
    create(draft)->validate/reject two-phase flow, exactly like Phase 16's
    rag_grounded_requests and Phase 17's memory_evaluation_runs."""

    database = tmp_path / "corrections_mutable.db"
    initialize_database(database)
    with database_connection(database) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            """INSERT INTO feedback_subjects(public_id,subject_type,
            subject_reference_public_id,output_checksum_sha256) VALUES (?,?,?,?)""",
            ("00000000-0000-0000-0000-0000000000c1", "model_release", "rel1", "a" * 64),
        )
        subject_id = connection.execute(
            "SELECT id FROM feedback_subjects WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000c1",),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO feedback_policies(public_id,name,
            created_by_admin_public_id) VALUES (?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000c2", "policy",
                "00000000-0000-0000-0000-000000000001",
            ),
        )
        policy_id = connection.execute(
            "SELECT id FROM feedback_policies WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000c2",),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO feedback_events(public_id,feedback_policy_id,subject_id,
            participant_scope_key,feedback_type,created_by_admin_public_id)
            VALUES (?,?,?,?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000c3", policy_id, subject_id,
                "admin:00000000-0000-0000-0000-000000000001", "correction",
                "00000000-0000-0000-0000-000000000001",
            ),
        )
        event_id = connection.execute(
            "SELECT id FROM feedback_events WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000c3",),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO feedback_corrected_responses(public_id,feedback_event_id,
            original_output_checksum_sha256,corrected_response_text,
            corrected_response_checksum_sha256,created_by_admin_public_id)
            VALUES (?,?,?,?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000c4", event_id, "a" * 64, "corrected text",
                "b" * 64, "00000000-0000-0000-0000-000000000001",
            ),
        )
        connection.commit()
        connection.execute(
            """UPDATE feedback_corrected_responses SET validation_status='validated'
            WHERE public_id=?""",
            ("00000000-0000-0000-0000-0000000000c4",),
        )
        connection.commit()
        row = connection.execute(
            "SELECT validation_status FROM feedback_corrected_responses WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000c4",),
        ).fetchone()
        assert row[0] == "validated"


def test_feedback_regression_runs_are_mutable(tmp_path: Path) -> None:
    """feedback_regression_runs needs a create(draft)->execute(completed)
    two-phase flow, exactly like Phase 16's rag_evaluation_runs and Phase
    17's memory_evaluation_runs -- deliberately not append-only despite the
    literal spec table list."""

    database = tmp_path / "regression_runs_mutable.db"
    initialize_database(database)
    with database_connection(database) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            """INSERT INTO feedback_regression_suites(public_id,name,
            created_by_admin_public_id) VALUES (?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000r1", "suite",
                "00000000-0000-0000-0000-000000000001",
            ),
        )
        suite_id = connection.execute(
            "SELECT id FROM feedback_regression_suites WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000r1",),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO feedback_regression_runs(public_id,suite_id,model_assignment_id,
            created_by_admin_public_id) VALUES (?,?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000r2", suite_id, 1,
                "00000000-0000-0000-0000-000000000001",
            ),
        )
        connection.commit()
        connection.execute(
            "UPDATE feedback_regression_runs SET status='completed' WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000r2",),
        )
        connection.commit()
        row = connection.execute(
            "SELECT status FROM feedback_regression_runs WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000r2",),
        ).fetchone()
        assert row[0] == "completed"


def test_append_only_phase18_tables_reject_updates(tmp_path: Path) -> None:
    database = tmp_path / "append_only.db"
    initialize_database(database)
    with database_connection(database) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            """INSERT INTO feedback_subjects(public_id,subject_type,
            subject_reference_public_id,output_checksum_sha256) VALUES (?,?,?,?)""",
            ("00000000-0000-0000-0000-0000000000b1", "model_release", "rel1", "a" * 64),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE feedback_subjects SET output_checksum_sha256='x' WHERE public_id=?",
                ("00000000-0000-0000-0000-0000000000b1",),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "DELETE FROM feedback_subjects WHERE public_id=?",
                ("00000000-0000-0000-0000-0000000000b1",),
            )

        connection.execute(
            """INSERT INTO feedback_policies(public_id,name,
            created_by_admin_public_id) VALUES (?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000b2", "policy",
                "00000000-0000-0000-0000-000000000001",
            ),
        )
        policy_id = connection.execute(
            "SELECT id FROM feedback_policies WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000b2",),
        ).fetchone()[0]
        subject_id = connection.execute(
            "SELECT id FROM feedback_subjects WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000b1",),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO feedback_events(public_id,feedback_policy_id,subject_id,
            participant_scope_key,feedback_type,created_by_admin_public_id)
            VALUES (?,?,?,?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000b3", policy_id, subject_id,
                "admin:00000000-0000-0000-0000-000000000001", "thumbs_up",
                "00000000-0000-0000-0000-000000000001",
            ),
        )
        event_id = connection.execute(
            "SELECT id FROM feedback_events WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000b3",),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO feedback_classifications(public_id,feedback_event_id,category)
            VALUES (?,?,?)""",
            ("00000000-0000-0000-0000-0000000000b4", event_id, "helpful"),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE feedback_classifications SET category='unhelpful' WHERE public_id=?",
                ("00000000-0000-0000-0000-0000000000b4",),
            )
