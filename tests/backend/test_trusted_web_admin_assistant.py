"""Phase 20 Step 32 -- Admin Assistant integration: 8 read-only tools
(Trusted Web + Deterministic Tools) + 5 low-risk proposal actions, all
flag/record-only -- none of them mutate the checksum-versioned policy
file, toggle a tool's enabled state, enable a paid provider, or enable
external MCP."""

from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.admin import AdminRepository
from backend.database.repositories.trusted_web_tool_gateway import TrustedWebToolGatewayRepository
from backend.models.auth import AdminCreate
from backend.services.admin_assistant_service import AdminAssistantService
from backend.services.admin_assistant_tools import get_tool, run_tool
from core_model.admin_assistant.action_registry import (
    BLOCKED_ACTION_SUBSTRINGS,
    get_action_definition,
    is_known_action_type,
)

READ_ONLY_TOOL_NAMES = (
    "get_trusted_web_overview",
    "get_trusted_web_health",
    "get_web_source_verification_summary",
    "get_web_freshness_summary",
    "get_web_conflict_summary",
    "get_tool_gateway_overview",
    "get_tool_execution_summary",
    "get_mcp_readiness_summary",
)

ACTION_TYPES = (
    "propose_trusted_web_policy_issue",
    "propose_source_block",
    "propose_source_allowlist_review",
    "propose_tool_enablement_review",
    "propose_tool_permission_issue",
)


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
        AdminCreate(username="tw-admin", display_name="TW Admin", password="Password123!")
    )
    return admin.public_id


@pytest.mark.parametrize("name", READ_ONLY_TOOL_NAMES)
def test_all_eight_read_only_tools_are_registered(name: str) -> None:
    assert get_tool(name) is not None


def test_trusted_web_overview_tool_returns_real_data(settings: Settings) -> None:
    result = run_tool("get_trusted_web_overview", settings)
    assert result["available"] is True
    assert result["total_search_events"] == 0
    assert "web_demand" in result


def test_trusted_web_health_tool_never_leaks_api_key(settings: Settings) -> None:
    result = run_tool("get_trusted_web_health", settings)
    assert result["available"] is True
    assert "api_key" not in result
    assert result["external_mcp_enabled"] is False


def test_web_source_verification_summary_tool(settings: Settings) -> None:
    result = run_tool("get_web_source_verification_summary", settings)
    assert result["available"] is True
    assert "by_verification_level" in result


def test_web_freshness_summary_tool(settings: Settings) -> None:
    result = run_tool("get_web_freshness_summary", settings)
    assert result["available"] is True
    assert "by_freshness_status" in result


def test_web_conflict_summary_tool(settings: Settings) -> None:
    result = run_tool("get_web_conflict_summary", settings)
    assert result["available"] is True
    assert "conflicts" in result


def test_tool_gateway_overview_tool(settings: Settings) -> None:
    result = run_tool("get_tool_gateway_overview", settings)
    assert result["available"] is True
    assert result["total_executions"] == 0
    assert result["external_mcp_enabled"] is False


def test_tool_execution_summary_tool(settings: Settings) -> None:
    result = run_tool("get_tool_execution_summary", settings)
    assert result["available"] is True
    assert result["items"] == []


def test_mcp_readiness_summary_tool_proves_external_mcp_empty(settings: Settings) -> None:
    result = run_tool("get_mcp_readiness_summary", settings)
    assert result["available"] is True
    assert result["external_mcp_enabled"] is False
    assert set(result["built_in_deterministic_tools"]) == {
        "calculator",
        "unit_conversion",
        "date_time_arithmetic",
    }
    assert result["internal_service_tools"] == []
    assert result["external_mcp_tools"] == []


@pytest.mark.parametrize("action_type", ACTION_TYPES)
def test_actions_are_known_and_registered(action_type: str) -> None:
    assert is_known_action_type(action_type)
    definition = get_action_definition(action_type)
    assert definition is not None
    assert definition.risk_level == "low"


@pytest.mark.parametrize("action_type", ACTION_TYPES)
def test_actions_are_wired_to_a_real_executor(action_type: str) -> None:
    from backend.services.admin_assistant_service import ACTION_EXECUTORS

    assert action_type in ACTION_EXECUTORS


def test_actions_never_match_blocked_substrings() -> None:
    for action_type in ACTION_TYPES:
        assert not any(token in action_type.lower() for token in BLOCKED_ACTION_SUBSTRINGS)


def test_propose_trusted_web_policy_issue_full_cycle(settings: Settings, admin_id: str) -> None:
    service = AdminAssistantService(settings)
    proposal = service.propose(
        action_type="propose_trusted_web_policy_issue",
        target_type="trusted_web_policy_system",
        target_public_id="system",
        request_payload={
            "comment": "allowed_domains missing an important gov portal",
            "reason": "policy review",
        },
        requested_by=admin_id,
        summary="flag a policy issue",
    )
    service.review(proposal.public_id, decision="approved", reviewed_by=admin_id, comment=None)
    executed = service.execute(proposal.public_id, executor_public_id=admin_id)
    assert executed.status == "approved"

    events = TrustedWebToolGatewayRepository(settings.resolved_database_path).list_policy_events(
        limit=10, offset=0
    )
    assert len(events) == 1
    assert events[0]["event_type"] == "issue_flagged"


def test_propose_source_block_full_cycle_never_edits_policy_file(
    settings: Settings, admin_id: str
) -> None:
    from backend.services.trusted_web_policy_service import compute_policy_checksum, load_policy

    before = load_policy()
    before_checksum = compute_policy_checksum(before)

    service = AdminAssistantService(settings)
    proposal = service.propose(
        action_type="propose_source_block",
        target_type="trusted_web_policy_system",
        target_public_id="system",
        request_payload={
            "domain": "evil-lookalike.example",
            "comment": "phishing lookalike",
            "reason": "suspected phishing lookalike domain",
        },
        requested_by=admin_id,
        summary="propose blocking a domain",
    )
    service.review(proposal.public_id, decision="approved", reviewed_by=admin_id, comment=None)
    executed = service.execute(proposal.public_id, executor_public_id=admin_id)
    assert executed.status == "approved"

    after = load_policy()
    assert compute_policy_checksum(after) == before_checksum

    events = TrustedWebToolGatewayRepository(settings.resolved_database_path).list_policy_events(
        limit=10, offset=0
    )
    assert events[0]["event_type"] == "source_block_proposed"
    assert "evil-lookalike.example" in events[0]["detail"]


def test_propose_source_allowlist_review_full_cycle(settings: Settings, admin_id: str) -> None:
    service = AdminAssistantService(settings)
    proposal = service.propose(
        action_type="propose_source_allowlist_review",
        target_type="trusted_web_policy_system",
        target_public_id="system",
        request_payload={
            "domain": "new-official-source.gov",
            "comment": "should be official",
            "reason": "candidate official source",
        },
        requested_by=admin_id,
        summary="propose allowlist review",
    )
    service.review(proposal.public_id, decision="approved", reviewed_by=admin_id, comment=None)
    executed = service.execute(proposal.public_id, executor_public_id=admin_id)
    assert executed.execution_result["event_type"] == "allowlist_review_proposed"


def test_propose_tool_enablement_review_never_changes_registry(
    settings: Settings, admin_id: str
) -> None:
    from backend.services.deterministic_tool_registry import get_tool_descriptor

    before = get_tool_descriptor("calculator")
    service = AdminAssistantService(settings)
    proposal = service.propose(
        action_type="propose_tool_enablement_review",
        target_type="deterministic_tool_registry_system",
        target_public_id="system",
        request_payload={
            "tool_name": "calculator",
            "comment": "review risk tier",
            "reason": "periodic risk review",
        },
        requested_by=admin_id,
        summary="review tool enablement",
    )
    service.review(proposal.public_id, decision="approved", reviewed_by=admin_id, comment=None)
    executed = service.execute(proposal.public_id, executor_public_id=admin_id)
    assert executed.execution_result["recorded"] is True

    after = get_tool_descriptor("calculator")
    assert before == after  # registry is a fixed code-level constant, untouched


def test_propose_tool_permission_issue_full_cycle(settings: Settings, admin_id: str) -> None:
    service = AdminAssistantService(settings)
    proposal = service.propose(
        action_type="propose_tool_permission_issue",
        target_type="deterministic_tool_registry_system",
        target_public_id="system",
        request_payload={
            "tool_name": "calculator",
            "comment": "risk tier concern",
            "reason": "possible risk tier concern",
        },
        requested_by=admin_id,
        summary="flag a permission issue",
    )
    service.review(proposal.public_id, decision="approved", reviewed_by=admin_id, comment=None)
    executed = service.execute(proposal.public_id, executor_public_id=admin_id)
    assert executed.execution_result["recorded"] is True
    assert executed.execution_result["tool_name"] == "calculator"
