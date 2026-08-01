from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.dataset_sample_import import DatasetSampleImportRepository
from backend.database.repositories.dataset_verification import DatasetVerificationRepository
from backend.database.repositories.external_dataset_discovery import (
    ExternalDatasetDiscoveryRepository,
)
from backend.services.admin_assistant_service import AdminAssistantService
from backend.services.admin_assistant_tools import run_tool
from core_model.admin_assistant.action_registry import ACTION_BY_TYPE, is_blocked_action_type
from core_model.admin_assistant.sample_import_help import match_sample_import_question

ADMIN_ID = "00000000-0000-0000-0000-000000000001"

SAMPLE_ACTION_TYPES = (
    "create_sample_import",
    "request_sample_import_approval",
    "approve_sample_import",
    "download_approved_sample",
    "validate_sample_files",
    "extract_sample_archive",
    "scan_sample",
    "parse_sample",
    "run_sample_quality_checks",
    "run_sample_duplicate_checks",
    "run_sample_contamination_checks",
    "review_sample_issue",
    "finalize_sample_validation_report",
    "request_sample_deletion",
    "execute_sample_deletion",
)

SAMPLE_TOOL_NAMES = (
    "get_sample_import",
    "list_sample_files",
    "get_sample_scan_summary",
    "get_sample_quality_summary",
    "get_sample_pii_summary",
    "get_sample_duplicate_summary",
    "get_sample_contamination_summary",
    "get_sample_validation_report",
    "get_sample_rag_eligibility",
)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "assistant.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        quarantine_dir=tmp_path / "quarantine",
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return settings


def _finalized_case(settings: Settings) -> dict:
    discovery = ExternalDatasetDiscoveryRepository(settings.resolved_database_path)
    session = discovery.create_session(
        {"session_code": "session-1", "requested_by_admin_public_id": ADMIN_ID}
    )
    candidate = discovery.create_candidate(
        session["public_id"], {"canonical_name": "Corpus", "normalized_name": "corpus"}
    )
    verification = DatasetVerificationRepository(settings.resolved_database_path)
    case = verification.create_case(
        {
            "candidate_public_id": candidate["public_id"],
            "verification_code": "VC-1",
            "requested_by_admin_public_id": ADMIN_ID,
        }
    )
    verification.update_case(case["public_id"], {"identity_status": "verified"})
    for permission_type in ("rag_use", "evaluation_use"):
        verification.assess_permission(
            case["public_id"], permission_type,
            {"candidate_public_id": candidate["public_id"], "status": "likely_allowed"},
        )
        verification.review_permission(
            case["public_id"], permission_type,
            status="approved", reviewed_by=ADMIN_ID, reason="ok",
        )
    return verification.lock_case(case["public_id"], {"summary": "done"})


def _propose_review_execute(assistant: AdminAssistantService, **propose_kwargs):
    proposal = assistant.propose(**propose_kwargs)
    assistant.review(proposal.public_id, decision="approved", reviewed_by=ADMIN_ID, comment=None)
    return assistant.execute(proposal.public_id, executor_public_id=ADMIN_ID)


# -- registry completeness --------------------------------------------------------------


def test_all_15_sample_actions_are_registered_and_never_blocked() -> None:
    for action_type in SAMPLE_ACTION_TYPES:
        assert action_type in ACTION_BY_TYPE
        assert is_blocked_action_type(action_type) is False


def test_all_9_sample_tools_are_registered() -> None:
    from backend.services.admin_assistant_tools import TOOL_BY_NAME

    for name in SAMPLE_TOOL_NAMES:
        assert name in TOOL_BY_NAME


def test_no_sample_action_summary_or_confirmation_claims_training_approval() -> None:
    for action_type in SAMPLE_ACTION_TYPES:
        definition = ACTION_BY_TYPE[action_type]
        for language in ("en", "ta"):
            text = definition.summary[language] + definition.confirmation_text[language]
            assert "training_approved" not in text
            assert "Training Approved" not in text


# -- full propose -> review -> execute pipeline ------------------------------------------


def test_create_sample_import_through_full_pipeline(settings: Settings) -> None:
    case = _finalized_case(settings)
    assistant = AdminAssistantService(settings)
    result = _propose_review_execute(
        assistant,
        action_type="create_sample_import",
        target_type="external_dataset_verification_case",
        target_public_id=case["public_id"],
        request_payload={
            "purpose": "manual_review",
            "selection_method": "deterministic_first_n",
            "requested_count": 50,
        },
        requested_by=ADMIN_ID,
        summary="Create a sample import",
    )
    assert result.status == "approved"


def test_full_sample_pipeline_via_admin_assistant_actions(settings: Settings) -> None:
    case = _finalized_case(settings)
    assistant = AdminAssistantService(settings)
    _propose_review_execute(
        assistant,
        action_type="create_sample_import",
        target_type="external_dataset_verification_case",
        target_public_id=case["public_id"],
        request_payload={
            "purpose": "manual_review",
            "selection_method": "deterministic_first_n",
            "requested_count": 50,
        },
        requested_by=ADMIN_ID,
        summary="Create a sample import",
    )
    samples = DatasetSampleImportRepository(settings.resolved_database_path)
    sample_import = samples.list_sample_imports(verification_case_public_id=case["public_id"])[0]

    _propose_review_execute(
        assistant,
        action_type="request_sample_import_approval",
        target_type="external_dataset_sample_import",
        target_public_id=sample_import["public_id"],
        request_payload={
            "purpose": "manual_review", "requested_record_limit": 100,
            "requested_byte_limit": 100_000,
        },
        requested_by=ADMIN_ID,
        summary="Request approval",
    )
    _propose_review_execute(
        assistant,
        action_type="approve_sample_import",
        target_type="external_dataset_sample_import",
        target_public_id=sample_import["public_id"],
        request_payload={
            "approved_record_limit": 100, "approved_byte_limit": 100_000,
            "expires_at": "2026-12-31T00:00:00",
        },
        requested_by=ADMIN_ID,
        summary="Approve",
    )
    refreshed = samples.get_sample_import(sample_import["public_id"])
    assert refreshed["status"] == "approved"

    _propose_review_execute(
        assistant,
        action_type="validate_sample_files",
        target_type="external_dataset_sample_import",
        target_public_id=sample_import["public_id"],
        request_payload={},
        requested_by=ADMIN_ID,
        summary="Validate files",
    )
    _propose_review_execute(
        assistant,
        action_type="scan_sample",
        target_type="external_dataset_sample_import",
        target_public_id=sample_import["public_id"],
        request_payload={},
        requested_by=ADMIN_ID,
        summary="Scan",
    )
    _propose_review_execute(
        assistant,
        action_type="parse_sample",
        target_type="external_dataset_sample_import",
        target_public_id=sample_import["public_id"],
        request_payload={},
        requested_by=ADMIN_ID,
        summary="Parse",
    )

    tool_result = run_tool(
        "get_sample_import", settings, {"public_id": sample_import["public_id"]}
    )
    assert tool_result["available"] is True
    # validate -> scan -> parse advances status/stage past "approved" --
    # confirms the executors actually ran (not that they no-opped).
    assert tool_result["sample_import"]["status"] == "scanning"
    assert tool_result["sample_import"]["current_stage"] == "content_parsing"


def test_finalize_action_rejects_when_no_accepted_records(settings: Settings) -> None:
    case = _finalized_case(settings)
    assistant = AdminAssistantService(settings)
    _propose_review_execute(
        assistant,
        action_type="create_sample_import",
        target_type="external_dataset_verification_case",
        target_public_id=case["public_id"],
        request_payload={
            "purpose": "manual_review", "selection_method": "deterministic_first_n",
        },
        requested_by=ADMIN_ID,
        summary="Create",
    )
    samples = DatasetSampleImportRepository(settings.resolved_database_path)
    sample_import = samples.list_sample_imports(verification_case_public_id=case["public_id"])[0]

    finalized = _propose_review_execute(
        assistant,
        action_type="finalize_sample_validation_report",
        target_type="external_dataset_sample_import",
        target_public_id=sample_import["public_id"],
        request_payload={},
        requested_by=ADMIN_ID,
        summary="Finalize",
    )
    # execute() still succeeds at the proposal-lifecycle level, but the
    # underlying finalize() must have produced a not-eligible report --
    # never a rag_sandbox_eligible=true report with zero accepted records.
    assert finalized.status == "approved"
    refreshed = samples.get_sample_import(sample_import["public_id"])
    assert refreshed["rag_sandbox_eligible"] is False


def test_stale_check_rejects_approval_after_case_source_changes(settings: Settings) -> None:
    case = _finalized_case(settings)
    assistant = AdminAssistantService(settings)
    _propose_review_execute(
        assistant,
        action_type="create_sample_import",
        target_type="external_dataset_verification_case",
        target_public_id=case["public_id"],
        request_payload={
            "purpose": "manual_review", "selection_method": "deterministic_first_n",
        },
        requested_by=ADMIN_ID,
        summary="Create",
    )
    samples = DatasetSampleImportRepository(settings.resolved_database_path)
    sample_import = samples.list_sample_imports(verification_case_public_id=case["public_id"])[0]

    proposal = assistant.propose(
        action_type="request_sample_import_approval",
        target_type="external_dataset_sample_import",
        target_public_id=sample_import["public_id"],
        request_payload={
            "purpose": "manual_review", "requested_record_limit": 100,
            "requested_byte_limit": 100_000,
        },
        requested_by=ADMIN_ID,
        summary="Request approval",
    )
    # Simulate the sample import being cancelled after the proposal was
    # made, out from under the pending review.
    samples.update_sample_import(sample_import["public_id"], {"status": "cancelled"})

    from backend.services.admin_assistant_service import AdminAssistantError

    with pytest.raises(AdminAssistantError):
        assistant.review(
            proposal.public_id, decision="approved", reviewed_by=ADMIN_ID, comment=None
        )


# -- deterministic help / language modes -------------------------------------------------


def test_faq_matches_quarantine_question() -> None:
    assert match_sample_import_question("what is quarantine") == "what_is_quarantine"


def test_faq_matches_rag_sandbox_eligible_question() -> None:
    assert (
        match_sample_import_question("what does rag sandbox eligible mean")
        == "what_does_rag_sandbox_eligible_mean"
    )


def test_faq_returns_none_for_unrelated_message() -> None:
    assert match_sample_import_question("what is the weather today") is None


def test_faq_entries_have_nonempty_tamil_and_english_answers() -> None:
    from core_model.admin_assistant.sample_import_help import SAMPLE_IMPORT_FAQ

    assert len(SAMPLE_IMPORT_FAQ) == 10
    for entry in SAMPLE_IMPORT_FAQ.values():
        assert entry["en"].strip()
        assert entry["ta"].strip()
