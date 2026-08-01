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
    _apply_v30,
    _apply_v31,
    _apply_v32,
    _apply_v33,
    _apply_v34,
    _apply_v35,
    current_schema_version,
    initialize_database,
    upgrade_database,
)
from backend.database.schema import SCHEMA_VERSION

PHASE36_TABLES = {
    "rag_sandbox_experiments",
    "rag_sandbox_query_sets",
    "rag_sandbox_queries",
    "rag_sandbox_approvals",
    "rag_sandbox_corpora",
    "rag_sandbox_records",
    "rag_sandbox_indexes",
    "rag_sandbox_retrieval_runs",
    "rag_sandbox_retrieval_results",
    "rag_sandbox_answer_runs",
    "rag_sandbox_citations",
    "rag_sandbox_evaluations",
    "rag_sandbox_human_reviews",
    "rag_sandbox_reports",
    "rag_sandbox_acceptances",
    "rag_sandbox_events",
    "rag_sandbox_deletion_requests",
}

APPLY_THROUGH_V35 = (
    _apply_v1, _apply_v2, _apply_v3, _apply_v4, _apply_v5, _apply_v6, _apply_v7, _apply_v8,
    _apply_v9, _apply_v10, _apply_v11, _apply_v12, _apply_v13, _apply_v14, _apply_v15,
    _apply_v16, _apply_v17, _apply_v18, _apply_v19, _apply_v20, _apply_v21, _apply_v22,
    _apply_v23, _apply_v24, _apply_v25, _apply_v26, _apply_v27, _apply_v28, _apply_v29,
    _apply_v30, _apply_v31, _apply_v32, _apply_v33, _apply_v34, _apply_v35,
)

ADMIN_ID = "00000000-0000-0000-0000-000000000001"


def _existing_tables(connection) -> set[str]:
    return {
        row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }


def _setup_case(connection) -> tuple[int, int, int]:
    connection.execute(
        """INSERT INTO external_dataset_search_sessions(public_id, session_code,
        requested_by_admin_public_id) VALUES (?,?,?)""",
        ("sess-1", "session-1", ADMIN_ID),
    )
    session_id = connection.execute(
        "SELECT id FROM external_dataset_search_sessions WHERE public_id=?", ("sess-1",)
    ).fetchone()[0]
    connection.execute(
        """INSERT INTO external_dataset_candidates(public_id, search_session_id,
        canonical_name, normalized_name) VALUES (?,?,?,?)""",
        ("cand-1", session_id, "Tamil Corpus", "tamil corpus"),
    )
    candidate_id = connection.execute(
        "SELECT id FROM external_dataset_candidates WHERE public_id=?", ("cand-1",)
    ).fetchone()[0]
    connection.execute(
        """INSERT INTO external_dataset_verification_cases(public_id, verification_code,
        candidate_id, search_session_id, requested_by_admin_public_id, locked_at)
        VALUES (?,?,?,?,?,CURRENT_TIMESTAMP)""",
        ("case-1", "VC-1", candidate_id, session_id, ADMIN_ID),
    )
    case_id = connection.execute(
        "SELECT id FROM external_dataset_verification_cases WHERE public_id=?", ("case-1",)
    ).fetchone()[0]
    return session_id, candidate_id, case_id


def _insert_sample_import(connection, case_id, candidate_id, public_id="sample-1") -> int:
    connection.execute(
        """INSERT INTO external_dataset_sample_imports(public_id, sample_import_code,
        verification_case_id, candidate_id, purpose, selection_method,
        requested_by_admin_public_id) VALUES (?,?,?,?,?,?,?)""",
        (public_id, f"SI-{public_id}", case_id, candidate_id, "rag_sandbox_preparation",
         "deterministic_first_n", ADMIN_ID),
    )
    return connection.execute(
        "SELECT id FROM external_dataset_sample_imports WHERE public_id=?", (public_id,)
    ).fetchone()[0]


def _insert_file(connection, sample_import_id, public_id="file-1") -> int:
    connection.execute(
        """INSERT INTO external_dataset_sample_files(public_id, sample_import_id,
        original_filename, safe_filename, relative_path) VALUES (?,?,?,?,?)""",
        (public_id, sample_import_id, "data.txt", "data.txt", "original/data.txt"),
    )
    return connection.execute(
        "SELECT id FROM external_dataset_sample_files WHERE public_id=?", (public_id,)
    ).fetchone()[0]


def _insert_record(connection, sample_import_id, file_id, public_id="record-1") -> int:
    connection.execute(
        """INSERT INTO external_dataset_sample_records(public_id, sample_import_id,
        source_file_id, raw_content, normalized_content, source_checksum, record_checksum,
        status) VALUES (?,?,?,?,?,?,?,?)""",
        (public_id, sample_import_id, file_id, "hello", "hello", "chk-src", "chk-rec",
         "accepted"),
    )
    return connection.execute(
        "SELECT id FROM external_dataset_sample_records WHERE public_id=?", (public_id,)
    ).fetchone()[0]


def _insert_report(connection, sample_import_id, public_id="report-1") -> int:
    connection.execute(
        """INSERT INTO external_dataset_sample_reports(public_id, sample_import_id,
        rag_sandbox_eligible, training_assessment_status, finalized_by_admin_public_id)
        VALUES (?,?,?,?,?)""",
        (public_id, sample_import_id, 1, "not_assessed", ADMIN_ID),
    )
    return connection.execute(
        "SELECT id FROM external_dataset_sample_reports WHERE public_id=?", (public_id,)
    ).fetchone()[0]


def _insert_experiment(
    connection, sample_import_id, report_id, case_id, public_id="exp-1"
) -> int:
    connection.execute(
        """INSERT INTO rag_sandbox_experiments(public_id, experiment_code, sample_import_id,
        sample_report_id, verification_case_id, purpose, created_by_admin_public_id)
        VALUES (?,?,?,?,?,?,?)""",
        (public_id, f"EXP-{public_id}", sample_import_id, report_id, case_id,
         "retrieval_validation", ADMIN_ID),
    )
    return connection.execute(
        "SELECT id FROM rag_sandbox_experiments WHERE public_id=?", (public_id,)
    ).fetchone()[0]


def _insert_query_set(connection, experiment_id, public_id="qs-1") -> int:
    connection.execute(
        """INSERT INTO rag_sandbox_query_sets(public_id, experiment_id, name,
        created_by_admin_public_id) VALUES (?,?,?,?)""",
        (public_id, experiment_id, "Baseline queries", ADMIN_ID),
    )
    return connection.execute(
        "SELECT id FROM rag_sandbox_query_sets WHERE public_id=?", (public_id,)
    ).fetchone()[0]


def _insert_query(connection, query_set_id, public_id="q-1", query_type="fact_lookup") -> int:
    connection.execute(
        """INSERT INTO rag_sandbox_queries(public_id, query_set_id, query_text, query_type,
        created_by) VALUES (?,?,?,?,?)""",
        (public_id, query_set_id, "What is the capital?", query_type, ADMIN_ID),
    )
    return connection.execute(
        "SELECT id FROM rag_sandbox_queries WHERE public_id=?", (public_id,)
    ).fetchone()[0]


def _insert_knowledge_space(connection, public_id="space-1") -> int:
    connection.execute(
        """INSERT INTO rag_knowledge_spaces(public_id, name, slug, created_by_admin_public_id)
        VALUES (?,?,?,?)""",
        (public_id, "Sandbox Space", f"sandbox-{public_id}", ADMIN_ID),
    )
    return connection.execute(
        "SELECT id FROM rag_knowledge_spaces WHERE public_id=?", (public_id,)
    ).fetchone()[0]


def _insert_corpus(connection, experiment_id, space_id, public_id="corpus-1") -> int:
    connection.execute(
        """INSERT INTO rag_sandbox_corpora(public_id, experiment_id, knowledge_space_id,
        sandbox_scope_key, created_by_admin_public_id) VALUES (?,?,?,?,?)""",
        (public_id, experiment_id, space_id, f"scope-{public_id}", ADMIN_ID),
    )
    return connection.execute(
        "SELECT id FROM rag_sandbox_corpora WHERE public_id=?", (public_id,)
    ).fetchone()[0]


def _full_chain(connection):
    """Builds one experiment through corpus/query-set/query, returns a dict of ids."""

    _session_id, candidate_id, case_id = _setup_case(connection)
    sample_import_id = _insert_sample_import(connection, case_id, candidate_id)
    file_id = _insert_file(connection, sample_import_id)
    record_id = _insert_record(connection, sample_import_id, file_id)
    report_id = _insert_report(connection, sample_import_id)
    experiment_id = _insert_experiment(connection, sample_import_id, report_id, case_id)
    query_set_id = _insert_query_set(connection, experiment_id)
    query_id = _insert_query(connection, query_set_id)
    space_id = _insert_knowledge_space(connection)
    corpus_id = _insert_corpus(connection, experiment_id, space_id)
    return {
        "case_id": case_id,
        "sample_import_id": sample_import_id,
        "file_id": file_id,
        "record_id": record_id,
        "report_id": report_id,
        "experiment_id": experiment_id,
        "query_set_id": query_set_id,
        "query_id": query_id,
        "space_id": space_id,
        "corpus_id": corpus_id,
    }


def test_fresh_database_reaches_schema_36(tmp_path: Path) -> None:
    database = tmp_path / "fresh.db"
    initialize_database(database)
    assert current_schema_version(database) == SCHEMA_VERSION
    assert SCHEMA_VERSION >= 36
    with database_connection(database) as connection:
        assert PHASE36_TABLES <= _existing_tables(connection)
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert not list(connection.execute("PRAGMA foreign_key_check"))
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_schema_35_upgrades_to_36_and_preserves_existing_data(tmp_path: Path) -> None:
    database = tmp_path / "v35.db"
    with database_connection(database) as connection:
        for apply in APPLY_THROUGH_V35:
            apply(connection)
        connection.execute(
            """INSERT INTO external_dataset_search_sessions(public_id, session_code,
            requested_by_admin_public_id) VALUES (?,?,?)""",
            ("sess-preexisting", "preexisting-code", ADMIN_ID),
        )
        connection.commit()
    assert current_schema_version(database) == 35

    settings = Settings(
        database_path=database,
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
    )
    version, _backup, integrity = upgrade_database(settings)
    assert version == SCHEMA_VERSION
    assert SCHEMA_VERSION >= 36
    assert integrity == "ok"

    with database_connection(database) as connection:
        assert PHASE36_TABLES <= _existing_tables(connection)
        assert not list(connection.execute("PRAGMA foreign_key_check"))
        preserved = connection.execute(
            "SELECT session_code FROM external_dataset_search_sessions WHERE public_id=?",
            ("sess-preexisting",),
        ).fetchone()
        assert preserved["session_code"] == "preexisting-code"

        ids = _full_chain(connection)
        connection.commit()
        row = connection.execute(
            "SELECT status, current_stage FROM rag_sandbox_experiments WHERE id=?",
            (ids["experiment_id"],),
        ).fetchone()
        assert row["status"] == "draft"
        assert row["current_stage"] == "eligibility"


def test_experiment_code_is_unique(tmp_path: Path) -> None:
    database = tmp_path / "unique.db"
    initialize_database(database)
    with database_connection(database) as connection:
        ids = _full_chain(connection)
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO rag_sandbox_experiments(public_id, experiment_code,
                sample_import_id, sample_report_id, verification_case_id, purpose,
                created_by_admin_public_id) VALUES (?,?,?,?,?,?,?)""",
                ("exp-2", "EXP-exp-1", ids["sample_import_id"], ids["report_id"],
                 ids["case_id"], "retrieval_validation", ADMIN_ID),
            )


def test_experiment_rejects_unknown_status(tmp_path: Path) -> None:
    database = tmp_path / "status.db"
    initialize_database(database)
    with database_connection(database) as connection:
        ids = _full_chain(connection)
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO rag_sandbox_experiments(public_id, experiment_code,
                sample_import_id, sample_report_id, verification_case_id, purpose,
                created_by_admin_public_id, status) VALUES (?,?,?,?,?,?,?,?)""",
                ("exp-bad", "EXP-bad", ids["sample_import_id"], ids["report_id"],
                 ids["case_id"], "retrieval_validation", ADMIN_ID, "not_a_real_status"),
            )


def test_experiment_rejects_unknown_purpose(tmp_path: Path) -> None:
    database = tmp_path / "purpose.db"
    initialize_database(database)
    with database_connection(database) as connection:
        ids = _full_chain(connection)
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO rag_sandbox_experiments(public_id, experiment_code,
                sample_import_id, sample_report_id, verification_case_id, purpose,
                created_by_admin_public_id) VALUES (?,?,?,?,?,?,?)""",
                ("exp-bad-purpose", "EXP-bad-purpose", ids["sample_import_id"], ids["report_id"],
                 ids["case_id"], "training", ADMIN_ID),
            )


def test_corpora_rejects_production_visible_true(tmp_path: Path) -> None:
    database = tmp_path / "prodvis.db"
    initialize_database(database)
    with database_connection(database) as connection:
        ids = _full_chain(connection)
        space2_id = _insert_knowledge_space(connection, public_id="space-2")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO rag_sandbox_corpora(public_id, experiment_id,
                knowledge_space_id, sandbox_scope_key, production_visible,
                created_by_admin_public_id) VALUES (?,?,?,?,?,?)""",
                ("corpus-bad", ids["experiment_id"], space2_id, "scope-bad", 1, ADMIN_ID),
            )


def test_corpora_is_one_per_experiment(tmp_path: Path) -> None:
    database = tmp_path / "one_corpus.db"
    initialize_database(database)
    with database_connection(database) as connection:
        ids = _full_chain(connection)
        space2_id = _insert_knowledge_space(connection, public_id="space-2")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO rag_sandbox_corpora(public_id, experiment_id,
                knowledge_space_id, sandbox_scope_key, created_by_admin_public_id)
                VALUES (?,?,?,?,?)""",
                ("corpus-2", ids["experiment_id"], space2_id, "scope-2", ADMIN_ID),
            )


def _insert_approval(connection, ids, public_id="approval-1", status="pending") -> int:
    connection.execute(
        """INSERT INTO rag_sandbox_approvals(public_id, experiment_id, sample_import_id,
        sample_report_id, verification_case_id, purpose, maximum_records,
        maximum_total_characters, maximum_total_tokens, target_fingerprint, status,
        query_set_id, requested_by_admin_public_id)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (public_id, ids["experiment_id"], ids["sample_import_id"], ids["report_id"],
         ids["case_id"], "retrieval_validation", 100, 500_000, 100_000, "fp-1", status,
         ids["query_set_id"], ADMIN_ID),
    )
    return connection.execute(
        "SELECT id FROM rag_sandbox_approvals WHERE public_id=?", (public_id,)
    ).fetchone()[0]


def test_approval_rejects_nonpositive_limits(tmp_path: Path) -> None:
    database = tmp_path / "limits.db"
    initialize_database(database)
    with database_connection(database) as connection:
        ids = _full_chain(connection)
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO rag_sandbox_approvals(public_id, experiment_id,
                sample_import_id, sample_report_id, verification_case_id, purpose,
                maximum_records, maximum_total_characters, maximum_total_tokens,
                target_fingerprint, requested_by_admin_public_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                ("approval-bad", ids["experiment_id"], ids["sample_import_id"],
                 ids["report_id"], ids["case_id"], "retrieval_validation", 0, 500_000,
                 100_000, "fp", ADMIN_ID),
            )


def test_approval_is_immutable_once_approved(tmp_path: Path) -> None:
    database = tmp_path / "approval_immutable.db"
    initialize_database(database)
    with database_connection(database) as connection:
        ids = _full_chain(connection)
        approval_id = _insert_approval(connection, ids)
        connection.execute(
            "UPDATE rag_sandbox_approvals SET status='approved' WHERE id=?", (approval_id,)
        )
        connection.commit()

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE rag_sandbox_approvals SET maximum_records=999 WHERE id=?",
                (approval_id,),
            )


def test_approval_can_transition_from_approved_to_expired(tmp_path: Path) -> None:
    database = tmp_path / "approval_expire.db"
    initialize_database(database)
    with database_connection(database) as connection:
        ids = _full_chain(connection)
        approval_id = _insert_approval(connection, ids)
        connection.execute(
            "UPDATE rag_sandbox_approvals SET status='approved' WHERE id=?", (approval_id,)
        )
        connection.execute(
            "UPDATE rag_sandbox_approvals SET status='expired' WHERE id=?", (approval_id,)
        )
        connection.commit()
        row = connection.execute(
            "SELECT status FROM rag_sandbox_approvals WHERE id=?", (approval_id,)
        ).fetchone()
        assert row["status"] == "expired"


def test_finalized_query_set_blocks_new_queries(tmp_path: Path) -> None:
    database = tmp_path / "qs_finalize_insert.db"
    initialize_database(database)
    with database_connection(database) as connection:
        ids = _full_chain(connection)
        connection.execute(
            "UPDATE rag_sandbox_query_sets SET status='finalized' WHERE id=?",
            (ids["query_set_id"],),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO rag_sandbox_queries(public_id, query_set_id, query_text,
                query_type, created_by) VALUES (?,?,?,?,?)""",
                ("q-late", ids["query_set_id"], "Late query?", "fact_lookup", ADMIN_ID),
            )


def test_finalized_query_set_blocks_query_update_and_delete(tmp_path: Path) -> None:
    database = tmp_path / "qs_finalize_update.db"
    initialize_database(database)
    with database_connection(database) as connection:
        ids = _full_chain(connection)
        connection.execute(
            "UPDATE rag_sandbox_query_sets SET status='finalized' WHERE id=?",
            (ids["query_set_id"],),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE rag_sandbox_queries SET query_text='edited' WHERE id=?",
                (ids["query_id"],),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("DELETE FROM rag_sandbox_queries WHERE id=?", (ids["query_id"],))


def test_query_set_itself_is_immutable_once_finalized(tmp_path: Path) -> None:
    database = tmp_path / "qs_row_immutable.db"
    initialize_database(database)
    with database_connection(database) as connection:
        ids = _full_chain(connection)
        connection.execute(
            "UPDATE rag_sandbox_query_sets SET status='finalized' WHERE id=?",
            (ids["query_set_id"],),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE rag_sandbox_query_sets SET name='renamed' WHERE id=?",
                (ids["query_set_id"],),
            )


def test_draft_query_set_allows_edits(tmp_path: Path) -> None:
    database = tmp_path / "qs_draft_edit.db"
    initialize_database(database)
    with database_connection(database) as connection:
        ids = _full_chain(connection)
        connection.execute(
            "UPDATE rag_sandbox_queries SET query_text='edited while draft' WHERE id=?",
            (ids["query_id"],),
        )
        connection.commit()
        row = connection.execute(
            "SELECT query_text FROM rag_sandbox_queries WHERE id=?", (ids["query_id"],)
        ).fetchone()
        assert row["query_text"] == "edited while draft"


@pytest.mark.parametrize(
    "table,columns,values",
    [
        (
            "rag_sandbox_records",
            "(public_id,experiment_id,corpus_id,sample_record_id,content,content_checksum)",
            None,
        ),
        (
            "rag_sandbox_events",
            "(public_id,experiment_id,event_type,performed_by_admin_public_id)",
            None,
        ),
    ],
)
def test_append_only_tables_reject_update_and_delete(
    tmp_path: Path, table: str, columns: str, values
) -> None:
    database = tmp_path / f"append_only_{table}.db"
    initialize_database(database)
    with database_connection(database) as connection:
        ids = _full_chain(connection)
        if table == "rag_sandbox_records":
            connection.execute(
                f"INSERT INTO {table}{columns} VALUES (?,?,?,?,?,?)",
                ("row-1", ids["experiment_id"], ids["corpus_id"], ids["record_id"], "hi", "chk"),
            )
        else:
            connection.execute(
                f"INSERT INTO {table}{columns} VALUES (?,?,?,?)",
                ("row-1", ids["experiment_id"], "experiment_created", ADMIN_ID),
            )
        connection.commit()
        row_id = connection.execute(
            f"SELECT id FROM {table} WHERE public_id='row-1'"
        ).fetchone()[0]
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(f"UPDATE {table} SET public_id='row-1-edited' WHERE id=?", (row_id,))
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(f"DELETE FROM {table} WHERE id=?", (row_id,))


def _insert_index(connection, ids, public_id="idx-1") -> int:
    connection.execute(
        """INSERT INTO rag_sandbox_indexes(public_id, experiment_id, corpus_id, index_kind,
        created_by_admin_public_id) VALUES (?,?,?,?,?)""",
        (public_id, ids["experiment_id"], ids["corpus_id"], "bm25", ADMIN_ID),
    )
    return connection.execute(
        "SELECT id FROM rag_sandbox_indexes WHERE public_id=?", (public_id,)
    ).fetchone()[0]


def test_indexes_are_mutable_through_lifecycle_updates(tmp_path: Path) -> None:
    database = tmp_path / "index_lifecycle.db"
    initialize_database(database)
    with database_connection(database) as connection:
        ids = _full_chain(connection)
        index_id = _insert_index(connection, ids)
        connection.execute(
            "UPDATE rag_sandbox_indexes SET status='validated' WHERE id=?", (index_id,)
        )
        connection.execute(
            "UPDATE rag_sandbox_indexes SET status='active' WHERE id=?", (index_id,)
        )
        connection.commit()
        row = connection.execute(
            "SELECT status FROM rag_sandbox_indexes WHERE id=?", (index_id,)
        ).fetchone()
        assert row["status"] == "active"


def _insert_retrieval_run(connection, ids, index_id, public_id="run-1") -> int:
    connection.execute(
        """INSERT INTO rag_sandbox_retrieval_runs(public_id, experiment_id, index_id,
        query_set_id, performed_by_admin_public_id) VALUES (?,?,?,?,?)""",
        (public_id, ids["experiment_id"], index_id, ids["query_set_id"], ADMIN_ID),
    )
    return connection.execute(
        "SELECT id FROM rag_sandbox_retrieval_runs WHERE public_id=?", (public_id,)
    ).fetchone()[0]


def test_retrieval_run_and_result_append_only(tmp_path: Path) -> None:
    database = tmp_path / "retrieval_append.db"
    initialize_database(database)
    with database_connection(database) as connection:
        ids = _full_chain(connection)
        index_id = _insert_index(connection, ids)
        run_id = _insert_retrieval_run(connection, ids, index_id)
        connection.execute(
            """INSERT INTO rag_sandbox_retrieval_results(public_id, retrieval_run_id,
            query_id) VALUES (?,?,?)""",
            ("result-1", run_id, ids["query_id"]),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE rag_sandbox_retrieval_runs SET total_queries=99 WHERE id=?", (run_id,)
            )
        result_id = connection.execute(
            "SELECT id FROM rag_sandbox_retrieval_results WHERE public_id='result-1'"
        ).fetchone()[0]
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE rag_sandbox_retrieval_results SET result_count=5 WHERE id=?",
                (result_id,),
            )


def test_deletion_request_transitions_are_separate_appended_rows(tmp_path: Path) -> None:
    database = tmp_path / "deletion.db"
    initialize_database(database)
    with database_connection(database) as connection:
        ids = _full_chain(connection)
        connection.execute(
            """INSERT INTO rag_sandbox_deletion_requests(public_id, deletion_request_code,
            experiment_id, status, reason, requested_by_admin_public_id)
            VALUES (?,?,?,?,?,?)""",
            ("del-1", "DEL-CODE-1", ids["experiment_id"], "requested", "no longer needed",
             ADMIN_ID),
        )
        connection.commit()
        req_id = connection.execute(
            "SELECT id FROM rag_sandbox_deletion_requests WHERE public_id='del-1'"
        ).fetchone()[0]
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE rag_sandbox_deletion_requests SET status='confirmed' WHERE id=?",
                (req_id,),
            )
        # the correct pattern: append a new row sharing the same code
        connection.execute(
            """INSERT INTO rag_sandbox_deletion_requests(public_id, deletion_request_code,
            experiment_id, status, reason, requested_by_admin_public_id,
            confirmed_by_admin_public_id, confirmed_at) VALUES (?,?,?,?,?,?,?,CURRENT_TIMESTAMP)""",
            ("del-2", "DEL-CODE-1", ids["experiment_id"], "confirmed", "no longer needed",
             ADMIN_ID, ADMIN_ID),
        )
        connection.commit()
        rows = connection.execute(
            "SELECT status FROM rag_sandbox_deletion_requests WHERE deletion_request_code=? "
            "ORDER BY id",
            ("DEL-CODE-1",),
        ).fetchall()
        assert [r["status"] for r in rows] == ["requested", "confirmed"]


def test_deleting_experiment_is_blocked_by_append_only_child_row(tmp_path: Path) -> None:
    """Mirrors Phase 12's discovery: ON DELETE CASCADE from a parent still
    fires the child's own append-only BEFORE DELETE trigger, aborting the
    whole cascade -- deleting an experiment with any report is blocked."""

    database = tmp_path / "cascade_blocked.db"
    initialize_database(database)
    with database_connection(database) as connection:
        ids = _full_chain(connection)
        connection.execute(
            """INSERT INTO rag_sandbox_reports(public_id, experiment_id, report_json,
            report_checksum_sha256, production_rag_readiness, training_data_observation,
            finalized_by_admin_public_id) VALUES (?,?,?,?,?,?,?)""",
            ("report-1", ids["experiment_id"], "{}", "chk", "not_assessed", "not_assessed",
             ADMIN_ID),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "DELETE FROM rag_sandbox_experiments WHERE id=?", (ids["experiment_id"],)
            )


def test_citation_rejects_unknown_validation_status(tmp_path: Path) -> None:
    database = tmp_path / "citation_status.db"
    initialize_database(database)
    with database_connection(database) as connection:
        ids = _full_chain(connection)
        index_id = _insert_index(connection, ids)
        run_id = _insert_retrieval_run(connection, ids, index_id)
        connection.execute(
            """INSERT INTO rag_sandbox_retrieval_results(public_id, retrieval_run_id,
            query_id) VALUES (?,?,?)""",
            ("result-1", run_id, ids["query_id"]),
        )
        result_id = connection.execute(
            "SELECT id FROM rag_sandbox_retrieval_results WHERE public_id='result-1'"
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO rag_sandbox_answer_runs(public_id, experiment_id,
            retrieval_result_id, query_id, status, performed_by_admin_public_id)
            VALUES (?,?,?,?,?,?)""",
            ("ans-1", ids["experiment_id"], result_id, ids["query_id"], "grounded_answer",
             ADMIN_ID),
        )
        answer_run_id = connection.execute(
            "SELECT id FROM rag_sandbox_answer_runs WHERE public_id='ans-1'"
        ).fetchone()[0]
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO rag_sandbox_citations(public_id, answer_run_id, citation_label,
                validation_status) VALUES (?,?,?,?)""",
                ("cite-bad", answer_run_id, "[1]", "not_a_real_status"),
            )


def test_acceptance_requires_nonempty_reason(tmp_path: Path) -> None:
    database = tmp_path / "acceptance_reason.db"
    initialize_database(database)
    with database_connection(database) as connection:
        ids = _full_chain(connection)
        connection.execute(
            """INSERT INTO rag_sandbox_reports(public_id, experiment_id, report_json,
            report_checksum_sha256, production_rag_readiness, training_data_observation,
            finalized_by_admin_public_id) VALUES (?,?,?,?,?,?,?)""",
            ("report-1", ids["experiment_id"], "{}", "chk", "not_assessed", "not_assessed",
             ADMIN_ID),
        )
        report_id = connection.execute(
            "SELECT id FROM rag_sandbox_reports WHERE public_id='report-1'"
        ).fetchone()[0]
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO rag_sandbox_acceptances(public_id, experiment_id, report_id,
                decision, reason, reviewer_admin_public_id, report_checksum_sha256,
                target_fingerprint) VALUES (?,?,?,?,?,?,?,?)""",
                ("acc-bad", ids["experiment_id"], report_id, "accepted", "   ", ADMIN_ID,
                 "chk", "fp"),
            )


def test_acceptance_is_append_only(tmp_path: Path) -> None:
    database = tmp_path / "acceptance_append.db"
    initialize_database(database)
    with database_connection(database) as connection:
        ids = _full_chain(connection)
        connection.execute(
            """INSERT INTO rag_sandbox_reports(public_id, experiment_id, report_json,
            report_checksum_sha256, production_rag_readiness, training_data_observation,
            finalized_by_admin_public_id) VALUES (?,?,?,?,?,?,?)""",
            ("report-1", ids["experiment_id"], "{}", "chk", "not_assessed", "not_assessed",
             ADMIN_ID),
        )
        report_id = connection.execute(
            "SELECT id FROM rag_sandbox_reports WHERE public_id='report-1'"
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO rag_sandbox_acceptances(public_id, experiment_id, report_id,
            decision, reason, reviewer_admin_public_id, report_checksum_sha256,
            target_fingerprint) VALUES (?,?,?,?,?,?,?,?)""",
            ("acc-1", ids["experiment_id"], report_id, "needs_more_testing",
             "insufficient query coverage", ADMIN_ID, "chk", "fp"),
        )
        connection.commit()
        acc_id = connection.execute(
            "SELECT id FROM rag_sandbox_acceptances WHERE public_id='acc-1'"
        ).fetchone()[0]
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE rag_sandbox_acceptances SET decision='accepted' WHERE id=?", (acc_id,)
            )
