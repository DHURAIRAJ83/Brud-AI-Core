from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.connection import database_connection
from backend.database.migrations import initialize_database
from backend.database.repositories.admin_assistant_context import (
    AdminAssistantContextRepository,
)
from backend.database.repositories.conversation_memory import ConversationMemoryRepository
from backend.models.conversation_memory import MemoryPolicyCreate
from backend.services.admin_assistant_chat_service import AdminAssistantChatService
from backend.services.conversation_session_service import ConversationSessionService

ADMIN_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "chat.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    # `send_message` now resolves the sender's saved response-language
    # preference (Phase 10A), which requires a real `admin_accounts` row
    # -- unlike before, `ADMIN_ID` can no longer be a bare placeholder.
    with database_connection(settings.resolved_database_path) as connection:
        connection.execute(
            "INSERT INTO admin_accounts(public_id, username, display_name, password_hash) "
            "VALUES (?,?,?,?)",
            (ADMIN_ID, "chat-test-admin", "Chat Test Admin", "hash"),
        )
        connection.commit()
    return settings


@pytest.fixture
def service(settings: Settings) -> AdminAssistantChatService:
    return AdminAssistantChatService(settings)


def test_greeting_replies_deterministically_in_english(service: AdminAssistantChatService) -> None:
    result = service.send_message(admin_id=ADMIN_ID, message="Hello", page_id="overview")
    assert result["intent"] == "greeting"
    assert result["language_category"] == "en"
    assert result["status"] == "completed"
    assert "Brud AI Admin Assistant" in result["answer"]
    assert result["conversation_session_public_id"] is None  # no active memory policy yet


def test_greeting_replies_deterministically_in_tamil(service: AdminAssistantChatService) -> None:
    result = service.send_message(admin_id=ADMIN_ID, message="வணக்கம்", page_id="overview")
    assert result["intent"] == "greeting"
    assert result["language_category"] == "ta"
    assert "வணக்கம்" in result["answer"]


def test_help_intent_answers_from_page_registry(service: AdminAssistantChatService) -> None:
    result = service.send_message(
        admin_id=ADMIN_ID, message="How do I use the Datasets page?", page_id="overview"
    )
    assert result["intent"] == "help"
    assert "Datasets" in result["answer"]
    assert result["status"] == "completed"


def test_help_intent_for_unimplemented_page_says_so(service: AdminAssistantChatService) -> None:
    result = service.send_message(
        admin_id=ADMIN_ID, message="Chat Testing", page_id="overview"
    )
    assert result["intent"] == "help"
    assert "not implemented" in result["answer"]


def test_pending_work_intent_uses_dashboard_overview(service: AdminAssistantChatService) -> None:
    result = service.send_message(
        admin_id=ADMIN_ID, message="What is pending?", page_id="overview"
    )
    assert result["intent"] == "pending_work"
    assert result["answer"]


def test_navigation_intent_returns_navigation_target(service: AdminAssistantChatService) -> None:
    result = service.send_message(
        admin_id=ADMIN_ID, message="take me to Builds & Pipelines", page_id="overview"
    )
    assert result["intent"] == "navigation"
    assert result["navigation_target"] == {
        "page_id": "builds_pipelines",
        "nav_key": "Builds & Pipelines",
    }


def test_open_ended_falls_back_to_deterministic_message_when_no_llm_configured(
    service: AdminAssistantChatService,
) -> None:
    result = service.send_message(
        admin_id=ADMIN_ID,
        message="Why did the last evaluation run score lower than expected?",
        page_id="evaluation",
    )
    assert result["intent"] == "open_ended"
    assert result["status"] == "generation_failed"
    assert "unavailable" in result["answer"]


def test_context_snapshot_and_tool_invocation_are_recorded(
    settings: Settings, service: AdminAssistantChatService
) -> None:
    service.send_message(
        admin_id=ADMIN_ID, message="What is pending?", page_id="datasets", tab_id="Records"
    )
    repository = AdminAssistantContextRepository(settings.resolved_database_path)
    snapshots = repository.list_context_snapshots(limit=10)
    assert any(s["page_id"] == "datasets" and s["tab_id"] == "Records" for s in snapshots)

    invocations = repository.list_tool_invocations(limit=10)
    assert any(inv["tool_name"] == "get_dashboard_overview" for inv in invocations)
    assert all(inv["status"] == "succeeded" for inv in invocations)


def _activate_a_memory_policy(settings: Settings) -> str:
    repository = ConversationMemoryRepository(settings.resolved_database_path)
    service = ConversationSessionService(repository, settings)
    policy = service.create_policy(
        MemoryPolicyCreate(
            name="Admin Assistant Test Policy", default_session_mode="session_memory"
        ),
        ADMIN_ID,
    )
    service.validate_policy(policy["public_id"], ADMIN_ID)
    return service.activate_policy(policy["public_id"], ADMIN_ID)["public_id"]


def test_session_and_turns_persist_when_an_active_memory_policy_exists(
    settings: Settings, service: AdminAssistantChatService
) -> None:
    _activate_a_memory_policy(settings)

    first = service.send_message(admin_id=ADMIN_ID, message="Hello", page_id="overview")
    assert first["conversation_session_public_id"] is not None

    second = service.send_message(
        admin_id=ADMIN_ID, message="What is pending?", page_id="overview"
    )
    # The same admin's second message reuses the same active session rather
    # than creating a new one each time.
    assert second["conversation_session_public_id"] == first["conversation_session_public_id"]

    repository = ConversationMemoryRepository(settings.resolved_database_path)
    with repository.transaction() as connection:
        session = repository.session(connection, first["conversation_session_public_id"])
        turns = repository.turns_for_session(connection, session["id"])
    # user + assistant turns for each of the two messages sent above.
    assert len(turns) == 4


def test_conversation_persisted_true_when_a_memory_policy_is_active(
    settings: Settings, service: AdminAssistantChatService
) -> None:
    _activate_a_memory_policy(settings)
    result = service.send_message(admin_id=ADMIN_ID, message="Hello", page_id="overview")
    assert result["conversation_persisted"] is True
    assert result["conversation_session_public_id"] is not None


def test_conversation_persisted_false_when_no_memory_policy_is_active(
    service: AdminAssistantChatService,
) -> None:
    # No _activate_a_memory_policy() call -- this is the default,
    # out-of-the-box state a fresh install starts in.
    result = service.send_message(admin_id=ADMIN_ID, message="Hello", page_id="overview")
    assert result["conversation_persisted"] is False
    assert result["conversation_session_public_id"] is None


def test_secrets_are_never_present_in_recorded_context(
    settings: Settings, service: AdminAssistantChatService
) -> None:
    service.send_message(admin_id=ADMIN_ID, message="Hello", page_id="overview")
    repository = AdminAssistantContextRepository(settings.resolved_database_path)
    snapshots = repository.list_context_snapshots(limit=10)
    for snapshot in snapshots:
        assert "password" not in str(snapshot["sanitized_context"]).lower()


def test_provider_lookup_answers_deterministically_from_the_real_registry(
    service: AdminAssistantChatService,
) -> None:
    result = service.send_message(
        admin_id=ADMIN_ID,
        message="Tell me about the AI4Bharat provider",
        page_id="external_data_providers",
    )
    assert result["intent"] == "open_ended"
    assert result["status"] == "completed"
    assert "AI4Bharat" in result["answer"]
    assert "unverified" in result["answer"]
    assert "never grants a dataset licence" in result["answer"]
    assert "training remains blocked" in result["answer"].lower()


def test_provider_lookup_falls_back_to_llm_unavailable_when_no_provider_matches(
    service: AdminAssistantChatService,
) -> None:
    result = service.send_message(
        admin_id=ADMIN_ID,
        message="Why did the last evaluation run score lower than expected?",
        page_id="evaluation",
    )
    assert result["status"] == "generation_failed"


def test_dataset_discovery_intent_answers_deterministically_without_inventing_a_result(
    service: AdminAssistantChatService,
) -> None:
    result = service.send_message(
        admin_id=ADMIN_ID,
        message="Can you find a dataset for Tamil speech recognition?",
        page_id="dataset_discovery",
    )
    assert result["intent"] == "open_ended"
    assert result["status"] == "completed"
    assert "Dataset Discovery" in result["answer"]
    assert "no dataset licence" in result["answer"].lower() or "dataset licence" in result["answer"]
    assert result["navigation_target"] == {
        "page_id": "dataset_discovery", "nav_key": "Dataset Discovery"
    }


def test_dataset_discovery_intent_matches_mixed_language_message(
    service: AdminAssistantChatService,
) -> None:
    result = service.send_message(
        admin_id=ADMIN_ID,
        message="எனக்கு தமிழ் மொழிக்காக search datasets செய்ய வேண்டும்",
        page_id="dataset_discovery",
    )
    assert result["status"] == "completed"
    assert "Dataset Discovery" in result["answer"]


def test_trusted_web_faq_answers_deterministically_without_an_llm_call(
    service: AdminAssistantChatService,
) -> None:
    result = service.send_message(
        admin_id=ADMIN_ID, message="Why is external MCP disabled?", page_id="trusted_web",
    )
    assert result["status"] == "completed"
    assert "external_mcp_enabled" in result["answer"]
    assert "MCP" in result["answer"]


# -- MB-39: chat -> proposal bridge ------------------------------------------------


def test_actionable_message_creates_a_real_pending_proposal(
    service: AdminAssistantChatService,
) -> None:
    result = service.send_message(
        admin_id=ADMIN_ID,
        message="Please import dataset content from an external provider",
        page_id="overview",
    )
    assert result["proposal"] is not None
    assert result["proposal"]["action_type"] == "register_external_data_provider"
    assert result["proposal"]["status"] == "pending"
    assert result["proposal"]["public_id"]
    assert "proposal" in result["answer"].lower()

    # Real proof this only created a proposal -- it did not execute anything.
    stored = service.assistant.get_proposal(result["proposal"]["public_id"])
    assert stored.status == "pending"
    assert stored.execution_status != "succeeded"
    assert stored.executed_at is None


def test_actionable_message_proposal_is_not_auto_executed(
    service: AdminAssistantChatService,
) -> None:
    result = service.send_message(
        admin_id=ADMIN_ID, message="I'd like to use an external provider", page_id="overview",
    )
    proposal_id = result["proposal"]["public_id"]
    # Confirm the only way execution could occur is a separate, explicit
    # `execute()` call -- send_message() never makes one itself.
    stored = service.assistant.get_proposal(proposal_id)
    assert stored.status == "pending"
    assert stored.execution_status in ("not_applicable", "pending")
    assert stored.executed_at is None
    assert stored.execution_result == {}


def test_dataset_clean_proposes_when_entity_context_matches(
    service: AdminAssistantChatService,
) -> None:
    result = service.send_message(
        admin_id=ADMIN_ID,
        message="Please clean dataset records now",
        page_id="dataset_sample_import",
        entity_type="external_dataset_sample_import",
        entity_public_id="sample-import-123",
    )
    assert result["proposal"] is not None
    assert result["proposal"]["action_type"] == "run_sample_quality_checks"


def test_dataset_clean_falls_back_to_guidance_without_entity_context(
    service: AdminAssistantChatService,
) -> None:
    result = service.send_message(
        admin_id=ADMIN_ID, message="Please clean dataset records now", page_id="overview",
    )
    assert result["proposal"] is None


def test_rag_build_and_rag_evaluate_never_auto_propose(
    service: AdminAssistantChatService,
) -> None:
    # Both real action types need configuration (embedding model, chunking
    # config, or an answer_run_public_id) this bridge is never given --
    # it must decline rather than invent values, and fall back to the
    # existing RAG Sandbox guidance.
    build_result = service.send_message(
        admin_id=ADMIN_ID,
        message="Let's build rag sandbox index for this experiment",
        page_id="rag_sandbox",
    )
    assert build_result["proposal"] is None
    assert build_result["navigation_target"] == {"page_id": "rag_sandbox", "nav_key": "RAG Sandbox"}

    evaluate_result = service.send_message(
        admin_id=ADMIN_ID, message="run a rag test please", page_id="rag_sandbox",
    )
    assert evaluate_result["proposal"] is None


def test_ambiguous_query_never_creates_a_proposal(
    service: AdminAssistantChatService,
) -> None:
    result = service.send_message(
        admin_id=ADMIN_ID, message="What's the weather like today?", page_id="overview",
    )
    assert result["proposal"] is None


def test_blocked_training_intent_never_creates_a_proposal(
    service: AdminAssistantChatService,
) -> None:
    # "clean dataset" alone would match dataset.clean -- the presence of
    # "training" anywhere in the message must still block the proposal.
    result = service.send_message(
        admin_id=ADMIN_ID,
        message="clean dataset and then start training the model",
        page_id="overview",
        entity_type="external_dataset_sample_import",
        entity_public_id="sample-import-123",
    )
    assert result["proposal"] is None


def test_navigation_target_still_works_for_non_actionable_queries(
    service: AdminAssistantChatService,
) -> None:
    # Existing behavior (pre-MB-39) must be completely unaffected.
    result = service.send_message(
        admin_id=ADMIN_ID, message="take me to Builds & Pipelines", page_id="overview",
    )
    assert result["proposal"] is None
    assert result["navigation_target"] == {
        "page_id": "builds_pipelines", "nav_key": "Builds & Pipelines",
    }
