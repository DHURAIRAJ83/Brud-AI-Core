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
    current_schema_version,
    initialize_database,
    upgrade_database,
)
from backend.database.schema import SCHEMA_VERSION

PHASE28_TABLES = {
    "governed_build_requests",
    "governed_build_preflight_results",
    "governed_build_request_items",
    "pipeline_artifact_links",
    "lineage_edges",
    "lineage_events",
}

APPLY_THROUGH_V27 = (
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


def _insert_build_request(connection, public_id: str) -> int:
    connection.execute(
        """INSERT INTO governed_build_requests(public_id, build_code, target_pipeline,
        requested_by_admin_public_id) VALUES (?,?,?,?)""",
        (public_id, public_id.upper(), "dataset_version", "admin-1"),
    )
    return connection.execute(
        "SELECT id FROM governed_build_requests WHERE public_id=?", (public_id,)
    ).fetchone()[0]


def test_fresh_database_reaches_schema_28(tmp_path: Path) -> None:
    database = tmp_path / "fresh.db"
    initialize_database(database)
    assert current_schema_version(database) == SCHEMA_VERSION
    assert SCHEMA_VERSION >= 28
    with database_connection(database) as connection:
        assert PHASE28_TABLES <= _existing_tables(connection)
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert not list(connection.execute("PRAGMA foreign_key_check"))
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_schema_27_upgrades_to_28_and_preserves_existing_data(tmp_path: Path) -> None:
    database = tmp_path / "v27.db"
    with database_connection(database) as connection:
        for apply in APPLY_THROUGH_V27:
            apply(connection)
        _insert_document(connection, "00000000-0000-0000-0000-000000000d28")
        connection.commit()
    assert current_schema_version(database) == 27

    settings = Settings(
        database_path=database,
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
    )
    version, _backup, integrity = upgrade_database(settings)
    assert version == SCHEMA_VERSION
    assert SCHEMA_VERSION >= 28
    assert integrity == "ok"

    with database_connection(database) as connection:
        assert PHASE28_TABLES <= _existing_tables(connection)
        assert not list(connection.execute("PRAGMA foreign_key_check"))
        row = connection.execute(
            "SELECT original_filename FROM document_sources WHERE public_id=?",
            ("00000000-0000-0000-0000-000000000d28",),
        ).fetchone()
        assert row["original_filename"] == "a.pdf"


def test_governed_build_requests_requires_valid_target_pipeline_and_status(
    tmp_path: Path,
) -> None:
    database = tmp_path / "check.db"
    initialize_database(database)
    with database_connection(database) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO governed_build_requests(public_id, build_code, target_pipeline,
                requested_by_admin_public_id) VALUES (?,?,?,?)""",
                ("gbr-bad", "GBR-BAD", "not_a_real_pipeline", "admin-1"),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO governed_build_requests(public_id, build_code, target_pipeline,
                status, requested_by_admin_public_id) VALUES (?,?,?,?,?)""",
                ("gbr-bad2", "GBR-BAD2", "rag", "not_a_status", "admin-1"),
            )
        connection.execute(
            """INSERT INTO governed_build_requests(public_id, build_code, target_pipeline,
            requested_by_admin_public_id) VALUES (?,?,?,?)""",
            ("gbr-1", "GBR-1", "rag", "admin-1"),
        )
        connection.commit()
        row = connection.execute(
            "SELECT status FROM governed_build_requests WHERE public_id=?", ("gbr-1",)
        ).fetchone()
        assert row["status"] == "draft"


def test_governed_build_preflight_results_are_append_only(tmp_path: Path) -> None:
    database = tmp_path / "preflight_append.db"
    initialize_database(database)
    with database_connection(database) as connection:
        request_id = _insert_build_request(connection, "gbr-2")
        connection.execute(
            """INSERT INTO governed_build_preflight_results(public_id, build_request_id,
            target_pipeline, eligible_count, created_by_admin_public_id)
            VALUES (?,?,?,?,?)""",
            ("pf-1", request_id, "dataset_version", 5, "admin-1"),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE governed_build_preflight_results SET eligible_count=99 WHERE public_id=?",
                ("pf-1",),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "DELETE FROM governed_build_preflight_results WHERE public_id=?", ("pf-1",)
            )


def test_governed_build_request_items_require_valid_decision_and_link_to_preflight(
    tmp_path: Path,
) -> None:
    database = tmp_path / "items.db"
    initialize_database(database)
    with database_connection(database) as connection:
        request_id = _insert_build_request(connection, "gbr-3")
        connection.execute(
            """INSERT INTO governed_build_preflight_results(public_id, build_request_id,
            target_pipeline, created_by_admin_public_id) VALUES (?,?,?,?)""",
            ("pf-2", request_id, "dataset_version", "admin-1"),
        )
        preflight_id = connection.execute(
            "SELECT id FROM governed_build_preflight_results WHERE public_id=?", ("pf-2",)
        ).fetchone()[0]
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO governed_build_request_items(public_id, build_request_id,
                preflight_result_id, entity_type, entity_public_id, decision, decision_code)
                VALUES (?,?,?,?,?,?,?)""",
                ("item-bad", request_id, preflight_id, "dataset_record", "rec-1",
                 "not_a_decision", "X"),
            )
        connection.execute(
            """INSERT INTO governed_build_request_items(public_id, build_request_id,
            preflight_result_id, entity_type, entity_public_id, decision, decision_code, included)
            VALUES (?,?,?,?,?,?,?,?)""",
            ("item-1", request_id, preflight_id, "dataset_record", "rec-1",
             "eligible", "ELIGIBLE", 1),
        )
        connection.commit()
        row = connection.execute(
            "SELECT included FROM governed_build_request_items WHERE public_id=?", ("item-1",)
        ).fetchone()
        assert row["included"] == 1
        # Items are a mutable working-selection surface (Step 7's "allow
        # admin to revise selection") -- unlike the preflight result itself.
        connection.execute(
            "UPDATE governed_build_request_items SET included=0 WHERE public_id=?", ("item-1",)
        )
        connection.commit()


def test_pipeline_artifact_links_require_valid_type_and_prevent_duplicate_links(
    tmp_path: Path,
) -> None:
    database = tmp_path / "links.db"
    initialize_database(database)
    with database_connection(database) as connection:
        request_id = _insert_build_request(connection, "gbr-4")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO pipeline_artifact_links(public_id, build_request_id,
                artifact_type, artifact_public_id, created_by_admin_public_id)
                VALUES (?,?,?,?,?)""",
                ("link-bad", request_id, "not_a_real_artifact", "art-1", "admin-1"),
            )
        connection.execute(
            """INSERT INTO pipeline_artifact_links(public_id, build_request_id,
            artifact_type, artifact_public_id, created_by_admin_public_id)
            VALUES (?,?,?,?,?)""",
            ("link-1", request_id, "dataset_version", "ver-1", "admin-1"),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO pipeline_artifact_links(public_id, build_request_id,
                artifact_type, artifact_public_id, created_by_admin_public_id)
                VALUES (?,?,?,?,?)""",
                ("link-2", request_id, "dataset_version", "ver-1", "admin-1"),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE pipeline_artifact_links SET artifact_public_id='ver-2' WHERE public_id=?",
                ("link-1",),
            )


def test_lineage_edges_require_valid_relationship_and_prevent_duplicate_edges(
    tmp_path: Path,
) -> None:
    database = tmp_path / "lineage.db"
    initialize_database(database)
    with database_connection(database) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO lineage_edges(public_id, upstream_entity_type, upstream_entity_id,
                downstream_entity_type, downstream_entity_id, relationship_type,
                created_by_admin_public_id) VALUES (?,?,?,?,?,?,?)""",
                ("edge-bad", "manual_data_record", "rec-1", "dataset_record", "ds-1",
                 "not_a_real_relationship", "admin-1"),
            )
        connection.execute(
            """INSERT INTO lineage_edges(public_id, upstream_entity_type, upstream_entity_id,
            downstream_entity_type, downstream_entity_id, relationship_type,
            created_by_admin_public_id) VALUES (?,?,?,?,?,?,?)""",
            ("edge-1", "manual_data_record", "rec-1", "dataset_record", "ds-1",
             "derived_from", "admin-1"),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO lineage_edges(public_id, upstream_entity_type, upstream_entity_id,
                downstream_entity_type, downstream_entity_id, relationship_type,
                created_by_admin_public_id) VALUES (?,?,?,?,?,?,?)""",
                ("edge-2", "manual_data_record", "rec-1", "dataset_record", "ds-1",
                 "derived_from", "admin-1"),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE lineage_edges SET metadata_json='{}' WHERE public_id=?", ("edge-1",)
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("DELETE FROM lineage_edges WHERE public_id=?", ("edge-1",))


def test_lineage_events_are_append_only(tmp_path: Path) -> None:
    database = tmp_path / "lineage_events.db"
    initialize_database(database)
    with database_connection(database) as connection:
        request_id = _insert_build_request(connection, "gbr-5")
        connection.execute(
            """INSERT INTO lineage_events(public_id, build_request_id, event_type,
            performed_by_admin_public_id) VALUES (?,?,?,?)""",
            ("levt-1", request_id, "build_request_created", "admin-1"),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE lineage_events SET notes='changed' WHERE public_id=?", ("levt-1",)
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("DELETE FROM lineage_events WHERE public_id=?", ("levt-1",))
