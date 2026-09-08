import sqlite3
from pathlib import Path

import pytest

from backend.database.migrations import initialize_database
from backend.database.schema import SCHEMA_VERSION


def test_fresh_database_reaches_schema_version_40(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.db"
    version = initialize_database(db_path)
    assert version == SCHEMA_VERSION
    assert SCHEMA_VERSION >= 40


def test_public_chat_routing_events_table_exists_with_expected_columns(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "fresh.db"
    initialize_database(db_path)
    connection = sqlite3.connect(db_path)
    try:
        columns = {row[1] for row in connection.execute(
            "PRAGMA table_info(public_chat_routing_events)"
        )}
        expected = {
            "public_id", "request_id", "input_hash", "classification_decision_public_id",
            "recommended_route", "resolved_route", "route_status", "evidence_status",
            "detected_language", "answer_language", "safety_status",
            "fallbacks_attempted_json", "latency_ms", "error_code", "conversation_id",
            "created_at",
        }
        assert expected.issubset(columns)
        assert "message" not in columns
        assert "reply" not in columns
        assert "raw_text" not in columns
    finally:
        connection.close()


def test_public_chat_feedback_events_table_exists_with_expected_columns(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "fresh.db"
    initialize_database(db_path)
    connection = sqlite3.connect(db_path)
    try:
        columns = {row[1] for row in connection.execute(
            "PRAGMA table_info(public_chat_feedback_events)"
        )}
        expected = {
            "public_id", "request_id", "route_used", "answer_hash", "feedback_type",
            "comment", "created_at",
        }
        assert expected.issubset(columns)
        assert "answer_text" not in columns
    finally:
        connection.close()


def test_no_foreign_key_violations_after_migration(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.db"
    initialize_database(db_path)
    connection = sqlite3.connect(db_path)
    try:
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        assert violations == []
    finally:
        connection.close()


def test_migration_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.db"
    initialize_database(db_path)
    version_again = initialize_database(db_path)
    assert version_again == SCHEMA_VERSION


def test_public_chat_routing_events_is_append_only(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.db"
    initialize_database(db_path)
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            """INSERT INTO public_chat_routing_events(
                public_id, request_id, input_hash, recommended_route, resolved_route,
                route_status, evidence_status, detected_language, safety_status
            ) VALUES ('p1', 'r1', 'h1', 'core_model', 'core_model',
                'executable', 'model_only', 'en', 'safe')"""
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE public_chat_routing_events SET resolved_route = 'refuse' "
                "WHERE public_id = 'p1'"
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "DELETE FROM public_chat_routing_events WHERE public_id = 'p1'"
            )
    finally:
        connection.close()


def test_public_chat_routing_events_rejects_invalid_route(tmp_path: Path) -> None:
    # `trusted_web` was mistakenly used here as an "invalid" value before
    # migration 071 (see test_phase71_public_chat_routing_events_resolved_
    # route_fix.py) -- it is a legitimate, application-assigned resolved_route
    # value and must NOT be rejected. Use a genuinely invalid value instead.
    db_path = tmp_path / "fresh.db"
    initialize_database(db_path)
    connection = sqlite3.connect(db_path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO public_chat_routing_events(
                    public_id, request_id, input_hash, recommended_route, resolved_route,
                    route_status, evidence_status, detected_language, safety_status
                ) VALUES ('p2', 'r2', 'h2', 'core_model', 'invalid_test_route',
                    'executable', 'model_only', 'en', 'safe')"""
            )
    finally:
        connection.close()
