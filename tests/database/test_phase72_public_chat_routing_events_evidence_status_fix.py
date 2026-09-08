import sqlite3
from pathlib import Path

import pytest

from backend.database import migrations as db_migrations
from backend.database.migrations import initialize_database
from backend.database.schema import SCHEMA_VERSION

_INSERT = """INSERT INTO public_chat_routing_events(
    public_id, request_id, input_hash, recommended_route, resolved_route,
    route_status, evidence_status, detected_language, safety_status
) VALUES (?, ?, ?, 'tool', 'tool', 'executable', ?, 'en', 'safe')"""

_PRE_072_VALID_EVIDENCE_STATUSES = (
    "grounded", "partially_grounded", "insufficient", "conflicting", "model_only", "none",
)


def test_fresh_database_reaches_schema_version_72(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.db"
    version = initialize_database(db_path)
    assert version == SCHEMA_VERSION
    assert SCHEMA_VERSION >= 72


def test_evidence_status_accepts_deterministic(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.db"
    initialize_database(db_path)
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(_INSERT, ("det1", "r1", "h1", "deterministic"))
        connection.commit()
        stored = connection.execute(
            "SELECT evidence_status FROM public_chat_routing_events WHERE public_id='det1'"
        ).fetchone()[0]
        assert stored == "deterministic"
    finally:
        connection.close()


def test_evidence_status_still_accepts_all_previously_valid_values(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.db"
    initialize_database(db_path)
    connection = sqlite3.connect(db_path)
    try:
        for i, status in enumerate(_PRE_072_VALID_EVIDENCE_STATUSES):
            public_id = f"legacy-status-{i}"
            connection.execute(_INSERT, (public_id, f"r{i}", f"h{i}", status))
            connection.commit()
            stored = connection.execute(
                "SELECT evidence_status FROM public_chat_routing_events WHERE public_id=?",
                (public_id,),
            ).fetchone()[0]
            assert stored == status
    finally:
        connection.close()


def test_evidence_status_still_rejects_invalid_value(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.db"
    initialize_database(db_path)
    connection = sqlite3.connect(db_path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(_INSERT, ("bad1", "r1", "h1", "invalid_test_evidence_status"))
    finally:
        connection.close()


def test_resolved_route_fix_from_phase_071_remains_intact(tmp_path: Path) -> None:
    """The exact combination that failed in Phase 2.3D/E's original finding
    -- resolved_route='tool' AND evidence_status='deterministic' together,
    as the real deterministic-tool route actually writes them -- must now
    insert cleanly. Also confirms migration 071's resolved_route widening
    was not narrowed or reverted by this migration."""
    db_path = tmp_path / "fresh.db"
    initialize_database(db_path)
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(_INSERT, ("combo1", "r1", "h1", "deterministic"))
        connection.commit()
        row = connection.execute(
            "SELECT resolved_route, evidence_status FROM public_chat_routing_events "
            "WHERE public_id='combo1'"
        ).fetchone()
        assert row == ("tool", "deterministic")

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO public_chat_routing_events(
                    public_id, request_id, input_hash, recommended_route, resolved_route,
                    route_status, evidence_status, detected_language, safety_status
                ) VALUES ('bad-route', 'r2', 'h2', 'core_model', 'invalid_test_route',
                    'executable', 'none', 'en', 'safe')"""
            )
    finally:
        connection.close()


def test_public_chat_routing_events_still_append_only_after_fix(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.db"
    initialize_database(db_path)
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(_INSERT, ("ao1", "r1", "h1", "deterministic"))
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE public_chat_routing_events SET evidence_status='none' "
                "WHERE public_id='ao1'"
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("DELETE FROM public_chat_routing_events WHERE public_id='ao1'")
    finally:
        connection.close()


def test_indexes_survive_the_table_reconstruction(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.db"
    initialize_database(db_path)
    connection = sqlite3.connect(db_path)
    try:
        index_names = {
            row[1]
            for row in connection.execute(
                "PRAGMA index_list(public_chat_routing_events)"
            )
        }
        assert {
            "ix_public_chat_routing_events_resolved_route",
            "ix_public_chat_routing_events_created_at",
            "ix_public_chat_routing_events_request_id",
        }.issubset(index_names)
    finally:
        connection.close()


def test_no_foreign_key_violations_after_migration_072(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.db"
    initialize_database(db_path)
    connection = sqlite3.connect(db_path)
    try:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert [row[0] for row in connection.execute("PRAGMA integrity_check")] == ["ok"]
    finally:
        connection.close()


def test_migration_072_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.db"
    initialize_database(db_path)
    version_again = initialize_database(db_path)
    assert version_again == SCHEMA_VERSION


def test_upgrade_from_pre_072_database_preserves_existing_rows_and_ids(
    tmp_path: Path,
) -> None:
    """Simulates a real pre-existing database that only had migrations 1-71
    applied (the old, buggy evidence_status constraint, but with 071's
    resolved_route fix already in place) -- exactly the upgrade path a
    real deployed database would take after Phase 2.3E -- and confirms
    migration 072 both preserves its existing rows/ids untouched AND
    accepts the previously-rejected 'deterministic' value afterward."""

    db_path = tmp_path / "legacy.db"
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("BEGIN")
        db_migrations._apply_v1(connection)
        for version in range(2, 72):
            getattr(db_migrations, f"_apply_v{version}")(connection)
        connection.commit()

        # Old constraint is active: resolved_route='tool' now works (071
        # already applied), but evidence_status='deterministic' does not.
        connection.execute(
            """INSERT INTO public_chat_routing_events(
                public_id, request_id, input_hash, recommended_route, resolved_route,
                route_status, evidence_status, detected_language, safety_status
            ) VALUES ('legacy-row', 'r0', 'h0', 'core_model', 'core_model',
                'executable', 'model_only', 'en', 'safe')"""
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(_INSERT, ("legacy-det", "r1", "h1", "deterministic"))
        legacy_row_id = connection.execute(
            "SELECT id FROM public_chat_routing_events WHERE public_id='legacy-row'"
        ).fetchone()[0]
    finally:
        connection.close()

    version = initialize_database(db_path)
    assert version == SCHEMA_VERSION

    connection = sqlite3.connect(db_path)
    try:
        row = connection.execute(
            "SELECT id, evidence_status FROM public_chat_routing_events "
            "WHERE public_id='legacy-row'"
        ).fetchone()
        assert row == (legacy_row_id, "model_only")

        connection.execute(_INSERT, ("post-fix-det", "r2", "h2", "deterministic"))
        connection.commit()
        new_id, new_status = connection.execute(
            "SELECT id, evidence_status FROM public_chat_routing_events "
            "WHERE public_id='post-fix-det'"
        ).fetchone()
        assert new_status == "deterministic"
        assert new_id > legacy_row_id
    finally:
        connection.close()
