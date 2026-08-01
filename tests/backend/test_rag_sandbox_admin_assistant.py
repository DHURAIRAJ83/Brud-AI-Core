import sqlite3
from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.connection import database_connection
from backend.database.migrations import initialize_database
from backend.database.repositories.dataset_sample_import import DatasetSampleImportRepository
from backend.database.repositories.dataset_verification import DatasetVerificationRepository
from backend.database.repositories.external_dataset_discovery import (
    ExternalDatasetDiscoveryRepository,
)
from backend.services.admin_assistant_chat_service import AdminAssistantChatService
from backend.services.admin_assistant_service import AdminAssistantService
from backend.services.rag_sandbox_eligibility_service import RagSandboxError
from core_model.admin_assistant.action_registry import ACTION_BY_TYPE, is_blocked_action_type
from core_model.admin_assistant.rag_sandbox_help import match_rag_sandbox_question

ADMIN_ID = "00000000-0000-0000-0000-000000000001"
REVIEWER_ID = "00000000-0000-0000-0000-000000000002"

RAG_SANDBOX_ACTION_TYPES = (
    "create_rag_sandbox_experiment",
    "request_rag_sandbox_approval",
    "approve_rag_sandbox_experiment",
    "prepare_rag_sandbox_corpus",
    "build_rag_sandbox_index",
    "create_rag_sandbox_query_set",
    "finalize_rag_sandbox_query_set",
    "run_rag_sandbox_retrieval",
    "run_rag_sandbox_generation",
    "run_rag_sandbox_evaluation",
    "review_rag_sandbox_query",
    "finalize_rag_sandbox_report",
    "accept_rag_sandbox",
    "reject_rag_sandbox",
    "request_rag_sandbox_deletion",
    "execute_rag_sandbox_deletion",
)

RAG_SANDBOX_TOOL_NAMES = (
    "get_rag_sandbox_experiment",
    "get_rag_sandbox_eligibility",
    "list_rag_sandbox_indexes",
    "get_rag_sandbox_retrieval_summary",
    "get_rag_sandbox_answer_summary",
    "get_rag_sandbox_citation_summary",
    "get_rag_sandbox_language_summary",
    "get_rag_sandbox_injection_summary",
    "get_rag_sandbox_report",
    "get_rag_sandbox_acceptance_status",
)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "rag_sandbox_assistant.db",
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
            (ADMIN_ID, "rag-sandbox-test-admin", "RAG Sandbox Test Admin", "hash"),
        )
        connection.commit()
    return settings


def _finalized_sample_import(settings: Settings) -> str:
    discovery = ExternalDatasetDiscoveryRepository(settings.resolved_database_path)
    session = discovery.create_session(
        {"session_code": "session-1", "requested_by_admin_public_id": ADMIN_ID}
    )
    candidate = discovery.create_candidate(
        session["public_id"],
        {
            "canonical_name": "Tamil Corpus", "normalized_name": "tamil corpus",
            "declared_licence": "CC-BY-4.0",
        },
    )
    verification = DatasetVerificationRepository(settings.resolved_database_path)
    case = verification.create_case(
        {
            "candidate_public_id": candidate["public_id"], "verification_code": "VC-1",
            "requested_by_admin_public_id": ADMIN_ID,
        }
    )
    verification.update_case(case["public_id"], {"identity_status": "verified"})
    verification.assess_permission(
        case["public_id"], "rag_use",
        {"candidate_public_id": candidate["public_id"], "status": "likely_allowed"},
    )
    verification.review_permission(
        case["public_id"], "rag_use",
        status="approved", reviewed_by=ADMIN_ID, reason="Licence review",
    )
    verification.lock_case(case["public_id"], {"summary": "finalized for test"})

    samples = DatasetSampleImportRepository(settings.resolved_database_path)
    sample_import = samples.create_sample_import(
        {
            "sample_import_code": "SI-1", "verification_case_public_id": case["public_id"],
            "candidate_public_id": candidate["public_id"], "purpose": "manual_review",
            "selection_method": "deterministic_first_n", "requested_count": 10,
            "requested_by_admin_public_id": ADMIN_ID,
        }
    )
    sample_file = samples.add_file(
        sample_import["public_id"],
        {
            "original_filename": "corpus.txt", "safe_filename": "corpus.txt",
            "relative_path": "corpus.txt", "declared_format": "txt",
        },
    )
    record = samples.add_record(
        sample_import["public_id"],
        {
            "source_file_public_id": sample_file["public_id"],
            "modality": "text", "language": "tamil",
            "raw_content": "தமிழ் உரை", "normalized_content": "தமிழ் உரை",
            "source_checksum": "chk-source-0", "record_checksum": "chk-record-0",
            "status": "accepted",
        },
    )
    with sqlite3.connect(settings.resolved_database_path) as connection:
        record_id = connection.execute(
            "SELECT id FROM external_dataset_sample_records WHERE public_id=?",
            (record["public_id"],),
        ).fetchone()[0]
    samples.add_review(
        sample_import["public_id"],
        {
            "target_type": "record", "target_id": record_id, "decision": "accept",
            "reason": "clean record", "reviewer_admin_public_id": REVIEWER_ID,
        },
    )
    samples.add_report(
        sample_import["public_id"],
        {
            "rag_sandbox_eligible": True, "training_assessment_status": "not_assessed",
            "report": {"summary": "ok"}, "finalized_by_admin_public_id": ADMIN_ID,
        },
    )
    samples.lock_sample_import(
        sample_import["public_id"], report={"summary": "ok"},
        rag_sandbox_eligible=True, training_assessment_status="not_assessed", status="validated",
    )
    return sample_import["public_id"]


def _propose_review_execute(assistant: AdminAssistantService, **propose_kwargs):
    proposal = assistant.propose(**propose_kwargs)
    assistant.review(proposal.public_id, decision="approved", reviewed_by=ADMIN_ID, comment=None)
    return assistant.execute(proposal.public_id, executor_public_id=ADMIN_ID)


# -- registry completeness --------------------------------------------------------------


def test_all_16_rag_sandbox_actions_are_registered_and_never_blocked() -> None:
    for action_type in RAG_SANDBOX_ACTION_TYPES:
        assert action_type in ACTION_BY_TYPE
        assert is_blocked_action_type(action_type) is False


def test_all_10_rag_sandbox_tools_are_registered() -> None:
    from backend.services.admin_assistant_tools import TOOL_BY_NAME

    for name in RAG_SANDBOX_TOOL_NAMES:
        assert name in TOOL_BY_NAME


def test_no_rag_sandbox_action_claims_production_activation_or_training_approval() -> None:
    forbidden = (
        "training_approved", "Training Approved", "Production RAG Activated",
        "production_rag_activated", "Model Released",
    )
    for action_type in RAG_SANDBOX_ACTION_TYPES:
        definition = ACTION_BY_TYPE[action_type]
        for language in ("en", "ta"):
            text = definition.summary[language] + definition.confirmation_text[language]
            for phrase in forbidden:
                assert phrase not in text


# -- full propose -> review -> execute pipeline ------------------------------------------


def test_create_rag_sandbox_experiment_through_full_pipeline(settings: Settings) -> None:
    sample_import_public_id = _finalized_sample_import(settings)
    assistant = AdminAssistantService(settings)
    result = _propose_review_execute(
        assistant,
        action_type="create_rag_sandbox_experiment",
        target_type="external_dataset_sample_import",
        target_public_id=sample_import_public_id,
        request_payload={"purpose": "retrieval_validation"},
        requested_by=ADMIN_ID,
        summary="Create a rag sandbox experiment",
    )
    assert result.status == "approved"


def test_create_rag_sandbox_experiment_fails_when_not_eligible(settings: Settings) -> None:
    discovery = ExternalDatasetDiscoveryRepository(settings.resolved_database_path)
    session = discovery.create_session(
        {"session_code": "session-1", "requested_by_admin_public_id": ADMIN_ID}
    )
    candidate = discovery.create_candidate(
        session["public_id"], {"canonical_name": "X", "normalized_name": "x"}
    )
    verification = DatasetVerificationRepository(settings.resolved_database_path)
    case = verification.create_case(
        {
            "candidate_public_id": candidate["public_id"], "verification_code": "VC-1",
            "requested_by_admin_public_id": ADMIN_ID,
        }
    )
    samples = DatasetSampleImportRepository(settings.resolved_database_path)
    sample_import = samples.create_sample_import(
        {
            "sample_import_code": "SI-1", "verification_case_public_id": case["public_id"],
            "candidate_public_id": candidate["public_id"], "purpose": "manual_review",
            "selection_method": "deterministic_first_n", "requested_count": 10,
            "requested_by_admin_public_id": ADMIN_ID,
        }
    )
    assistant = AdminAssistantService(settings)
    with pytest.raises(RagSandboxError):
        _propose_review_execute(
            assistant,
            action_type="create_rag_sandbox_experiment",
            target_type="external_dataset_sample_import",
            target_public_id=sample_import["public_id"],
            request_payload={"purpose": "retrieval_validation"},
            requested_by=ADMIN_ID,
            summary="Create a rag sandbox experiment",
        )


# -- deterministic chat guidance and FAQ --------------------------------------------------


def test_faq_matches_what_is_a_rag_sandbox_question() -> None:
    assert match_rag_sandbox_question("What is a RAG sandbox?") == "what_is_a_rag_sandbox"


def test_faq_matches_why_isolated_question() -> None:
    assert (
        match_rag_sandbox_question("why is it isolated") == "why_is_it_isolated"
    )


def test_faq_returns_none_for_unrelated_message() -> None:
    assert match_rag_sandbox_question("what is the weather today") is None


def test_faq_entries_have_nonempty_tamil_and_english_answers() -> None:
    from core_model.admin_assistant.rag_sandbox_help import RAG_SANDBOX_FAQ

    assert len(RAG_SANDBOX_FAQ) == 12
    for entry in RAG_SANDBOX_FAQ.values():
        assert entry["en"].strip()
        assert entry["ta"].strip()


def test_chat_service_answers_rag_sandbox_guidance_in_tamil(settings: Settings) -> None:
    chat_service = AdminAssistantChatService(settings)
    result = chat_service.send_message(
        admin_id=ADMIN_ID,
        message="இந்த Tamil sample-ஐ rag sandbox-ல் test செய்யலாமா?",
        page_id="overview",
    )
    assert result["status"] == "completed"
    assert result["navigation_target"] == {"page_id": "rag_sandbox", "nav_key": "RAG Sandbox"}
    assert result["answer"].strip()


def test_chat_service_answers_rag_sandbox_faq_in_english(settings: Settings) -> None:
    chat_service = AdminAssistantChatService(settings)
    result = chat_service.send_message(
        admin_id=ADMIN_ID, message="What is a RAG sandbox?", page_id="overview"
    )
    assert result["status"] == "completed"
    assert "isolated" in result["answer"].lower() or "sandbox" in result["answer"].lower()
