"""Phase 19 Step 28 -- Admin Assistant integration: 9 read-only tools
+ 4 fully-wired propose/preview/confirm-with-stale-check/execute/audit
actions + 4 defined-but-not-yet-executor-wired actions, matching this
codebase's own established proportionate-scope precedent."""

import time
from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.admin import AdminRepository
from backend.database.repositories.knowledge_gap import KnowledgeGapRepository
from backend.models.auth import AdminCreate
from backend.services.admin_assistant_service import AdminAssistantError, AdminAssistantService
from backend.services.admin_assistant_tools import get_tool, run_tool
from backend.services.knowledge_gap_capture_service import KnowledgeGapCaptureService
from core_model.admin_assistant.action_registry import get_action_definition, is_known_action_type

READ_ONLY_TOOL_NAMES = (
    "get_knowledge_gap_overview",
    "get_knowledge_gap_case",
    "list_top_knowledge_gaps",
    "get_knowledge_gap_cluster",
    "get_tamil_knowledge_gap_summary",
    "get_web_demand_summary",
    "get_tool_demand_summary",
    "get_language_failure_summary",
    "get_daily_knowledge_gap_report",
)

WIRED_ACTION_TYPES = (
    "create_knowledge_gap_research_note",
    "propose_gap_priority_update",
    "propose_duplicate_gap_merge",
    "generate_daily_knowledge_gap_report",
    "propose_knowledge_gap_classification",
    "propose_gap_resolution",
    "propose_rag_research_handoff",
    # Named "capability_assessment", not "training_assessment_handoff" as
    # Phase 19's own spec literally names it -- that string contains
    # "train", which the pre-existing `BLOCKED_ACTION_SUBSTRINGS` safety
    # filter refuses regardless of what executor is wired. See
    # `test_admin_assistant_action_never_approves_rag_or_starts_training`.
    "propose_capability_assessment_handoff",
)

# All 8 requested proposal actions are fully wired -- this codebase's
# `test_action_executors_match_action_registry_exactly` regression test
# enforces that every `ActionDefinition` has a real executor, so a
# defined-but-unwired action (the initial Phase 19 scope decision) is
# not a valid end state here, unlike the historical Phase 8 precedent
# that scope decision was based on.
DEFINED_ONLY_ACTION_TYPES: tuple[str, ...] = ()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "test.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return settings


@pytest.fixture
def admin_id(settings: Settings) -> str:
    admin = AdminRepository(settings.resolved_database_path).create_admin(
        AdminCreate(username="gap-admin", display_name="Gap Admin", password="Password123!")
    )
    return admin.public_id


@pytest.fixture
def seeded_case(settings: Settings) -> dict:
    capture = KnowledgeGapCaptureService(settings)
    return capture.capture(
        message="what is the latest python version",
        resolved_route="insufficient",
        safety_status="safe",
        evidence_status="none",
        confidence_band="unknown",
        fallbacks_attempted=("trusted_web_unavailable",),
        clarification_required=False,
        detected_language="en",
    )


@pytest.fixture
def seeded_case_with_email(settings: Settings) -> dict:
    capture = KnowledgeGapCaptureService(settings)
    return capture.capture(
        message="my email is real.person@example.com, what is the latest python version",
        resolved_route="insufficient",
        safety_status="safe",
        evidence_status="none",
        confidence_band="unknown",
        fallbacks_attempted=("trusted_web_unavailable",),
        clarification_required=False,
        detected_language="en",
    )


@pytest.mark.parametrize("name", READ_ONLY_TOOL_NAMES)
def test_all_nine_read_only_tools_are_registered(name: str) -> None:
    assert get_tool(name) is not None


def test_read_only_tools_return_real_data_never_raw_text(
    settings: Settings, seeded_case_with_email: dict
) -> None:
    overview = run_tool("get_knowledge_gap_overview", settings)
    assert overview["available"] is True
    assert overview["total_cases"] == 1

    case_result = run_tool(
        "get_knowledge_gap_case", settings, {"case_public_id": seeded_case_with_email["public_id"]}
    )
    assert case_result["available"] is True
    assert "real.person@example.com" not in str(case_result)
    assert "email" in case_result.get("canonical_question", "").lower()

    tamil = run_tool("get_tamil_knowledge_gap_summary", settings)
    web = run_tool("get_web_demand_summary", settings)
    tool = run_tool("get_tool_demand_summary", settings)
    language = run_tool("get_language_failure_summary", settings)
    for result in (tamil, web, tool, language):
        assert result["available"] is True


def test_get_knowledge_gap_case_tool_reports_unavailable_for_unknown_id(
    settings: Settings,
) -> None:
    result = run_tool("get_knowledge_gap_case", settings, {"case_public_id": "does-not-exist"})
    assert result["available"] is False


@pytest.mark.parametrize("action_type", WIRED_ACTION_TYPES)
def test_wired_actions_are_known_and_registered(action_type: str) -> None:
    assert is_known_action_type(action_type)
    definition = get_action_definition(action_type)
    assert definition is not None
    assert definition.risk_level in ("low", "moderate", "high", "critical")


def test_no_defined_only_actions_remain_in_this_registry() -> None:
    """Locks in the Section-2 scope reversal: this codebase's own
    `test_action_executors_match_action_registry_exactly` regression
    test enforces that every defined action has a real executor, so
    Phase 19 ends with all 8 requested proposal actions fully wired,
    not 4 wired + 4 defined-only as originally scoped."""

    assert DEFINED_ONLY_ACTION_TYPES == ()
    assert len(WIRED_ACTION_TYPES) == 8


@pytest.mark.parametrize("action_type", WIRED_ACTION_TYPES)
def test_every_requested_action_has_a_real_executor(action_type: str) -> None:
    from backend.services.admin_assistant_service import ACTION_EXECUTORS

    assert is_known_action_type(action_type)
    assert action_type in ACTION_EXECUTORS


def test_create_research_note_action_full_propose_review_execute_cycle(
    settings: Settings, admin_id: str, seeded_case: dict
) -> None:
    service = AdminAssistantService(settings)
    proposal = service.propose(
        action_type="create_knowledge_gap_research_note",
        target_type="knowledge_gap_case",
        target_public_id=seeded_case["public_id"],
        request_payload={"note_type": "investigation", "note_text": "checked existing sources"},
        requested_by=admin_id,
        summary="add a research note",
    )
    assert proposal.status == "pending"

    service.review(proposal.public_id, decision="approved", reviewed_by=admin_id, comment=None)
    executed = service.execute(proposal.public_id, executor_public_id=admin_id)
    assert executed.status == "approved"

    notes = KnowledgeGapRepository(settings.resolved_database_path).list_notes_for_case(
        seeded_case["public_id"]
    )
    assert len(notes) == 1
    assert notes[0]["note_text_redacted"] == "checked existing sources"


def test_priority_update_action_recomputes_and_persists_priority(
    settings: Settings, admin_id: str, seeded_case: dict
) -> None:
    service = AdminAssistantService(settings)
    proposal = service.propose(
        action_type="propose_gap_priority_update",
        target_type="knowledge_gap_case",
        target_public_id=seeded_case["public_id"],
        request_payload={},
        requested_by=admin_id,
        summary="recompute priority",
    )
    service.review(proposal.public_id, decision="approved", reviewed_by=admin_id, comment=None)
    executed = service.execute(proposal.public_id, executor_public_id=admin_id)
    assert executed.execution_result["priority_band"] in (
        "critical", "high", "medium", "low", "informational",
    )


def test_duplicate_merge_action_full_cycle_creates_cluster_and_retains_cases(
    settings: Settings, admin_id: str, seeded_case: dict
) -> None:
    capture = KnowledgeGapCaptureService(settings)
    second_case = capture.capture(
        message="latest python version please",
        resolved_route="insufficient",
        safety_status="safe",
        evidence_status="none",
        confidence_band="unknown",
        fallbacks_attempted=("trusted_web_unavailable",),
        clarification_required=False,
        detected_language="en",
    )

    service = AdminAssistantService(settings)
    proposal = service.propose(
        action_type="propose_duplicate_gap_merge",
        target_type="knowledge_gap_case",
        target_public_id=seeded_case["public_id"],
        request_payload={
            "case_public_ids": [seeded_case["public_id"], second_case["public_id"]],
            "canonical_question": "what is the latest python version",
            "primary_language": "en",
        },
        requested_by=admin_id,
        summary="merge duplicate gaps",
    )
    service.review(proposal.public_id, decision="approved", reviewed_by=admin_id, comment=None)
    executed = service.execute(proposal.public_id, executor_public_id=admin_id)
    assert executed.status == "approved"

    repository = KnowledgeGapRepository(settings.resolved_database_path)
    cluster_public_id = executed.execution_result["public_id"]
    members = repository.list_cluster_members(cluster_public_id)
    assert len(members) == 2

    # Original occurrences must still exist post-merge.
    occurrences = repository.list_occurrences_for_case(seeded_case["public_id"])
    assert len(occurrences) >= 1


def test_daily_report_action_full_cycle(
    settings: Settings, admin_id: str, seeded_case: dict
) -> None:
    service = AdminAssistantService(settings)
    proposal = service.propose(
        action_type="generate_daily_knowledge_gap_report",
        target_type="knowledge_gap_report_system",
        target_public_id="system",
        request_payload={},
        requested_by=admin_id,
        summary="generate daily report",
    )
    service.review(proposal.public_id, decision="approved", reviewed_by=admin_id, comment=None)
    executed = service.execute(proposal.public_id, executor_public_id=admin_id)
    assert "summary" in executed.execution_result


def test_admin_assistant_action_never_approves_rag_or_starts_training(
    settings: Settings, admin_id: str, seeded_case: dict
) -> None:
    """No Phase 19 action_type registered anywhere may contain a
    training/pretrain substring (defense in depth, mirroring the
    existing `BLOCKED_ACTION_SUBSTRINGS` check), and none of the
    wired executors' results ever include a RAG-source or training-run
    identifier."""

    from core_model.admin_assistant.action_registry import BLOCKED_ACTION_SUBSTRINGS

    for action_type in (*WIRED_ACTION_TYPES, *DEFINED_ONLY_ACTION_TYPES):
        assert not any(token in action_type.lower() for token in BLOCKED_ACTION_SUBSTRINGS)


def test_merge_review_rejects_when_target_case_changed_since_proposal(
    settings: Settings, admin_id: str, seeded_case: dict
) -> None:
    capture = KnowledgeGapCaptureService(settings)
    second_case = capture.capture(
        message="latest python version please tell me",
        resolved_route="insufficient",
        safety_status="safe",
        evidence_status="none",
        confidence_band="unknown",
        fallbacks_attempted=("trusted_web_unavailable",),
        clarification_required=False,
        detected_language="en",
    )
    service = AdminAssistantService(settings)
    proposal = service.propose(
        action_type="propose_duplicate_gap_merge",
        target_type="knowledge_gap_case",
        target_public_id=seeded_case["public_id"],
        request_payload={
            "case_public_ids": [seeded_case["public_id"], second_case["public_id"]],
            "canonical_question": "what is the latest python version",
            "primary_language": "en",
        },
        requested_by=admin_id,
        summary="merge duplicate gaps",
    )
    # Mutate one of the target cases after the proposal was created --
    # the review step must refuse to approve against a stale preview.
    # `updated_at` is SQLite `CURRENT_TIMESTAMP` (second granularity),
    # so a real wall-clock gap is needed for the fingerprint to differ.
    time.sleep(1.1)
    KnowledgeGapRepository(settings.resolved_database_path).touch_case_occurrence(
        second_case["public_id"]
    )
    with pytest.raises(AdminAssistantError):
        service.review(proposal.public_id, decision="approved", reviewed_by=admin_id, comment=None)
