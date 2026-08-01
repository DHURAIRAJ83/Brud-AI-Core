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
    _apply_v27,
    _apply_v28,
    _apply_v29,
    current_schema_version,
    initialize_database,
    upgrade_database,
)
from backend.database.schema import SCHEMA_VERSION

PHASE30_TABLES = {
    "external_data_providers",
    "external_data_provider_domains",
    "external_data_provider_capabilities",
    "external_data_provider_credentials",
    "external_data_provider_connection_tests",
    "external_data_provider_events",
}

APPLY_THROUGH_V29 = (
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
    _apply_v27,
    _apply_v28,
    _apply_v29,
)

ADMIN_ID = "00000000-0000-0000-0000-000000000001"


def _existing_tables(connection) -> set[str]:
    return {
        row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }


def _insert_provider(connection, public_id: str, provider_code: str) -> int:
    connection.execute(
        """INSERT INTO external_data_providers(public_id, provider_code, name, provider_type,
        access_mode, created_by_admin_public_id) VALUES (?,?,?,?,?,?)""",
        (public_id, provider_code, "Test Provider", "public_api", "public", ADMIN_ID),
    )
    return connection.execute(
        "SELECT id FROM external_data_providers WHERE public_id=?", (public_id,)
    ).fetchone()[0]


def test_fresh_database_reaches_schema_30(tmp_path: Path) -> None:
    database = tmp_path / "fresh.db"
    initialize_database(database)
    assert current_schema_version(database) == SCHEMA_VERSION
    assert SCHEMA_VERSION >= 30
    with database_connection(database) as connection:
        assert PHASE30_TABLES <= _existing_tables(connection)
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert not list(connection.execute("PRAGMA foreign_key_check"))
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_schema_29_upgrades_to_30_and_preserves_existing_data(tmp_path: Path) -> None:
    database = tmp_path / "v29.db"
    with database_connection(database) as connection:
        for apply in APPLY_THROUGH_V29:
            apply(connection)
        connection.execute(
            """INSERT INTO admin_approvals(public_id,action_type,target_type,
            target_public_id,request_payload_json,requested_by) VALUES (?,?,?,?,?,?)""",
            ("00000000-0000-0000-0000-000000000a30", "dataset_record_review", "dataset_record",
             "rec-1", "{}", ADMIN_ID),
        )
        connection.commit()
    assert current_schema_version(database) == 29

    settings = Settings(
        database_path=database,
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
    )
    version, _backup, integrity = upgrade_database(settings)
    assert version == SCHEMA_VERSION
    assert SCHEMA_VERSION >= 30
    assert integrity == "ok"

    with database_connection(database) as connection:
        assert PHASE30_TABLES <= _existing_tables(connection)
        assert not list(connection.execute("PRAGMA foreign_key_check"))
        preserved = connection.execute(
            "SELECT action_type FROM admin_approvals WHERE public_id=?",
            ("00000000-0000-0000-0000-000000000a30",),
        ).fetchone()
        assert preserved["action_type"] == "dataset_record_review"

        provider_id = _insert_provider(connection, "prov-post-upgrade", "post-upgrade-code")
        connection.commit()
        row = connection.execute(
            "SELECT provider_code, lifecycle_status, trust_status, enabled FROM "
            "external_data_providers WHERE id=?",
            (provider_id,),
        ).fetchone()
        assert row["provider_code"] == "post-upgrade-code"
        assert row["lifecycle_status"] == "draft"
        assert row["trust_status"] == "unverified"
        assert row["enabled"] == 0


def test_provider_code_is_unique(tmp_path: Path) -> None:
    database = tmp_path / "unique.db"
    initialize_database(database)
    with database_connection(database) as connection:
        _insert_provider(connection, "prov-1", "dup-code")
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO external_data_providers(public_id, provider_code, name,
                provider_type, access_mode, created_by_admin_public_id)
                VALUES (?,?,?,?,?,?)""",
                ("prov-2", "dup-code", "Another", "public_api", "public", ADMIN_ID),
            )


def test_provider_rejects_unknown_provider_type_and_access_mode(tmp_path: Path) -> None:
    database = tmp_path / "checks.db"
    initialize_database(database)
    with database_connection(database) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO external_data_providers(public_id, provider_code, name,
                provider_type, access_mode, created_by_admin_public_id)
                VALUES (?,?,?,?,?,?)""",
                ("prov-bad", "bad-type", "Bad", "not_a_real_type", "public", ADMIN_ID),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO external_data_providers(public_id, provider_code, name,
                provider_type, access_mode, created_by_admin_public_id)
                VALUES (?,?,?,?,?,?)""",
                ("prov-bad2", "bad-access", "Bad", "public_api", "not_a_real_mode", ADMIN_ID),
            )


def test_providers_default_to_draft_unverified_disabled(tmp_path: Path) -> None:
    database = tmp_path / "defaults.db"
    initialize_database(database)
    with database_connection(database) as connection:
        provider_id = _insert_provider(connection, "prov-defaults", "defaults-code")
        connection.commit()
        row = connection.execute(
            "SELECT lifecycle_status, trust_status, enabled, authentication_type FROM "
            "external_data_providers WHERE id=?",
            (provider_id,),
        ).fetchone()
        assert row["lifecycle_status"] == "draft"
        assert row["trust_status"] == "unverified"
        assert row["enabled"] == 0
        assert row["authentication_type"] == "none"


def test_providers_are_never_hard_deleted(tmp_path: Path) -> None:
    database = tmp_path / "no_delete.db"
    initialize_database(database)
    with database_connection(database) as connection:
        _insert_provider(connection, "prov-persist", "persist-code")
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "DELETE FROM external_data_providers WHERE public_id=?", ("prov-persist",)
            )


def test_domain_capability_credential_tables_and_uniqueness(tmp_path: Path) -> None:
    database = tmp_path / "children.db"
    initialize_database(database)
    with database_connection(database) as connection:
        provider_id = _insert_provider(connection, "prov-children", "children-code")
        connection.execute(
            """INSERT INTO external_data_provider_domains(public_id, provider_id, domain,
            domain_type) VALUES (?,?,?,?)""",
            ("dom-1", provider_id, "example.org", "official"),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO external_data_provider_domains(public_id, provider_id, domain,
                domain_type) VALUES (?,?,?,?)""",
                ("dom-2", provider_id, "example.org", "official"),
            )

        connection.execute(
            """INSERT INTO external_data_provider_capabilities(public_id, provider_id,
            capability_type) VALUES (?,?,?)""",
            ("cap-1", provider_id, "read_metadata"),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO external_data_provider_capabilities(public_id, provider_id,
                capability_type) VALUES (?,?,?)""",
                ("cap-2", provider_id, "read_metadata"),
            )

        connection.execute(
            """INSERT INTO external_data_provider_credentials(public_id, provider_id,
            credential_type, reference_key, created_by_admin_public_id)
            VALUES (?,?,?,?,?)""",
            ("cred-1", provider_id, "api_key", "BRUD_PROVIDER_SECRET__test", ADMIN_ID),
        )
        connection.commit()
        row = connection.execute(
            "SELECT status FROM external_data_provider_credentials WHERE public_id=?", ("cred-1",)
        ).fetchone()
        assert row["status"] == "not_configured"
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "DELETE FROM external_data_provider_credentials WHERE public_id=?", ("cred-1",)
            )


def test_connection_tests_and_events_are_append_only(tmp_path: Path) -> None:
    database = tmp_path / "append_only.db"
    initialize_database(database)
    with database_connection(database) as connection:
        provider_id = _insert_provider(connection, "prov-log", "log-code")
        connection.execute(
            """INSERT INTO external_data_provider_connection_tests(public_id, provider_id,
            result, tested_by_admin_public_id) VALUES (?,?,?,?)""",
            ("test-1", provider_id, "success", ADMIN_ID),
        )
        connection.execute(
            """INSERT INTO external_data_provider_events(public_id, provider_id, event_type,
            performed_by_admin_public_id) VALUES (?,?,?,?)""",
            ("event-1", provider_id, "provider_registered", ADMIN_ID),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE external_data_provider_connection_tests SET result='failed' "
                "WHERE public_id=?",
                ("test-1",),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "DELETE FROM external_data_provider_connection_tests WHERE public_id=?",
                ("test-1",),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE external_data_provider_events SET summary='changed' WHERE public_id=?",
                ("event-1",),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "DELETE FROM external_data_provider_events WHERE public_id=?", ("event-1",)
            )


def test_child_rows_cascade_delete_is_blocked_via_provider_trigger(tmp_path: Path) -> None:
    """Providers can never be hard-deleted (see test above), so the
    ON DELETE CASCADE on child tables is unreachable in practice --
    this test just confirms the foreign keys are well-formed (no
    dangling-reference risk) rather than relying on cascade behavior."""
    database = tmp_path / "fk.db"
    initialize_database(database)
    with database_connection(database) as connection:
        provider_id = _insert_provider(connection, "prov-fk", "fk-code")
        connection.execute(
            """INSERT INTO external_data_provider_domains(public_id, provider_id, domain,
            domain_type) VALUES (?,?,?,?)""",
            ("dom-fk", provider_id, "example.org", "official"),
        )
        connection.commit()
        assert not list(connection.execute("PRAGMA foreign_key_check"))
