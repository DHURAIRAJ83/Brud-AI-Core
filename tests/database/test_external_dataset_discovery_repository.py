from pathlib import Path

import pytest

from backend.database.migrations import initialize_database
from backend.database.repositories.base import ConflictError, NotFoundError
from backend.database.repositories.external_data_providers import (
    ExternalDataProviderRepository,
)
from backend.database.repositories.external_dataset_discovery import (
    ExternalDatasetDiscoveryRepository,
)

ADMIN_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    path = tmp_path / "discovery.db"
    initialize_database(path)
    return path


@pytest.fixture
def repository(database_path: Path) -> ExternalDatasetDiscoveryRepository:
    return ExternalDatasetDiscoveryRepository(database_path)


@pytest.fixture
def provider_public_id(database_path: Path) -> str:
    provider_repository = ExternalDataProviderRepository(database_path)
    provider = provider_repository.get_provider_by_code("huggingface")
    assert provider is not None
    return provider["public_id"]


def _create_session(repository, code="session-1"):
    return repository.create_session(
        {
            "session_code": code,
            "title": "Tamil ASR corpus",
            "requested_by_admin_public_id": ADMIN_ID,
        }
    )


def test_create_and_get_session_defaults(repository: ExternalDatasetDiscoveryRepository) -> None:
    session = _create_session(repository)
    assert session["status"] == "draft"
    assert session["current_stage"] == "requirement"
    assert session["result_count"] == 0
    assert session["provider_count"] == 0

    fetched = repository.get_session(session["public_id"])
    assert fetched == session

    with pytest.raises(NotFoundError):
        repository.get_session("does-not-exist")


def test_get_session_by_code(repository: ExternalDatasetDiscoveryRepository) -> None:
    session = _create_session(repository, code="by-code")
    found = repository.get_session_by_code("by-code")
    assert found["public_id"] == session["public_id"]
    assert repository.get_session_by_code("missing-code") is None


def test_list_sessions_filters(repository: ExternalDatasetDiscoveryRepository) -> None:
    s1 = _create_session(repository, code="s1")
    s2 = _create_session(repository, code="s2")
    repository.update_session(s2["public_id"], {"status": "running"})

    all_items = repository.list_sessions(limit=50)
    assert {s1["public_id"], s2["public_id"]} <= {item["public_id"] for item in all_items}

    running_only = repository.list_sessions(status="running")
    assert [item["public_id"] for item in running_only] == [s2["public_id"]]

    by_requester = repository.list_sessions(requested_by_admin_public_id=ADMIN_ID)
    assert {s1["public_id"], s2["public_id"]} <= {item["public_id"] for item in by_requester}


def test_update_session(repository: ExternalDatasetDiscoveryRepository) -> None:
    session = _create_session(repository)
    updated = repository.update_session(
        session["public_id"], {"status": "ready", "current_stage": "search"}
    )
    assert updated["status"] == "ready"
    assert updated["current_stage"] == "search"

    with pytest.raises(NotFoundError):
        repository.update_session("does-not-exist", {"status": "ready"})


def test_requirements_upsert_is_one_to_one(repository: ExternalDatasetDiscoveryRepository) -> None:
    session = _create_session(repository)
    assert repository.get_requirements(session["public_id"]) is None

    created = repository.upsert_requirements(
        session["public_id"],
        {
            "modality": "text",
            "languages": ["tamil", "english"],
            "tasks": ["asr_transcription"],
            "intended_uses": ["research"],
            "commercial_requirement": "unknown",
            "free_text_requirement": "Tamil speech transcripts",
        },
    )
    assert created["languages"] == ["tamil", "english"]
    assert created["commercial_requirement"] == "unknown"

    updated = repository.upsert_requirements(
        session["public_id"],
        {"modality": "text", "languages": ["tamil"], "commercial_requirement": "required"},
    )
    assert updated["public_id"] == created["public_id"]
    assert updated["languages"] == ["tamil"]
    assert updated["commercial_requirement"] == "required"

    fetched = repository.get_requirements(session["public_id"])
    assert fetched == updated


def test_provider_run_lifecycle(
    repository: ExternalDatasetDiscoveryRepository, provider_public_id: str
) -> None:
    session = _create_session(repository)
    run = repository.create_provider_run(
        session["public_id"], {"provider_public_id": provider_public_id, "query_used": "tamil asr"}
    )
    assert run["status"] == "success"
    assert run["provider_code"] == "huggingface"

    updated = repository.update_provider_run(
        run["public_id"], {"result_count": 3, "status": "success", "latency_ms": 120}
    )
    assert updated["result_count"] == 3
    assert updated["latency_ms"] == 120

    runs = repository.list_provider_runs(session["public_id"])
    assert [item["public_id"] for item in runs] == [run["public_id"]]

    with pytest.raises(NotFoundError):
        repository.create_provider_run(
            session["public_id"], {"provider_public_id": "does-not-exist"}
        )


def _create_candidate(repository, session_public_id, **overrides):
    values = {
        "canonical_name": "IndicVoices Tamil ASR",
        "normalized_name": "indicvoices tamil asr",
        "description": "Tamil speech corpus",
        "declared_licence": "cc-by-4.0",
    }
    values.update(overrides)
    return repository.create_candidate(session_public_id, values)


def test_candidate_lifecycle(
    repository: ExternalDatasetDiscoveryRepository, provider_public_id: str
) -> None:
    session = _create_session(repository)
    candidate = _create_candidate(
        repository, session["public_id"], primary_provider_public_id=provider_public_id
    )
    assert candidate["licence_status"] == "unknown"
    assert candidate["commercial_use_status"] == "unknown"
    assert candidate["training_use_status"] == "not_approved"
    assert candidate["rag_use_status"] == "not_approved"
    assert candidate["evaluation_use_status"] == "not_approved"
    assert candidate["excluded"] is False
    assert candidate["primary_provider_public_id"] == provider_public_id

    fetched = repository.get_candidate(candidate["public_id"])
    assert fetched == candidate

    with pytest.raises(NotFoundError):
        repository.get_candidate("does-not-exist")

    updated = repository.update_candidate(
        candidate["public_id"],
        {"suitability_score": 72.5, "recommendation_status": "recommended_for_review"},
    )
    assert updated["suitability_score"] == 72.5
    assert updated["recommendation_status"] == "recommended_for_review"

    excluded = repository.update_candidate(candidate["public_id"], {"excluded": 1})
    assert excluded["excluded"] is True


def test_candidate_use_status_can_never_become_approved(
    repository: ExternalDatasetDiscoveryRepository,
) -> None:
    session = _create_session(repository)
    candidate = _create_candidate(repository, session["public_id"])
    with pytest.raises(ConflictError):
        repository.update_candidate(candidate["public_id"], {"training_use_status": "approved"})


def test_mark_possible_duplicate(repository: ExternalDatasetDiscoveryRepository) -> None:
    session = _create_session(repository)
    original = _create_candidate(
        repository, session["public_id"], canonical_name="Original", normalized_name="original"
    )
    duplicate = _create_candidate(
        repository, session["public_id"], canonical_name="Duplicate", normalized_name="duplicate"
    )
    updated = repository.mark_possible_duplicate(duplicate["public_id"], original["public_id"])
    assert updated["possible_duplicate_of_candidate_public_id"] == original["public_id"]

    with pytest.raises(NotFoundError):
        repository.mark_possible_duplicate("does-not-exist", original["public_id"])
    with pytest.raises(NotFoundError):
        repository.mark_possible_duplicate(duplicate["public_id"], "does-not-exist")


def test_list_candidates_ordering_and_exclusion_filter(
    repository: ExternalDatasetDiscoveryRepository,
) -> None:
    session = _create_session(repository)
    low = _create_candidate(
        repository, session["public_id"], canonical_name="Low", normalized_name="low"
    )
    high = _create_candidate(
        repository, session["public_id"], canonical_name="High", normalized_name="high"
    )
    repository.update_candidate(low["public_id"], {"suitability_score": 10})
    repository.update_candidate(high["public_id"], {"suitability_score": 90})
    repository.update_candidate(low["public_id"], {"excluded": 1})

    all_items = repository.list_candidates(session["public_id"], include_excluded=True)
    assert [item["public_id"] for item in all_items] == [high["public_id"], low["public_id"]]

    visible_only = repository.list_candidates(session["public_id"], include_excluded=False)
    assert [item["public_id"] for item in visible_only] == [high["public_id"]]


def test_candidate_source_add_and_conflict_upsert(
    repository: ExternalDatasetDiscoveryRepository, provider_public_id: str
) -> None:
    session = _create_session(repository)
    candidate = _create_candidate(repository, session["public_id"])
    source = repository.add_candidate_source(
        candidate["public_id"],
        {
            "provider_public_id": provider_public_id,
            "provider_dataset_id": "org/indicvoices-tamil",
            "source_url": "https://huggingface.co/datasets/org/indicvoices-tamil",
            "raw_metadata": {"downloads": 100},
            "raw_metadata_checksum": "abc123",
        },
    )
    assert source["provider_dataset_id"] == "org/indicvoices-tamil"
    assert source["raw_metadata"] == {"downloads": 100}

    updated = repository.add_candidate_source(
        candidate["public_id"],
        {
            "provider_public_id": provider_public_id,
            "provider_dataset_id": "org/indicvoices-tamil",
            "source_url": "https://huggingface.co/datasets/org/indicvoices-tamil",
            "raw_metadata": {"downloads": 200},
            "raw_metadata_checksum": "def456",
        },
    )
    assert updated["public_id"] == source["public_id"]
    assert updated["raw_metadata"] == {"downloads": 200}

    sources = repository.list_candidate_sources(candidate["public_id"])
    assert len(sources) == 1

    with pytest.raises(NotFoundError):
        repository.add_candidate_source(
            "does-not-exist",
            {"provider_public_id": provider_public_id, "provider_dataset_id": "x"},
        )


def test_candidate_scores_are_replaced_on_rescore(
    repository: ExternalDatasetDiscoveryRepository,
) -> None:
    session = _create_session(repository)
    candidate = _create_candidate(repository, session["public_id"])
    first = repository.set_candidate_scores(
        candidate["public_id"],
        [
            {
                "dimension": "language_fit",
                "raw_value": 1.0,
                "weight": 10,
                "score": 10,
                "reason": "tamil match",
            },
            {
                "dimension": "task_fit",
                "raw_value": 0.5,
                "weight": 8,
                "score": 4,
                "reason": "partial match",
            },
        ],
    )
    assert {item["dimension"] for item in first} == {"language_fit", "task_fit"}

    second = repository.set_candidate_scores(
        candidate["public_id"],
        [
            {
                "dimension": "language_fit",
                "raw_value": 0.8,
                "weight": 10,
                "score": 8,
                "reason": "revised",
            }
        ],
    )
    assert len(second) == 1
    assert second[0]["dimension"] == "language_fit"
    assert second[0]["score"] == 8

    fetched = repository.list_candidate_scores(candidate["public_id"])
    assert len(fetched) == 1


def test_comparisons(repository: ExternalDatasetDiscoveryRepository) -> None:
    session = _create_session(repository)
    a = _create_candidate(repository, session["public_id"], canonical_name="A", normalized_name="a")
    b = _create_candidate(repository, session["public_id"], canonical_name="B", normalized_name="b")

    comparison = repository.create_comparison(
        session["public_id"],
        {
            "candidate_ids": [a["public_id"], b["public_id"]],
            "summary": {"winner": a["public_id"]},
            "created_by_admin_public_id": ADMIN_ID,
        },
    )
    assert comparison["candidate_ids"] == [a["public_id"], b["public_id"]]

    fetched = repository.get_comparison(comparison["public_id"])
    assert fetched == comparison

    listed = repository.list_comparisons(session["public_id"])
    assert [item["public_id"] for item in listed] == [comparison["public_id"]]

    with pytest.raises(NotFoundError):
        repository.get_comparison("does-not-exist")


def test_events_are_recorded_and_listed_newest_first(
    repository: ExternalDatasetDiscoveryRepository,
) -> None:
    session = _create_session(repository)
    first = repository.record_event(
        session["public_id"],
        {
            "event_type": "session_created",
            "summary": "created",
            "performed_by_admin_public_id": ADMIN_ID,
        },
    )
    second = repository.record_event(
        session["public_id"],
        {
            "event_type": "search_started",
            "summary": "started",
            "performed_by_admin_public_id": ADMIN_ID,
        },
    )

    events = repository.list_events(session["public_id"])
    assert [item["public_id"] for item in events] == [second["public_id"], first["public_id"]]


def test_events_are_append_only(repository: ExternalDatasetDiscoveryRepository) -> None:
    import sqlite3

    session = _create_session(repository)
    event = repository.record_event(
        session["public_id"],
        {
            "event_type": "session_created",
            "summary": "created",
            "performed_by_admin_public_id": ADMIN_ID,
        },
    )
    with repository.transaction() as connection, pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE external_dataset_search_events SET summary='changed' WHERE public_id=?",
            (event["public_id"],),
        )
