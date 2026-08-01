from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.services.admin_assistant_service import AdminAssistantError, AdminAssistantService
from backend.services.admin_assistant_tools import run_tool
from backend.services.external_dataset_search_service import ExternalDatasetSearchSessionService

ADMIN_ID = "00000000-0000-0000-0000-000000000001"


def _approve(assistant, proposal_id):
    return assistant.review(proposal_id, decision="approved", reviewed_by=ADMIN_ID, comment=None)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "assistant_discovery.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return settings


def _create_ready_session(settings: Settings) -> dict:
    session_service = ExternalDatasetSearchSessionService(settings)
    session = session_service.create_session(title="Tamil ASR search", admin_id=ADMIN_ID)
    session_service.set_requirements(
        session["public_id"], {"languages": ["tamil"], "tasks": ["asr"]}, admin_id=ADMIN_ID
    )
    return session


# -- read-only tools ----------------------------------------------------


def test_list_and_get_dataset_search_session_tools(settings: Settings) -> None:
    session = _create_ready_session(settings)

    listed = run_tool("list_dataset_search_sessions", settings)
    assert session["public_id"] in {item["public_id"] for item in listed["items"]}

    found = run_tool(
        "get_dataset_search_session", settings, {"public_id": session["public_id"]}
    )
    assert found["available"] is True
    assert found["session"]["public_id"] == session["public_id"]
    assert found["requirement"]["languages"] == ["tamil"]

    missing = run_tool("get_dataset_search_session", settings, {"public_id": "does-not-exist"})
    assert missing["available"] is False


def test_list_and_get_dataset_candidate_tools(settings: Settings) -> None:
    from backend.services.external_dataset_search_service import ExternalDatasetCandidateService

    session = _create_ready_session(settings)
    candidate_service = ExternalDatasetCandidateService(settings)
    candidate = candidate_service.add_manual_candidate(
        session["public_id"], {"canonical_name": "Manually Found Corpus"}, admin_id=ADMIN_ID
    )

    listed = run_tool(
        "list_dataset_candidates", settings, {"session_public_id": session["public_id"]}
    )
    assert listed["available"] is True
    assert [item["public_id"] for item in listed["items"]] == [candidate["public_id"]]

    found = run_tool("get_dataset_candidate", settings, {"public_id": candidate["public_id"]})
    assert found["available"] is True
    assert found["canonical_name"] == "Manually Found Corpus"
    assert found["sources"] == []
    assert found["scores"] == []

    missing = run_tool("get_dataset_candidate", settings, {"public_id": "does-not-exist"})
    assert missing["available"] is False


# -- controlled actions: propose -> review -> execute --------------------


def test_run_dataset_search_action_end_to_end_with_no_enabled_providers(
    settings: Settings,
) -> None:
    session = _create_ready_session(settings)
    assistant = AdminAssistantService(settings)

    proposal = assistant.propose(
        action_type="run_dataset_search",
        target_type="external_dataset_search_session",
        target_public_id=session["public_id"],
        request_payload={},
        requested_by=ADMIN_ID,
        summary="Run the discovery search",
    )
    assert proposal.risk_level == "moderate"
    assert proposal.preview["current_state"]["status"] == "ready"

    _approve(assistant, proposal.public_id)
    executed = assistant.execute(proposal.public_id, executor_public_id=ADMIN_ID)
    assert executed.execution_status == "succeeded"
    assert executed.execution_result["status"] == "failed"
    assert executed.execution_result["provider_count"] == 0


def test_run_dataset_search_rejected_at_confirm_if_session_cancelled_first(
    settings: Settings,
) -> None:
    session = _create_ready_session(settings)
    session_service = ExternalDatasetSearchSessionService(settings)
    assistant = AdminAssistantService(settings)

    proposal = assistant.propose(
        action_type="run_dataset_search",
        target_type="external_dataset_search_session",
        target_public_id=session["public_id"],
        request_payload={},
        requested_by=ADMIN_ID,
        summary="Run the discovery search",
    )

    # Someone else cancels the session before this proposal is confirmed.
    session_service.cancel_session(session["public_id"], admin_id=ADMIN_ID)

    with pytest.raises(AdminAssistantError, match="changed since this proposal"):
        _approve(assistant, proposal.public_id)


def test_exclude_dataset_candidate_action_end_to_end(settings: Settings) -> None:
    from backend.services.external_dataset_search_service import ExternalDatasetCandidateService

    session = _create_ready_session(settings)
    candidate = ExternalDatasetCandidateService(settings).add_manual_candidate(
        session["public_id"], {"canonical_name": "Low Quality Candidate"}, admin_id=ADMIN_ID
    )

    assistant = AdminAssistantService(settings)
    proposal = assistant.propose(
        action_type="exclude_dataset_candidate",
        target_type="external_dataset_candidate",
        target_public_id=candidate["public_id"],
        request_payload={},
        requested_by=ADMIN_ID,
        summary="Exclude this candidate",
    )
    assert proposal.risk_level == "low"
    _approve(assistant, proposal.public_id)
    executed = assistant.execute(proposal.public_id, executor_public_id=ADMIN_ID)
    assert executed.execution_status == "succeeded"
    assert executed.execution_result["excluded"] is True
