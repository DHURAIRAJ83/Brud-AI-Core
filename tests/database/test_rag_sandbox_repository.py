import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest

from backend.database.migrations import initialize_database
from backend.database.repositories.base import NotFoundError, ValidationError
from backend.database.repositories.dataset_sample_import import DatasetSampleImportRepository
from backend.database.repositories.dataset_verification import DatasetVerificationRepository
from backend.database.repositories.external_dataset_discovery import (
    ExternalDatasetDiscoveryRepository,
)
from backend.database.repositories.rag_sandbox import RagSandboxRepository

ADMIN_ID = "00000000-0000-0000-0000-000000000001"
REVIEWER_ID = "00000000-0000-0000-0000-000000000002"


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    path = tmp_path / "rag_sandbox.db"
    initialize_database(path)
    return path


@pytest.fixture
def repository(database_path: Path) -> RagSandboxRepository:
    return RagSandboxRepository(database_path)


def _insert_knowledge_space(database_path: Path, *, slug: str = "sandbox-test") -> int:
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """INSERT INTO rag_knowledge_spaces(public_id, name, slug, created_by_admin_public_id)
            VALUES (?,?,?,?)""",
            (str(uuid4()), "Sandbox Test Space", slug, ADMIN_ID),
        )
        connection.commit()
        return connection.execute(
            "SELECT id FROM rag_knowledge_spaces WHERE slug=?", (slug,)
        ).fetchone()[0]


@pytest.fixture
def finalized_sample_import(database_path: Path) -> dict:
    """Builds a full Phase 12 lineage ending in a finalized, rag-sandbox-
    eligible sample import with one accepted record -- the minimum input
    Phase 13 experiments require."""

    discovery = ExternalDatasetDiscoveryRepository(database_path)
    session = discovery.create_session(
        {"session_code": "session-1", "requested_by_admin_public_id": ADMIN_ID}
    )
    candidate = discovery.create_candidate(
        session["public_id"],
        {"canonical_name": "Tamil Corpus", "normalized_name": "tamil corpus"},
    )
    verification = DatasetVerificationRepository(database_path)
    case = verification.create_case(
        {
            "candidate_public_id": candidate["public_id"],
            "verification_code": "VC-1",
            "requested_by_admin_public_id": ADMIN_ID,
        }
    )
    sample_repository = DatasetSampleImportRepository(database_path)
    sample_import = sample_repository.create_sample_import(
        {
            "sample_import_code": "SI-1",
            "verification_case_public_id": case["public_id"],
            "candidate_public_id": candidate["public_id"],
            "purpose": "manual_review",
            "selection_method": "deterministic_first_n",
            "requested_count": 10,
            "requested_by_admin_public_id": ADMIN_ID,
        }
    )
    sample_file = sample_repository.add_file(
        sample_import["public_id"],
        {
            "original_filename": "corpus.txt",
            "safe_filename": "corpus.txt",
            "relative_path": "corpus.txt",
            "declared_format": "txt",
        },
    )
    record = sample_repository.add_record(
        sample_import["public_id"],
        {
            "source_file_public_id": sample_file["public_id"],
            "modality": "text",
            "language": "tamil",
            "raw_content": "தமிழ் உரை",
            "normalized_content": "தமிழ் உரை",
            "source_checksum": "chk-source-1",
            "record_checksum": "chk-record-1",
            "status": "accepted",
        },
    )
    with sqlite3.connect(database_path) as connection:
        record_id = connection.execute(
            "SELECT id FROM external_dataset_sample_records WHERE public_id=?",
            (record["public_id"],),
        ).fetchone()[0]
    sample_repository.add_review(
        sample_import["public_id"],
        {
            "target_type": "record",
            "target_id": record_id,
            "decision": "accept",
            "reason": "clean record",
            "reviewer_admin_public_id": REVIEWER_ID,
        },
    )
    report = sample_repository.add_report(
        sample_import["public_id"],
        {
            "rag_sandbox_eligible": True,
            "training_assessment_status": "not_assessed",
            "report": {"summary": "ok"},
            "finalized_by_admin_public_id": ADMIN_ID,
        },
    )
    sample_repository.lock_sample_import(
        sample_import["public_id"],
        report={"summary": "ok"},
        rag_sandbox_eligible=True,
        training_assessment_status="not_assessed",
        status="validated",
    )
    return {
        "sample_import": sample_repository.get_sample_import(sample_import["public_id"]),
        "sample_report": report,
        "verification_case_public_id": case["public_id"],
        "record": record,
    }


def _create_experiment(
    repository: RagSandboxRepository, finalized_sample_import: dict, *, code: str = "EXP-1"
) -> dict:
    return repository.create_experiment(
        {
            "experiment_code": code,
            "sample_import_public_id": finalized_sample_import["sample_import"]["public_id"],
            "sample_report_public_id": finalized_sample_import["sample_report"]["public_id"],
            "verification_case_public_id": finalized_sample_import["verification_case_public_id"],
            "purpose": "retrieval_validation",
            "maximum_records": 100,
            "maximum_total_characters": 500_000,
            "maximum_total_tokens": 100_000,
            "created_by_admin_public_id": ADMIN_ID,
        }
    )


def _create_approval(
    repository: RagSandboxRepository, finalized_sample_import: dict, experiment: dict
) -> dict:
    return repository.create_approval(
        experiment["public_id"],
        {
            "sample_import_public_id": finalized_sample_import["sample_import"]["public_id"],
            "sample_report_public_id": finalized_sample_import["sample_report"]["public_id"],
            "verification_case_public_id": finalized_sample_import["verification_case_public_id"],
            "purpose": "retrieval_validation",
            "accepted_record_ids": [finalized_sample_import["record"]["public_id"]],
            "accepted_record_checksums": ["chk-record-1"],
            "maximum_records": 100,
            "maximum_total_characters": 500_000,
            "maximum_total_tokens": 100_000,
            "target_fingerprint": "fp-1",
            "requested_by_admin_public_id": ADMIN_ID,
        },
    )


# -- experiments -----------------------------------------------------------------------


def test_create_and_get_experiment(
    repository: RagSandboxRepository, finalized_sample_import: dict
) -> None:
    experiment = _create_experiment(repository, finalized_sample_import)
    assert experiment["status"] == "draft"
    assert experiment["current_stage"] == "eligibility"
    fetched = repository.get_experiment(experiment["public_id"])
    assert fetched["experiment_code"] == "EXP-1"
    assert (
        fetched["sample_import_public_id"]
        == finalized_sample_import["sample_import"]["public_id"]
    )


def test_get_experiment_missing_raises(repository: RagSandboxRepository) -> None:
    with pytest.raises(NotFoundError):
        repository.get_experiment("does-not-exist")


def test_list_experiments_filters_by_status(
    repository: RagSandboxRepository, finalized_sample_import: dict
) -> None:
    experiment = _create_experiment(repository, finalized_sample_import)
    repository.update_experiment(experiment["public_id"], {"status": "awaiting_approval"})
    matches = repository.list_experiments(status="awaiting_approval")
    assert any(row["public_id"] == experiment["public_id"] for row in matches)
    assert not repository.list_experiments(status="accepted")


def test_get_active_experiment_for_sample_report_excludes_terminal(
    repository: RagSandboxRepository, finalized_sample_import: dict
) -> None:
    experiment = _create_experiment(repository, finalized_sample_import)
    active = repository.get_active_experiment_for_sample_report(
        finalized_sample_import["sample_report"]["public_id"]
    )
    assert active["public_id"] == experiment["public_id"]
    repository.update_experiment(experiment["public_id"], {"status": "rejected"})
    assert (
        repository.get_active_experiment_for_sample_report(
            finalized_sample_import["sample_report"]["public_id"]
        )
        is None
    )


def test_set_experiment_knowledge_space(
    repository: RagSandboxRepository, database_path: Path, finalized_sample_import: dict
) -> None:
    experiment = _create_experiment(repository, finalized_sample_import)
    space_id = _insert_knowledge_space(database_path)
    updated = repository.set_experiment_knowledge_space(experiment["public_id"], space_id)
    assert updated["knowledge_space_public_id"] is not None


def test_mark_experiment_deleted_sets_deleted_at(
    repository: RagSandboxRepository, finalized_sample_import: dict
) -> None:
    experiment = _create_experiment(repository, finalized_sample_import)
    deleted = repository.mark_experiment_deleted(experiment["public_id"])
    assert deleted["status"] == "deleted"
    assert deleted["deleted_at"] is not None


def test_overview_counts_reflect_live_state(
    repository: RagSandboxRepository, finalized_sample_import: dict
) -> None:
    experiment = _create_experiment(repository, finalized_sample_import)
    repository.update_experiment(experiment["public_id"], {"status": "awaiting_approval"})
    counts = repository.overview_counts()
    assert counts["rag_sandbox_experiments_awaiting_approval"] >= 1


# -- approvals ---------------------------------------------------------------------------


def test_create_approval_defaults_to_pending(
    repository: RagSandboxRepository, finalized_sample_import: dict
) -> None:
    experiment = _create_experiment(repository, finalized_sample_import)
    approval = _create_approval(repository, finalized_sample_import, experiment)
    assert approval["status"] == "pending"
    assert approval["target_fingerprint"] == "fp-1"


def test_approve_approval_requires_pending(
    repository: RagSandboxRepository, finalized_sample_import: dict
) -> None:
    experiment = _create_experiment(repository, finalized_sample_import)
    approval = _create_approval(repository, finalized_sample_import, experiment)
    approved = repository.approve_approval(
        approval["public_id"], approved_by_admin_id=ADMIN_ID, expires_at=None
    )
    assert approved["status"] == "approved"
    with pytest.raises(ValidationError):
        repository.approve_approval(
            approval["public_id"], approved_by_admin_id=ADMIN_ID, expires_at=None
        )


def test_reject_approval_requires_pending(
    repository: RagSandboxRepository, finalized_sample_import: dict
) -> None:
    experiment = _create_experiment(repository, finalized_sample_import)
    approval = _create_approval(repository, finalized_sample_import, experiment)
    rejected = repository.reject_approval(approval["public_id"])
    assert rejected["status"] == "rejected"
    with pytest.raises(ValidationError):
        repository.reject_approval(approval["public_id"])


def test_expire_approval_requires_pending_or_approved(
    repository: RagSandboxRepository, finalized_sample_import: dict
) -> None:
    experiment = _create_experiment(repository, finalized_sample_import)
    approval = _create_approval(repository, finalized_sample_import, experiment)
    repository.approve_approval(
        approval["public_id"], approved_by_admin_id=ADMIN_ID, expires_at=None
    )
    expired = repository.expire_approval(approval["public_id"])
    assert expired["status"] == "expired"
    with pytest.raises(ValidationError):
        repository.expire_approval(approval["public_id"])


def test_supersede_approval_requires_approved(
    repository: RagSandboxRepository, finalized_sample_import: dict
) -> None:
    experiment = _create_experiment(repository, finalized_sample_import)
    approval = _create_approval(repository, finalized_sample_import, experiment)
    with pytest.raises(ValidationError):
        repository.supersede_approval(approval["public_id"])
    repository.approve_approval(
        approval["public_id"], approved_by_admin_id=ADMIN_ID, expires_at=None
    )
    superseded = repository.supersede_approval(approval["public_id"])
    assert superseded["status"] == "superseded"


def test_approval_immutable_once_approved_at_sql_level(
    repository: RagSandboxRepository, database_path: Path, finalized_sample_import: dict
) -> None:
    experiment = _create_experiment(repository, finalized_sample_import)
    approval = _create_approval(repository, finalized_sample_import, experiment)
    repository.approve_approval(
        approval["public_id"], approved_by_admin_id=ADMIN_ID, expires_at=None
    )
    with sqlite3.connect(database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE rag_sandbox_approvals SET maximum_records=999 WHERE public_id=?",
                (approval["public_id"],),
            )


def test_get_latest_approval_returns_most_recent(
    repository: RagSandboxRepository, finalized_sample_import: dict
) -> None:
    experiment = _create_experiment(repository, finalized_sample_import)
    first = _create_approval(repository, finalized_sample_import, experiment)
    repository.reject_approval(first["public_id"])
    second = _create_approval(repository, finalized_sample_import, experiment)
    latest = repository.get_latest_approval(experiment["public_id"])
    assert latest["public_id"] == second["public_id"]


# -- corpora and records -------------------------------------------------------------------


def test_create_corpus_and_add_record(
    repository: RagSandboxRepository, database_path: Path, finalized_sample_import: dict
) -> None:
    experiment = _create_experiment(repository, finalized_sample_import)
    space_id = _insert_knowledge_space(database_path, slug=f"sandbox-{experiment['public_id']}")
    corpus = repository.create_corpus(
        experiment["public_id"],
        {
            "knowledge_space_id": space_id,
            "sandbox_scope_key": f"sandbox-{experiment['public_id']}",
            "created_by_admin_public_id": ADMIN_ID,
        },
    )
    assert corpus["production_visible"] is False
    assert corpus["status"] == "preparing"

    record = repository.add_record(
        experiment["public_id"],
        {
            "corpus_public_id": corpus["public_id"],
            "sample_record_public_id": finalized_sample_import["record"]["public_id"],
            "content": "தமிழ் உரை",
            "content_checksum": "chk-record-1",
            "language": "tamil",
        },
    )
    assert record["content_checksum"] == "chk-record-1"
    assert repository.count_records(experiment["public_id"]) == 1
    assert record["rag_source_id"] is None


def test_records_are_append_only_at_sql_level(
    repository: RagSandboxRepository, database_path: Path, finalized_sample_import: dict
) -> None:
    experiment = _create_experiment(repository, finalized_sample_import)
    space_id = _insert_knowledge_space(database_path, slug=f"sandbox-{experiment['public_id']}")
    corpus = repository.create_corpus(
        experiment["public_id"],
        {
            "knowledge_space_id": space_id,
            "sandbox_scope_key": f"sandbox-{experiment['public_id']}",
            "created_by_admin_public_id": ADMIN_ID,
        },
    )
    record = repository.add_record(
        experiment["public_id"],
        {
            "corpus_public_id": corpus["public_id"],
            "sample_record_public_id": finalized_sample_import["record"]["public_id"],
            "content": "text",
            "content_checksum": "chk-record-1",
        },
    )
    with sqlite3.connect(database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE rag_sandbox_records SET content='tampered' WHERE public_id=?",
                (record["public_id"],),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "DELETE FROM rag_sandbox_records WHERE public_id=?", (record["public_id"],)
            )


def test_production_visible_hard_checked_to_zero(
    repository: RagSandboxRepository, database_path: Path, finalized_sample_import: dict
) -> None:
    experiment = _create_experiment(repository, finalized_sample_import)
    space_id = _insert_knowledge_space(database_path, slug=f"sandbox-{experiment['public_id']}")
    with sqlite3.connect(database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO rag_sandbox_corpora(
                public_id, experiment_id, knowledge_space_id, sandbox_scope_key,
                production_visible, created_by_admin_public_id)
                VALUES (?,(SELECT id FROM rag_sandbox_experiments WHERE public_id=?),?,?,1,?)""",
                (str(uuid4()), experiment["public_id"], space_id, "bad-scope", ADMIN_ID),
            )


# -- indexes ---------------------------------------------------------------------------------


def _create_corpus(
    repository: RagSandboxRepository, database_path: Path, experiment: dict
) -> dict:
    space_id = _insert_knowledge_space(database_path, slug=f"sandbox-{experiment['public_id']}")
    return repository.create_corpus(
        experiment["public_id"],
        {
            "knowledge_space_id": space_id,
            "sandbox_scope_key": f"sandbox-{experiment['public_id']}",
            "created_by_admin_public_id": ADMIN_ID,
        },
    )


def test_create_and_update_index(
    repository: RagSandboxRepository, database_path: Path, finalized_sample_import: dict
) -> None:
    experiment = _create_experiment(repository, finalized_sample_import)
    corpus = _create_corpus(repository, database_path, experiment)
    index = repository.create_index(
        experiment["public_id"],
        {
            "corpus_public_id": corpus["public_id"],
            "index_kind": "hybrid",
            "build_config": {"top_k": 10},
            "created_by_admin_public_id": ADMIN_ID,
        },
    )
    assert index["status"] == "building"
    updated = repository.update_index(index["public_id"], {"status": "active", "chunk_count": 5})
    assert updated["status"] == "active"
    assert updated["chunk_count"] == 5
    assert len(repository.list_indexes(experiment["public_id"])) == 1


# -- query sets and queries -----------------------------------------------------------------


def test_query_set_lifecycle_and_finalize_blocks_further_queries(
    repository: RagSandboxRepository, finalized_sample_import: dict
) -> None:
    experiment = _create_experiment(repository, finalized_sample_import)
    query_set = repository.create_query_set(
        experiment["public_id"], {"name": "Base set", "created_by_admin_public_id": ADMIN_ID}
    )
    assert query_set["status"] == "draft"
    query = repository.add_query(
        query_set["public_id"],
        {
            "query_text": "தமிழ் என்றால் என்ன?",
            "language": "tamil",
            "query_type": "fact_lookup",
            "created_by": ADMIN_ID,
        },
    )
    assert query["human_authored"] is True
    refreshed_set = repository.get_query_set(query_set["public_id"])
    assert refreshed_set["query_count"] == 1

    finalized = repository.finalize_query_set(
        query_set["public_id"], finalized_by_admin_public_id=ADMIN_ID
    )
    assert finalized["status"] == "finalized"
    with pytest.raises(ValidationError):
        repository.add_query(
            query_set["public_id"],
            {
                "query_text": "another query",
                "query_type": "fact_lookup",
                "created_by": ADMIN_ID,
            },
        )
    with pytest.raises(ValidationError):
        repository.finalize_query_set(query_set["public_id"], finalized_by_admin_public_id=ADMIN_ID)


def test_queries_immutable_after_finalize_at_sql_level(
    repository: RagSandboxRepository, database_path: Path, finalized_sample_import: dict
) -> None:
    experiment = _create_experiment(repository, finalized_sample_import)
    query_set = repository.create_query_set(
        experiment["public_id"], {"name": "Base set", "created_by_admin_public_id": ADMIN_ID}
    )
    query = repository.add_query(
        query_set["public_id"],
        {"query_text": "q1", "query_type": "fact_lookup", "created_by": ADMIN_ID},
    )
    repository.finalize_query_set(query_set["public_id"], finalized_by_admin_public_id=ADMIN_ID)
    with sqlite3.connect(database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE rag_sandbox_queries SET query_text='tampered' WHERE public_id=?",
                (query["public_id"],),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO rag_sandbox_queries(
                public_id, query_set_id, query_text, query_type, created_by)
                VALUES (?,(SELECT id FROM rag_sandbox_query_sets WHERE public_id=?),?,?,?)""",
                (str(uuid4()), query_set["public_id"], "q2", "fact_lookup", ADMIN_ID),
            )


def test_count_unreviewed_assistant_queries(
    repository: RagSandboxRepository, finalized_sample_import: dict
) -> None:
    experiment = _create_experiment(repository, finalized_sample_import)
    query_set = repository.create_query_set(
        experiment["public_id"], {"name": "Base set", "created_by_admin_public_id": ADMIN_ID}
    )
    query = repository.add_query(
        query_set["public_id"],
        {
            "query_text": "assistant suggested",
            "query_type": "fact_lookup",
            "created_by": "assistant",
            "human_authored": False,
        },
    )
    assert repository.count_unreviewed_assistant_queries(query_set["public_id"]) == 1
    repository.review_query(query["public_id"], reviewed_by_admin_public_id=ADMIN_ID)
    assert repository.count_unreviewed_assistant_queries(query_set["public_id"]) == 0


# -- retrieval / answers / citations / evaluations / human reviews ---------------------------


def _build_query_pipeline(
    repository: RagSandboxRepository, database_path: Path, finalized_sample_import: dict
) -> dict:
    experiment = _create_experiment(repository, finalized_sample_import)
    corpus = _create_corpus(repository, database_path, experiment)
    index = repository.create_index(
        experiment["public_id"],
        {
            "corpus_public_id": corpus["public_id"],
            "index_kind": "bm25",
            "created_by_admin_public_id": ADMIN_ID,
        },
    )
    query_set = repository.create_query_set(
        experiment["public_id"], {"name": "Base set", "created_by_admin_public_id": ADMIN_ID}
    )
    query = repository.add_query(
        query_set["public_id"],
        {"query_text": "q1", "query_type": "fact_lookup", "created_by": ADMIN_ID},
    )
    return {
        "experiment": experiment,
        "corpus": corpus,
        "index": index,
        "query_set": query_set,
        "query": query,
    }


def test_retrieval_run_and_result_lifecycle(
    repository: RagSandboxRepository, database_path: Path, finalized_sample_import: dict
) -> None:
    ctx = _build_query_pipeline(repository, database_path, finalized_sample_import)
    run = repository.record_retrieval_run(
        ctx["experiment"]["public_id"],
        {
            "index_public_id": ctx["index"]["public_id"],
            "query_set_public_id": ctx["query_set"]["public_id"],
            "total_queries": 1,
            "performed_by_admin_public_id": ADMIN_ID,
        },
    )
    assert run["status"] == "completed"
    result = repository.add_retrieval_result(
        run["public_id"],
        {
            "query_public_id": ctx["query"]["public_id"],
            "metric_availability": "full",
            "expected_source_hit": True,
            "recall_at_k": 1.0,
        },
    )
    assert result["expected_source_hit"] is True
    assert len(repository.list_retrieval_results(run["public_id"])) == 1

    with sqlite3.connect(database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "DELETE FROM rag_sandbox_retrieval_results WHERE public_id=?",
                (result["public_id"],),
            )


def test_answer_run_citation_evaluation_and_human_review(
    repository: RagSandboxRepository, database_path: Path, finalized_sample_import: dict
) -> None:
    ctx = _build_query_pipeline(repository, database_path, finalized_sample_import)
    run = repository.record_retrieval_run(
        ctx["experiment"]["public_id"],
        {
            "index_public_id": ctx["index"]["public_id"],
            "query_set_public_id": ctx["query_set"]["public_id"],
            "performed_by_admin_public_id": ADMIN_ID,
        },
    )
    result = repository.add_retrieval_result(
        run["public_id"], {"query_public_id": ctx["query"]["public_id"]}
    )
    answer_run = repository.add_answer_run(
        ctx["experiment"]["public_id"],
        {
            "retrieval_result_public_id": result["public_id"],
            "query_public_id": ctx["query"]["public_id"],
            "answer_text": "Sandbox evaluation output — not production guidance. [S1]",
            "status": "grounded_answer",
            "performed_by_admin_public_id": ADMIN_ID,
        },
    )
    assert answer_run["status"] == "grounded_answer"

    citation = repository.add_citation(
        answer_run["public_id"],
        {
            "citation_label": "S1",
            "references_retrieved_source": True,
            "source_exists": True,
            "validation_status": "valid",
        },
    )
    assert citation["validation_status"] == "valid"
    assert len(repository.list_citations(answer_run["public_id"])) == 1
    assert len(repository.list_citations_for_experiment(ctx["experiment"]["public_id"])) == 1

    evaluation = repository.add_evaluation(
        ctx["experiment"]["public_id"],
        {
            "answer_run_public_id": answer_run["public_id"],
            "query_public_id": ctx["query"]["public_id"],
            "evaluation_type": "unsupported_claim",
            "result_status": "supported",
        },
    )
    assert evaluation["automated"] is True
    assert len(repository.list_evaluations(ctx["experiment"]["public_id"])) == 1
    assert (
        len(
            repository.list_evaluations(
                ctx["experiment"]["public_id"], evaluation_type="unsupported_claim"
            )
        )
        == 1
    )

    review = repository.add_human_review(
        ctx["experiment"]["public_id"],
        {
            "query_public_id": ctx["query"]["public_id"],
            "answer_run_public_id": answer_run["public_id"],
            "answer_grounded": True,
            "decision": "pass",
            "reviewer_admin_public_id": ADMIN_ID,
        },
    )
    assert review["decision"] == "pass"
    assert (
        repository.get_latest_human_review_for_query(ctx["query"]["public_id"])["public_id"]
        == review["public_id"]
    )

    with sqlite3.connect(database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE rag_sandbox_answer_runs SET answer_text='tampered' WHERE public_id=?",
                (answer_run["public_id"],),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "DELETE FROM rag_sandbox_citations WHERE public_id=?", (citation["public_id"],)
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "DELETE FROM rag_sandbox_human_reviews WHERE public_id=?", (review["public_id"],)
            )


# -- reports and acceptances -----------------------------------------------------------------


def test_report_versions_increment_and_are_immutable(
    repository: RagSandboxRepository, database_path: Path, finalized_sample_import: dict
) -> None:
    experiment = _create_experiment(repository, finalized_sample_import)
    first = repository.add_report(
        experiment["public_id"],
        {
            "report": {"summary": "v1"},
            "report_checksum_sha256": "chk-1",
            "production_rag_readiness": "not_assessed",
            "training_data_observation": "not_assessed",
            "finalized_by_admin_public_id": ADMIN_ID,
        },
    )
    second = repository.add_report(
        experiment["public_id"],
        {
            "report": {"summary": "v2"},
            "report_checksum_sha256": "chk-2",
            "production_rag_readiness": "potentially_ready",
            "training_data_observation": "not_assessed",
            "finalized_by_admin_public_id": ADMIN_ID,
        },
    )
    assert first["report_version"] == 1
    assert second["report_version"] == 2
    latest = repository.get_latest_report(experiment["public_id"])
    assert latest["public_id"] == second["public_id"]
    assert len(repository.list_reports(experiment["public_id"])) == 2

    with sqlite3.connect(database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE rag_sandbox_reports SET report_checksum_sha256='x' "
                "WHERE public_id=?",
                (second["public_id"],),
            )


def test_acceptance_lifecycle(
    repository: RagSandboxRepository, finalized_sample_import: dict
) -> None:
    experiment = _create_experiment(repository, finalized_sample_import)
    report = repository.add_report(
        experiment["public_id"],
        {
            "report": {"summary": "v1"},
            "report_checksum_sha256": "chk-1",
            "production_rag_readiness": "not_assessed",
            "training_data_observation": "not_assessed",
            "finalized_by_admin_public_id": ADMIN_ID,
        },
    )
    acceptance = repository.add_acceptance(
        experiment["public_id"],
        {
            "report_public_id": report["public_id"],
            "decision": "accepted_with_conditions",
            "reason": "queries mostly pass",
            "reviewer_admin_public_id": ADMIN_ID,
            "report_checksum_sha256": report["report_checksum_sha256"],
            "target_fingerprint": "fp-1",
        },
    )
    assert acceptance["decision"] == "accepted_with_conditions"
    assert (
        repository.get_latest_acceptance(experiment["public_id"])["public_id"]
        == acceptance["public_id"]
    )
    assert len(repository.list_acceptances(experiment["public_id"])) == 1


# -- events -----------------------------------------------------------------------------------


def test_record_event_defaults_performed_by_to_system(
    repository: RagSandboxRepository, finalized_sample_import: dict
) -> None:
    experiment = _create_experiment(repository, finalized_sample_import)
    event = repository.record_event(
        experiment["public_id"], {"event_type": "experiment_created"}
    )
    assert event["performed_by_admin_public_id"] == "system"
    events = repository.list_events(experiment["public_id"])
    assert len(events) == 1


# -- deletion lifecycle -------------------------------------------------------------------------


def test_deletion_lifecycle_requested_confirmed_executed(
    repository: RagSandboxRepository, finalized_sample_import: dict
) -> None:
    experiment = _create_experiment(repository, finalized_sample_import)
    requested = repository.request_deletion(
        experiment["public_id"],
        {"reason": "experiment complete", "requested_by_admin_public_id": ADMIN_ID},
    )
    assert requested["status"] == "requested"
    code = requested["deletion_request_code"]

    confirmed = repository.confirm_deletion(code, confirmed_by_admin_public_id=ADMIN_ID)
    assert confirmed["status"] == "confirmed"
    executed = repository.execute_deletion(code)
    assert executed["status"] == "executed"

    latest = repository.get_latest_deletion_request_by_code(code)
    assert latest["public_id"] == executed["public_id"]
    assert len(repository.list_deletion_requests(experiment["public_id"])) == 3


def test_cancel_deletion_records_cancelled_transition(
    repository: RagSandboxRepository, finalized_sample_import: dict
) -> None:
    experiment = _create_experiment(repository, finalized_sample_import)
    requested = repository.request_deletion(
        experiment["public_id"],
        {"reason": "no longer needed", "requested_by_admin_public_id": ADMIN_ID},
    )
    cancelled = repository.cancel_deletion(requested["deletion_request_code"])
    assert cancelled["status"] == "cancelled"


def test_confirm_deletion_unknown_code_raises(repository: RagSandboxRepository) -> None:
    with pytest.raises(NotFoundError):
        repository.confirm_deletion("does-not-exist", confirmed_by_admin_public_id=ADMIN_ID)


def test_deletion_requests_append_only_at_sql_level(
    repository: RagSandboxRepository, database_path: Path, finalized_sample_import: dict
) -> None:
    experiment = _create_experiment(repository, finalized_sample_import)
    requested = repository.request_deletion(
        experiment["public_id"],
        {"reason": "cleanup", "requested_by_admin_public_id": ADMIN_ID},
    )
    with sqlite3.connect(database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE rag_sandbox_deletion_requests SET status='executed' WHERE public_id=?",
                (requested["public_id"],),
            )
