import json
from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.external_data_providers import (
    ExternalDataProviderRepository,
)
from backend.services.external_data_connectors.base import HttpResponse
from backend.services.external_dataset_search_service import (
    ExternalDatasetCandidateService,
    ExternalDatasetSearchError,
    ExternalDatasetSearchExecutionService,
    ExternalDatasetSearchSessionService,
    build_query,
)

ADMIN_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "search.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return settings


@pytest.fixture
def session_service(settings: Settings) -> ExternalDatasetSearchSessionService:
    return ExternalDatasetSearchSessionService(settings)


def _enable_provider(settings: Settings, provider_code: str, *, with_search_capability: bool):
    provider_repository = ExternalDataProviderRepository(settings.resolved_database_path)
    provider = provider_repository.get_provider_by_code(provider_code)
    provider_repository.update_provider(
        provider["public_id"], {"lifecycle_status": "enabled", "enabled": 1}
    )
    if with_search_capability:
        provider_repository.upsert_capability(
            provider["public_id"], {"capability_type": "search_datasets", "enabled": True}
        )
    return provider_repository.get_provider(provider["public_id"])


def _hf_search_response(items):
    return HttpResponse(status_code=200, elapsed_ms=5, reachable=True, body=json.dumps(items))


def _empty_search_transport(url, headers, timeout_seconds):
    del headers, timeout_seconds
    if "huggingface.co/api/datasets" in url:
        return _hf_search_response([])
    if "api.github.com/search/repositories" in url:
        return HttpResponse(status_code=200, elapsed_ms=5, reachable=True, body='{"items": []}')
    if "wikidata.org" in url:
        return HttpResponse(status_code=200, elapsed_ms=5, reachable=True, body='{"search": []}')
    return HttpResponse(status_code=200, elapsed_ms=5, reachable=True, body="{}")


def _one_result_transport(url, headers, timeout_seconds):
    del headers, timeout_seconds
    if "huggingface.co/api/datasets" in url:
        return _hf_search_response(
            [
                {
                    "id": "ai4bharat/tamil-asr-corpus",
                    "cardData": {"summary": "Tamil ASR speech corpus", "license": "cc-by-4.0"},
                    "tags": ["asr", "tamil"],
                }
            ]
        )
    if "api.github.com/search/repositories" in url:
        return HttpResponse(status_code=200, elapsed_ms=5, reachable=True, body='{"items": []}')
    if "wikidata.org" in url:
        return HttpResponse(status_code=200, elapsed_ms=5, reachable=True, body='{"search": []}')
    return HttpResponse(status_code=200, elapsed_ms=5, reachable=True, body="{}")


def test_build_query_prefers_free_text() -> None:
    requirement = {
        "free_text_requirement": "Tamil ASR",
        "domain_tags": [],
        "tasks": [],
        "languages": [],
    }
    assert build_query(requirement) == "Tamil ASR"


def test_build_query_falls_back_to_tags_tasks_languages() -> None:
    requirement = {
        "free_text_requirement": "",
        "domain_tags": ["speech"],
        "tasks": ["asr"],
        "languages": ["tamil"],
    }
    assert build_query(requirement) == "speech asr tamil"


def test_build_query_defaults_when_nothing_present() -> None:
    requirement = {"free_text_requirement": "", "domain_tags": [], "tasks": [], "languages": []}
    assert build_query(requirement) == "dataset"


def test_create_session_and_set_requirements(
    session_service: ExternalDatasetSearchSessionService,
) -> None:
    session = session_service.create_session(title="Tamil ASR search", admin_id=ADMIN_ID)
    assert session["status"] == "draft"

    requirements = session_service.set_requirements(
        session["public_id"], {"modality": "text", "languages": ["tamil"]}, admin_id=ADMIN_ID
    )
    assert requirements["languages"] == ["tamil"]

    updated_session = session_service.get_session(session["public_id"])
    assert updated_session["status"] == "ready"
    assert updated_session["current_stage"] == "search"


def test_cancel_session(session_service: ExternalDatasetSearchSessionService) -> None:
    session = session_service.create_session(title="X", admin_id=ADMIN_ID)
    cancelled = session_service.cancel_session(session["public_id"], admin_id=ADMIN_ID)
    assert cancelled["status"] == "cancelled"

    with pytest.raises(ExternalDatasetSearchError):
        session_service.cancel_session(session["public_id"], admin_id=ADMIN_ID)


def test_run_search_rejects_session_without_requirements(
    settings: Settings, session_service: ExternalDatasetSearchSessionService
) -> None:
    session = session_service.create_session(title="X", admin_id=ADMIN_ID)
    execution_service = ExternalDatasetSearchExecutionService(
        settings, transport=_empty_search_transport
    )
    with pytest.raises(ExternalDatasetSearchError):
        execution_service.run_search(session["public_id"], admin_id=ADMIN_ID)


def test_run_search_with_no_enabled_providers_fails_cleanly(
    settings: Settings, session_service: ExternalDatasetSearchSessionService
) -> None:
    session = session_service.create_session(title="X", admin_id=ADMIN_ID)
    session_service.set_requirements(
        session["public_id"], {"languages": ["tamil"]}, admin_id=ADMIN_ID
    )
    execution_service = ExternalDatasetSearchExecutionService(
        settings, transport=_empty_search_transport
    )
    result = execution_service.run_search(session["public_id"], admin_id=ADMIN_ID)
    assert result["status"] == "failed"
    assert result["provider_count"] == 0


def test_run_search_completes_with_zero_results(settings: Settings, session_service) -> None:
    _enable_provider(settings, "huggingface", with_search_capability=True)
    session = session_service.create_session(title="X", admin_id=ADMIN_ID)
    session_service.set_requirements(
        session["public_id"], {"languages": ["tamil"], "tasks": ["asr"]}, admin_id=ADMIN_ID
    )
    execution_service = ExternalDatasetSearchExecutionService(
        settings, transport=_empty_search_transport
    )
    result = execution_service.run_search(session["public_id"], admin_id=ADMIN_ID)
    assert result["status"] == "completed"
    assert result["result_count"] == 0
    assert result["successful_provider_count"] == 1


def test_run_search_creates_scored_candidate_from_one_provider(
    settings: Settings, session_service
) -> None:
    _enable_provider(settings, "huggingface", with_search_capability=True)
    session = session_service.create_session(title="Tamil ASR search", admin_id=ADMIN_ID)
    session_service.set_requirements(
        session["public_id"],
        {"modality": "text", "languages": ["tamil"], "tasks": ["asr"]},
        admin_id=ADMIN_ID,
    )
    execution_service = ExternalDatasetSearchExecutionService(
        settings, transport=_one_result_transport
    )
    result = execution_service.run_search(session["public_id"], admin_id=ADMIN_ID)

    assert result["status"] == "completed"
    assert result["result_count"] == 1

    candidates = execution_service.repository.list_candidates(session["public_id"])
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate["canonical_name"] == "tamil-asr-corpus"
    assert candidate["declared_licence"] == "cc-by-4.0"
    assert candidate["suitability_score"] is not None

    sources = execution_service.repository.list_candidate_sources(candidate["public_id"])
    assert len(sources) == 1
    assert sources[0]["provider_dataset_id"] == "ai4bharat/tamil-asr-corpus"

    events = execution_service.repository.list_events(session["public_id"], limit=20)
    event_types = {event["event_type"] for event in events}
    assert "search_started" in event_types
    assert "search_completed" in event_types
    assert "provider_run_completed" in event_types


def test_run_search_one_provider_failure_does_not_block_others(
    settings: Settings, session_service
) -> None:
    _enable_provider(settings, "huggingface", with_search_capability=True)
    _enable_provider(settings, "github", with_search_capability=True)

    def transport(url, headers, timeout_seconds):
        del headers, timeout_seconds
        if "huggingface.co" in url:
            raise RuntimeError("simulated unexpected connector crash")
        return _one_result_transport(url, None, None)

    session = session_service.create_session(title="X", admin_id=ADMIN_ID)
    session_service.set_requirements(
        session["public_id"], {"languages": ["tamil"], "tasks": ["asr"]}, admin_id=ADMIN_ID
    )
    execution_service = ExternalDatasetSearchExecutionService(settings, transport=transport)
    result = execution_service.run_search(session["public_id"], admin_id=ADMIN_ID)

    assert result["status"] == "partial"
    assert result["successful_provider_count"] == 1
    assert result["failed_provider_count"] == 1

    runs = execution_service.repository.list_provider_runs(session["public_id"])
    statuses = {run["provider_code"]: run["status"] for run in runs}
    assert statuses["huggingface"] == "failed"
    assert statuses["github"] == "success"


def test_run_search_re_run_merges_same_provider_dataset_id(
    settings: Settings, session_service
) -> None:
    _enable_provider(settings, "huggingface", with_search_capability=True)
    session = session_service.create_session(title="X", admin_id=ADMIN_ID)
    session_service.set_requirements(
        session["public_id"], {"languages": ["tamil"], "tasks": ["asr"]}, admin_id=ADMIN_ID
    )
    execution_service = ExternalDatasetSearchExecutionService(
        settings, transport=_one_result_transport
    )
    session_service.repository.update_session(session["public_id"], {"status": "ready"})
    execution_service.run_search(session["public_id"], admin_id=ADMIN_ID)

    session_service.repository.update_session(session["public_id"], {"status": "ready"})
    result = execution_service.run_search(session["public_id"], admin_id=ADMIN_ID)

    assert result["result_count"] == 1
    candidates = execution_service.repository.list_candidates(session["public_id"])
    assert len(candidates) == 1
    sources = execution_service.repository.list_candidate_sources(candidates[0]["public_id"])
    assert len(sources) == 1


def test_manual_candidate_can_still_be_added_after_a_search_finishes(
    settings: Settings, session_service
) -> None:
    """Regression test: a session that finished searching (even with
    `status="failed"`, e.g. because no provider was enabled) is still
    an open research workspace an admin can keep curating -- only an
    explicitly cancelled/expired session should refuse a new manual
    candidate. Caught via manual browser verification (Flow D)."""

    session = session_service.create_session(title="X", admin_id=ADMIN_ID)
    session_service.set_requirements(
        session["public_id"], {"languages": ["tamil"]}, admin_id=ADMIN_ID
    )
    execution_service = ExternalDatasetSearchExecutionService(
        settings, transport=_empty_search_transport
    )
    result = execution_service.run_search(session["public_id"], admin_id=ADMIN_ID)
    assert result["status"] == "failed"

    candidate_service = ExternalDatasetCandidateService(settings)
    candidate = candidate_service.add_manual_candidate(
        session["public_id"], {"canonical_name": "Added after a failed search"}, admin_id=ADMIN_ID
    )
    assert candidate["canonical_name"] == "Added after a failed search"


def test_manual_candidate_is_refused_on_a_cancelled_session(
    settings: Settings, session_service
) -> None:
    session = session_service.create_session(title="X", admin_id=ADMIN_ID)
    session_service.cancel_session(session["public_id"], admin_id=ADMIN_ID)

    candidate_service = ExternalDatasetCandidateService(settings)
    with pytest.raises(ExternalDatasetSearchError):
        candidate_service.add_manual_candidate(
            session["public_id"], {"canonical_name": "Too late"}, admin_id=ADMIN_ID
        )
