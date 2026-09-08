from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.connection import database_connection
from backend.database.migrations import initialize_database
from backend.database.repositories.dataset_verification import DatasetVerificationRepository
from backend.database.repositories.external_dataset_discovery import (
    ExternalDatasetDiscoveryRepository,
)
from backend.services.admin_assistant_chat_service import AdminAssistantChatService
from backend.services.admin_assistant_service import (
    ACTION_EXECUTORS,
    PREVIEW_GENERATORS,
    STALE_CHECK_FINGERPRINTS,
    AdminAssistantService,
)
from backend.services.admin_assistant_tools import TOOL_BY_NAME, run_tool
from core_model.admin_assistant.action_registry import ACTION_BY_TYPE, is_known_action_type
from core_model.admin_assistant.dataset_verification_help import (
    DATASET_VERIFICATION_FAQ,
    match_dataset_verification_question,
)
from core_model.admin_assistant.localization import localize

ADMIN_ID = "00000000-0000-0000-0000-000000000001"
OTHER_ADMIN_ID = "00000000-0000-0000-0000-000000000002"

NEW_ACTIONS = (
    "create_dataset_verification_case",
    "collect_dataset_licence_evidence",
    "add_manual_dataset_evidence",
    "assess_dataset_permissions",
    "review_dataset_permission",
    "resolve_dataset_verification_conflict",
    "finalize_dataset_verification_report",
    "reverify_dataset_evidence",
    "record_dataset_withdrawal_notice",
)

NEW_TOOLS = (
    "get_dataset_verification_case",
    "list_dataset_evidence",
    "get_dataset_permission_assessments",
    "get_dataset_verification_conflicts",
    "get_dataset_verification_report",
    "get_dataset_reverification_status",
)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "assistant.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    with database_connection(settings.resolved_database_path) as connection:
        connection.execute(
            "INSERT INTO admin_accounts(public_id, username, display_name, password_hash) "
            "VALUES (?,?,?,?)",
            (ADMIN_ID, "assistant-test-admin", "Assistant Test Admin", "hash"),
        )
        connection.commit()
    return settings


def _create_candidate(settings: Settings) -> str:
    discovery = ExternalDatasetDiscoveryRepository(settings.resolved_database_path)
    session = discovery.create_session(
        {"session_code": "session-1", "requested_by_admin_public_id": ADMIN_ID}
    )
    candidate = discovery.create_candidate(
        session["public_id"], {"canonical_name": "Tamil Corpus", "normalized_name": "tamil corpus"}
    )
    return candidate["public_id"]


def _run_action(
    assistant: AdminAssistantService,
    *,
    action_type,
    target_type,
    target_public_id,
    payload,
    summary,
    reviewer=ADMIN_ID,
):
    proposal = assistant.propose(
        action_type=action_type,
        target_type=target_type,
        target_public_id=target_public_id,
        request_payload=payload,
        requested_by=ADMIN_ID,
        summary=summary,
    )
    assistant.review(proposal.public_id, decision="approved", reviewed_by=reviewer, comment=None)
    return assistant.execute(proposal.public_id, executor_public_id=ADMIN_ID)


# -- tool registry ---------------------------------------------------------------


def test_all_6_dataset_verification_tools_are_registered() -> None:
    for name in NEW_TOOLS:
        assert name in TOOL_BY_NAME


def test_tools_report_unavailable_for_unknown_case(settings: Settings) -> None:
    for name, params in (
        ("get_dataset_verification_case", {"public_id": "missing"}),
        ("list_dataset_evidence", {"case_public_id": "missing"}),
        ("get_dataset_permission_assessments", {"case_public_id": "missing"}),
        ("get_dataset_verification_conflicts", {"case_public_id": "missing"}),
        ("get_dataset_verification_report", {"case_public_id": "missing"}),
        ("get_dataset_reverification_status", {"case_public_id": "missing"}),
    ):
        result = run_tool(name, settings, params)
        assert result["available"] is False


def test_tools_return_real_data_for_a_real_case(settings: Settings) -> None:
    candidate_public_id = _create_candidate(settings)
    repository = DatasetVerificationRepository(settings.resolved_database_path)
    case = repository.create_case(
        {
            "candidate_public_id": candidate_public_id,
            "verification_code": "VC-1",
            "requested_by_admin_public_id": ADMIN_ID,
        }
    )
    case_result = run_tool(
        "get_dataset_verification_case", settings, {"public_id": case["public_id"]}
    )
    assert case_result["available"] is True
    assert case_result["case"]["public_id"] == case["public_id"]

    evidence_result = run_tool(
        "list_dataset_evidence", settings, {"case_public_id": case["public_id"]}
    )
    assert evidence_result == {"available": True, "items": []}

    report_result = run_tool(
        "get_dataset_verification_report", settings, {"case_public_id": case["public_id"]}
    )
    assert report_result["available"] is False
    assert "not finalized" in report_result["reason"]

    reverify_result = run_tool(
        "get_dataset_reverification_status", settings, {"case_public_id": case["public_id"]}
    )
    assert reverify_result["available"] is True
    assert reverify_result["verification_expiry_status"] == "current"


# -- action registry parity -------------------------------------------------------


def test_all_9_actions_registered_with_full_parity() -> None:
    for action_type in NEW_ACTIONS:
        assert action_type in ACTION_BY_TYPE
        assert action_type in ACTION_EXECUTORS
        assert action_type in STALE_CHECK_FINGERPRINTS
        assert action_type in PREVIEW_GENERATORS
        assert is_known_action_type(action_type)


def test_review_dataset_permission_requires_reason_in_registry() -> None:
    assert ACTION_BY_TYPE["review_dataset_permission"].requires_reason is True
    assert ACTION_BY_TYPE["resolve_dataset_verification_conflict"].requires_reason is True


# -- end-to-end propose -> review -> execute ---------------------------------------


def test_full_verification_lifecycle_through_admin_assistant_pipeline(settings: Settings) -> None:
    candidate_public_id = _create_candidate(settings)
    assistant = AdminAssistantService(settings)

    created = _run_action(
        assistant,
        action_type="create_dataset_verification_case",
        target_type="external_dataset_candidate",
        target_public_id=candidate_public_id,
        payload={},
        summary="create case",
    )
    assert created.status == "approved"
    case_public_id = created.execution_result["public_id"]

    evidence = _run_action(
        assistant,
        action_type="add_manual_dataset_evidence",
        target_type="external_dataset_verification_case",
        target_public_id=case_public_id,
        payload={"evidence_type": "licence_file", "content_text": "Licensed under CC-BY-4.0."},
        summary="manual evidence",
    )
    assert evidence.execution_result["retrieval_status"] == "manual"

    assessed = _run_action(
        assistant,
        action_type="assess_dataset_permissions",
        target_type="external_dataset_verification_case",
        target_public_id=case_public_id,
        payload={},
        summary="assess permissions",
    )
    assert "rag_use" in assessed.execution_result["items"]

    # review_dataset_permission is risk_level="high" -- reviewer must
    # differ from the proposer (ADMIN_ID).
    reviewed = _run_action(
        assistant,
        action_type="review_dataset_permission",
        target_type="external_dataset_verification_case",
        target_public_id=case_public_id,
        payload={
            "permission_type": "rag_use", "status": "approved",
            "reason": "Licence file confirms CC-BY-4.0 permits RAG use",
        },
        summary="review rag_use",
        reviewer=OTHER_ADMIN_ID,
    )
    assert reviewed.execution_result["status"] == "approved"


def test_propose_review_dataset_permission_without_reason_is_rejected(settings: Settings) -> None:
    candidate_public_id = _create_candidate(settings)
    assistant = AdminAssistantService(settings)
    created = _run_action(
        assistant,
        action_type="create_dataset_verification_case",
        target_type="external_dataset_candidate",
        target_public_id=candidate_public_id,
        payload={},
        summary="create case",
    )
    case_public_id = created.execution_result["public_id"]

    from backend.services.admin_assistant_service import AdminAssistantError

    with pytest.raises(AdminAssistantError):
        assistant.propose(
            action_type="review_dataset_permission",
            target_type="external_dataset_verification_case",
            target_public_id=case_public_id,
            request_payload={"permission_type": "rag_use", "status": "approved"},
            requested_by=ADMIN_ID,
            summary="review rag_use without reason",
        )


def test_record_dataset_withdrawal_notice_end_to_end(settings: Settings) -> None:
    candidate_public_id = _create_candidate(settings)
    assistant = AdminAssistantService(settings)
    created = _run_action(
        assistant,
        action_type="create_dataset_verification_case",
        target_type="external_dataset_candidate",
        target_public_id=candidate_public_id,
        payload={},
        summary="create case",
    )
    case_public_id = created.execution_result["public_id"]

    # record_dataset_withdrawal_notice is risk_level="high" -- reviewer must
    # differ from the proposer (ADMIN_ID).
    notice = _run_action(
        assistant,
        action_type="record_dataset_withdrawal_notice",
        target_type="external_dataset_verification_case",
        target_public_id=case_public_id,
        payload={"notice_type": "licence_changed", "notice_text": "Rights holder changed terms"},
        summary="withdrawal notice",
        reviewer=OTHER_ADMIN_ID,
    )
    assert notice.execution_result["impact_status"] == "assessed"


# -- deterministic FAQ (Step 25) ----------------------------------------------------


@pytest.mark.parametrize(
    ("message", "expected_key"),
    [
        ("What is a declared licence?", "what_is_declared_licence"),
        ("Why is provider licence not enough?", "why_is_provider_licence_not_enough"),
        ("Why is commercial permission separate?", "why_is_commercial_permission_separate"),
        (
            "Why is upstream-source verification required?",
            "why_is_upstream_verification_required",
        ),
        ("Why is a dataset card insufficient?", "why_is_dataset_card_insufficient"),
        ("What does approved_with_conditions mean?", "what_does_approved_with_conditions_mean"),
        ("What happens if terms change?", "what_happens_if_terms_change"),
        ("Why can't the dataset be downloaded yet?", "why_cant_the_dataset_be_downloaded_yet"),
        ("hello, how are you", None),
    ],
)
def test_faq_matching(message, expected_key) -> None:
    assert match_dataset_verification_question(message) == expected_key


@pytest.mark.parametrize("faq_key", list(DATASET_VERIFICATION_FAQ))
@pytest.mark.parametrize("language", ["english", "tamil", "tanglish"])
def test_faq_localizes_in_every_language(faq_key, language) -> None:
    entry = DATASET_VERIFICATION_FAQ[faq_key]
    text = localize({"en": entry["en"], "ta": entry["ta"]}, language)
    assert text
    if language == "tanglish":
        # Tanglish must be Latin-script, never containing raw Tamil script.
        assert not any("஀" <= ch <= "௿" for ch in text)


# -- chat dispatch integration -------------------------------------------------------


def test_chat_answers_faq_question_deterministically(settings: Settings) -> None:
    service = AdminAssistantChatService(settings)
    result = service.send_message(
        admin_id=ADMIN_ID,
        message="What is a declared licence?",
        page_id="dataset_verification",
    )
    assert result["status"] == "completed"
    assert "declared" in result["answer"].lower()


def test_chat_answers_verification_navigation_guidance(settings: Settings) -> None:
    # Deliberately avoids the generic intent classifier's own
    # "help"/"navigation"/page-name-mention keywords (e.g. "how do",
    # "take me", a literal page title) so this message actually falls
    # through to the open_ended branch and exercises the new
    # `_match_dataset_verification_intent` path, not an earlier one.
    service = AdminAssistantChatService(settings)
    result = service.send_message(
        admin_id=ADMIN_ID,
        message="I want to verify licence for this dataset now",
        page_id="dataset_discovery",
    )
    assert result["status"] == "completed"
    assert result["intent"] == "open_ended"
    assert "verification" in result["answer"].lower()
    assert result["navigation_target"] == {
        "page_id": "dataset_verification", "nav_key": "Dataset Verification"
    }


def test_chat_never_answers_approved_from_declared_metadata_alone(settings: Settings) -> None:
    service = AdminAssistantChatService(settings)
    result = service.send_message(
        admin_id=ADMIN_ID,
        message="Why is provider licence not enough?",
        page_id="dataset_verification",
    )
    assert "never treated as proof" in result["answer"].lower()
