import sqlite3
from pathlib import Path

import pytest

from backend.database import migrations as db_migrations
from backend.database.migrations import initialize_database
from backend.database.schema import SCHEMA_VERSION

_INSERT = """INSERT INTO public_chat_routing_events(
    public_id, request_id, input_hash, recommended_route, resolved_route,
    route_status, evidence_status, detected_language, safety_status
) VALUES (?, ?, ?, ?, ?, 'executable', 'model_only', 'en', 'safe')"""

_PRE_071_VALID_ROUTES = (
    "core_model", "approved_rag", "memory", "clarify", "refuse", "insufficient",
)


def test_fresh_database_reaches_schema_version_71(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.db"
    version = initialize_database(db_path)
    assert version == SCHEMA_VERSION
    assert SCHEMA_VERSION >= 71


def test_resolved_route_accepts_tool_and_trusted_web(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.db"
    initialize_database(db_path)
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(_INSERT, ("tool1", "r1", "h1", "tool", "tool"))
        connection.execute(_INSERT, ("web1", "r2", "h2", "trusted_web", "trusted_web"))
        connection.commit()
        rows = dict(
            connection.execute(
                "SELECT public_id, resolved_route FROM public_chat_routing_events "
                "WHERE public_id IN ('tool1', 'web1')"
            ).fetchall()
        )
        assert rows == {"tool1": "tool", "web1": "trusted_web"}
    finally:
        connection.close()


def test_resolved_route_still_accepts_all_previously_valid_values(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.db"
    initialize_database(db_path)
    connection = sqlite3.connect(db_path)
    try:
        for i, route in enumerate(_PRE_071_VALID_ROUTES):
            public_id = f"legacy-route-{i}"
            connection.execute(_INSERT, (public_id, f"r{i}", f"h{i}", route, route))
            connection.commit()
            stored = connection.execute(
                "SELECT resolved_route FROM public_chat_routing_events WHERE public_id=?",
                (public_id,),
            ).fetchone()[0]
            assert stored == route
    finally:
        connection.close()


def test_resolved_route_still_rejects_invalid_value(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.db"
    initialize_database(db_path)
    connection = sqlite3.connect(db_path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                _INSERT, ("bad1", "r1", "h1", "core_model", "invalid_test_route")
            )
    finally:
        connection.close()


def test_public_chat_routing_events_still_append_only_after_fix(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.db"
    initialize_database(db_path)
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(_INSERT, ("ao1", "r1", "h1", "tool", "tool"))
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE public_chat_routing_events SET resolved_route='refuse' "
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


def test_no_foreign_key_violations_after_migration_071(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.db"
    initialize_database(db_path)
    connection = sqlite3.connect(db_path)
    try:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert [row[0] for row in connection.execute("PRAGMA integrity_check")] == ["ok"]
    finally:
        connection.close()


def test_migration_071_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.db"
    initialize_database(db_path)
    version_again = initialize_database(db_path)
    assert version_again == SCHEMA_VERSION


def test_upgrade_from_pre_071_database_preserves_existing_rows_and_ids(
    tmp_path: Path,
) -> None:
    """Simulates a real pre-existing database that only had migrations 1-70
    applied (the old, buggy resolved_route constraint) -- exactly the
    upgrade path a real deployed database would take -- and confirms
    migration 071 both preserves its existing rows/ids untouched AND
    accepts the previously-rejected values afterward."""

    db_path = tmp_path / "legacy.db"
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("BEGIN")
        db_migrations._apply_v1(connection)
        for version in range(2, 71):
            getattr(db_migrations, f"_apply_v{version}")(connection)
        connection.commit()

        # Old constraint is active: a legacy row inserts fine, 'tool' does not.
        connection.execute(_INSERT, ("legacy-row", "r0", "h0", "core_model", "core_model"))
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(_INSERT, ("legacy-tool", "r1", "h1", "tool", "tool"))
        legacy_row_id = connection.execute(
            "SELECT id FROM public_chat_routing_events WHERE public_id='legacy-row'"
        ).fetchone()[0]
    finally:
        connection.close()

    # Upgrade via the real, public entrypoint -- exactly what a real
    # deployment would run.
    version = initialize_database(db_path)
    assert version == SCHEMA_VERSION

    connection = sqlite3.connect(db_path)
    try:
        # The legacy row survived the table-reconstruction migration with
        # its original id and value intact.
        row = connection.execute(
            "SELECT id, resolved_route FROM public_chat_routing_events "
            "WHERE public_id='legacy-row'"
        ).fetchone()
        assert row == (legacy_row_id, "core_model")

        # The previously-rejected value is now accepted, and a fresh
        # AUTOINCREMENT id is issued above the preserved legacy id (not
        # reset to 1 by the table rebuild).
        connection.execute(_INSERT, ("post-fix-tool", "r2", "h2", "tool", "tool"))
        connection.commit()
        new_id, new_route = connection.execute(
            "SELECT id, resolved_route FROM public_chat_routing_events "
            "WHERE public_id='post-fix-tool'"
        ).fetchone()
        assert new_route == "tool"
        assert new_id > legacy_row_id
    finally:
        connection.close()
