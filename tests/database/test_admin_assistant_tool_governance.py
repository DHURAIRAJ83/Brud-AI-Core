"""Phase 2: proves the Admin Assistant tool capability/authorization layer
(`ToolCapability`, `authorize_tool_invocation`, `ToolDefinition.capability`,
and the check `run_tool()` performs before every dispatch) is wired
correctly and preserves the invariant that a tool's declared capability
never by itself grants authorization to execute.

Scope, stated explicitly: this phase adds the capability field and the
authorization decision point. No tool other than the pre-existing 90
`READ_ONLY` tools has a wired execution path yet -- `WRITE`,
`PROPOSE`, and `ADMIN_APPROVAL_REQUIRED` are declared capabilities with
no execution path through `run_tool()` in this phase; mutations remain
governed exclusively by `AdminAssistantService.propose/review/execute`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.auth import AdminContext, require_admin, require_csrf
from backend.core.config import Settings
from backend.database.qualification_guard import assert_database_path_is_not_production
from backend.database.repositories.phase2 import AuditLogRepository
from backend.main import create_app
from backend.models.auth import AdminPublic, SessionPublic
from backend.models.domain import AuditEventCreate
from backend.services.admin_assistant_chat_service import AdminAssistantChatService
from backend.services.admin_assistant_tool_governance import (
    AuthorizationDecision,
    ToolAuthorizationError,
    ToolCapability,
    authorize_tool_invocation,
)
from backend.services.admin_assistant_tools import (
    READ_ONLY_TOOLS,
    TOOL_BY_NAME,
    ToolDefinition,
    get_tool,
    run_tool,
)
from datetime import UTC, datetime, timedelta


def _fake_admin_context() -> AdminContext:
    now = datetime.now(UTC)
    return AdminContext(
        admin=AdminPublic(
            public_id="00000000-0000-0000-0000-000000000032",
            username="test-admin-governance",
            display_name="Test Admin Governance",
        ),
        session=SessionPublic(expires_at=now + timedelta(hours=1), last_used_at=now),
        session_id=1,
        token="test-token",
    )


def _build_app(tmp_path: Path, name: str) -> FastAPI:
    db_dir = tmp_path / name
    settings = Settings(
        database_path=db_dir / "api.db",
        database_backup_dir=db_dir / "backups",
        allowed_data_dir=db_dir,
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    assert_database_path_is_not_production(
        settings.resolved_database_path, context="test_admin_assistant_tool_governance"
    )
    app = create_app(settings)

    async def fake_admin() -> AdminContext:
        return _fake_admin_context()

    async def fake_csrf() -> AdminContext:
        return _fake_admin_context()

    app.dependency_overrides[require_admin] = fake_admin
    app.dependency_overrides[require_csrf] = fake_csrf
    return app


def _noop_handler(settings, params):  # pragma: no cover - never expected to run
    del settings, params
    return {"available": True, "mutated": True}


# --- 1: every pre-Phase-2 tool stays compatible -----------------------------


def test_1_all_90_tools_default_to_read_only_capability() -> None:
    assert len(READ_ONLY_TOOLS) == 108  # Phase 11 added get_automation_execution_readiness
    for tool in READ_ONLY_TOOLS:
        assert tool.capability is ToolCapability.READ_ONLY


# --- 2: capability metadata is present and explicit -------------------------


def test_2_tooldefinition_exposes_capability_metadata() -> None:
    definition = ToolDefinition("t", "system", "d", (), _noop_handler)
    assert definition.capability is ToolCapability.READ_ONLY  # default, unspecified
    explicit = ToolDefinition(
        "t2", "system", "d", (), _noop_handler, capability=ToolCapability.WRITE
    )
    assert explicit.capability is ToolCapability.WRITE
    assert {c.value for c in ToolCapability} == {
        "read_only",
        "write",
        "propose",
        "admin_approval_required",
        "system_only",
    }


# --- 3: READ_ONLY executes automatically, no admin_id required --------------


def test_3_read_only_tool_executes_without_admin_id(tmp_path: Path) -> None:
    app = _build_app(tmp_path, "t3")
    with TestClient(app):
        settings = app.state.settings
        result = run_tool("get_dashboard_overview", settings, {})
        assert result["summary"] is not None


# --- 4/5/6/7/8: non-READ_ONLY capabilities never execute through run_tool ---


@pytest.mark.parametrize(
    "capability",
    [
        ToolCapability.WRITE,
        ToolCapability.PROPOSE,
        ToolCapability.ADMIN_APPROVAL_REQUIRED,
    ],
)
def test_4_5_write_propose_admin_approval_cannot_bypass_governance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capability: ToolCapability
) -> None:
    """WRITE/PROPOSE/ADMIN_APPROVAL_REQUIRED tools are unconditionally
    rejected by run_tool() -- with or without an admin_id, and
    regardless of how "trusted" that admin_id looks. This is
    INVARIANT: capability != authorization (item 7) applied
    concretely: declaring the capability is not itself a grant."""

    synthetic = ToolDefinition(
        "synthetic_governed_tool", "system", "d", (), _noop_handler, capability=capability
    )
    monkeypatch.setitem(TOOL_BY_NAME, synthetic.name, synthetic)
    app = _build_app(tmp_path, f"t4_{capability.value}")
    with TestClient(app):
        settings = app.state.settings
        for admin_id in (None, "some-admin-public-id", "trusted-super-admin"):
            with pytest.raises(ToolAuthorizationError):
                run_tool(synthetic.name, settings, {}, admin_id=admin_id)


def test_6_system_only_rejects_unauthorized_and_accepts_authorized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    synthetic = ToolDefinition(
        "synthetic_system_only_tool",
        "system",
        "d",
        (),
        _noop_handler,
        capability=ToolCapability.SYSTEM_ONLY,
    )
    monkeypatch.setitem(TOOL_BY_NAME, synthetic.name, synthetic)
    app = _build_app(tmp_path, "t6")
    with TestClient(app):
        settings = app.state.settings
        with pytest.raises(ToolAuthorizationError):
            run_tool(synthetic.name, settings, {})
        with pytest.raises(ToolAuthorizationError):
            run_tool(synthetic.name, settings, {}, admin_id="some-admin")
        result = run_tool(synthetic.name, settings, {}, system_authorized=True)
        assert result["available"] is True


def test_7_capability_alone_never_grants_authorization() -> None:
    """Direct unit-level proof of the invariant: for every non-READ_ONLY,
    non-SYSTEM_ONLY capability, the decision is False regardless of
    admin_id -- capability is a description of what a tool CAN do, not
    a grant of what it MAY do."""

    for capability in (
        ToolCapability.WRITE,
        ToolCapability.PROPOSE,
        ToolCapability.ADMIN_APPROVAL_REQUIRED,
    ):
        for admin_id in (None, "admin-1", "root"):
            decision = authorize_tool_invocation(
                "x", capability, admin_id=admin_id, system_authorized=False
            )
            assert isinstance(decision, AuthorizationDecision)
            assert decision.allowed is False


def test_8_unauthorized_invocation_raises_before_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The handler itself must never run for a denied invocation."""

    calls: list[str] = []

    def tracking_handler(settings, params):
        calls.append("ran")
        return {"available": True}

    synthetic = ToolDefinition(
        "synthetic_tracked_write_tool",
        "system",
        "d",
        (),
        tracking_handler,
        capability=ToolCapability.WRITE,
    )
    monkeypatch.setitem(TOOL_BY_NAME, synthetic.name, synthetic)
    app = _build_app(tmp_path, "t8")
    with TestClient(app):
        settings = app.state.settings
        with pytest.raises(ToolAuthorizationError):
            run_tool(synthetic.name, settings, {})
    assert calls == []


# --- 9: every governance decision is auditable -------------------------------


def test_9_denied_and_succeeded_invocations_are_both_audited(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    synthetic = ToolDefinition(
        "synthetic_audited_write_tool",
        "system",
        "d",
        (),
        _noop_handler,
        capability=ToolCapability.WRITE,
    )
    monkeypatch.setitem(TOOL_BY_NAME, synthetic.name, synthetic)
    app = _build_app(tmp_path, "t9")
    with TestClient(app):
        settings = app.state.settings
        service = AdminAssistantChatService(settings)

        with pytest.raises(ToolAuthorizationError) as excinfo:
            service._run_tool_logged(
                synthetic.name,
                mode="system",
                params={},
                admin_id="test-admin",
                conversation_session_public_id=None,
            )

        result = service._run_tool_logged(
            "get_dashboard_overview",
            mode="guide",
            params={},
            admin_id="test-admin",
            conversation_session_public_id=None,
        )
        assert result["summary"] is not None

        from backend.database.repositories.admin_assistant_context import (
            AdminAssistantContextRepository,
        )

        context_repo = AdminAssistantContextRepository(settings.resolved_database_path)
        with context_repo.transaction() as connection:
            rows = connection.execute(
                "SELECT tool_name, status, error_code FROM admin_assistant_tool_invocations "
                "ORDER BY id"
            ).fetchall()
        by_tool = {row["tool_name"]: row for row in rows}
        assert by_tool[synthetic.name]["status"] == "denied"
        assert str(excinfo.value) in by_tool[synthetic.name]["error_code"]
        assert by_tool["get_dashboard_overview"]["status"] == "succeeded"


# --- 10: datetime serialization regression -----------------------------------


def test_10_recent_audit_events_datetime_no_longer_raises_through_chat_service(
    tmp_path: Path,
) -> None:
    app = _build_app(tmp_path, "t10")
    with TestClient(app):
        settings = app.state.settings
        pool = app.state.pool
        AuditLogRepository(settings.resolved_database_path, pool=pool).append(
            AuditEventCreate(event_type="test", actor_type="system", action="seed")
        )
        service = AdminAssistantChatService(settings, pool=pool)
        result = service._run_tool_logged(
            "get_recent_audit_events",
            mode="system",
            params={},
            admin_id="test-admin",
            conversation_session_public_id=None,
        )
        assert result["available"] is True
        assert len(result["items"]) >= 1
        created_at = result["items"][0]["created_at"]
        assert isinstance(created_at, str)
        # ISO-8601 -- proves this is JSON-safe, not a raw datetime object.
        datetime.fromisoformat(created_at.replace("Z", "+00:00"))


# --- 11: pool-aware get_recent_audit_events remains functional --------------


def test_11_pool_aware_tool_still_functional_with_capability_check(tmp_path: Path) -> None:
    app = _build_app(tmp_path, "t11")
    with TestClient(app):
        settings = app.state.settings
        pool = app.state.pool
        result = run_tool(
            "get_recent_audit_events", settings, {}, pool=pool, admin_id="test-admin"
        )
        assert result["available"] is True


# --- 12: non-pool-aware tools remain unaffected ------------------------------


def test_12_non_pool_aware_tool_unaffected_by_governance_layer(tmp_path: Path) -> None:
    app = _build_app(tmp_path, "t12")
    with TestClient(app):
        settings = app.state.settings
        without_admin = run_tool("get_page_help", settings, {"nav_key": "nope"})
        with_admin = run_tool(
            "get_page_help", settings, {"nav_key": "nope"}, admin_id="test-admin"
        )
        assert without_admin == with_admin


def test_get_tool_still_returns_capability_for_every_tool() -> None:
    for tool in READ_ONLY_TOOLS:
        assert get_tool(tool.name) is tool
        assert isinstance(tool.capability, ToolCapability)
