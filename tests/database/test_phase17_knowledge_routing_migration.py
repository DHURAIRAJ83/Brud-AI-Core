import sqlite3
from pathlib import Path

import pytest

from backend.database.migrations import initialize_database
from backend.database.schema import SCHEMA_VERSION


def test_fresh_database_reaches_schema_version_39(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.db"
    version = initialize_database(db_path)
    assert version == SCHEMA_VERSION
    assert SCHEMA_VERSION >= 39


def test_routing_classification_decisions_table_exists_with_expected_columns(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "fresh.db"
    initialize_database(db_path)
    connection = sqlite3.connect(db_path)
    try:
        columns = {row[1] for row in connection.execute(
            "PRAGMA table_info(routing_classification_decisions)"
        )}
        expected = {
            "public_id", "input_hash", "context_type", "language_category", "intent", "domain",
            "subdomain", "freshness", "ambiguity", "safety_risk", "evidence_requirement",
            "execution_route", "learning_target", "requires_human_review", "input_truncated",
            "reason_codes_json", "policy_version", "taxonomy_version",
            "created_by_admin_public_id", "created_at",
        }
        assert expected.issubset(columns)
        assert "raw_text" not in columns
        assert "question" not in columns
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


def test_routing_classification_decisions_is_append_only(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.db"
    initialize_database(db_path)
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            """INSERT INTO routing_classification_decisions(
                public_id, input_hash, context_type, language_category, intent, domain,
                freshness, ambiguity, safety_risk, evidence_requirement, execution_route,
                learning_target, policy_version, taxonomy_version
            ) VALUES ('p1', 'h1', 'public_chat_question', 'en', 'ask_fact', 'general_knowledge',
                'timeless', 'not_ambiguous', 'safe', 'model_knowledge_ok', 'core_model',
                'core_model', 'v1', 'v1')"""
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE routing_classification_decisions SET domain = 'x' WHERE public_id = 'p1'"
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "DELETE FROM routing_classification_decisions WHERE public_id = 'p1'"
            )
    finally:
        connection.close()
