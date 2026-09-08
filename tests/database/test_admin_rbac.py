"""Phase 3: proves the RBAC role/permission layer (`AdminRole`,
`Permission`, `resolve_admin_role`, `permissions_for_role`) integrates
correctly with the Phase 2 `authorize_tool_invocation()`/`run_tool()`
seam, and that the Phase 3 addition (READ_ONLY now requires
`tool.read`) never weakens the Phase 2 guarantee that
WRITE/PROPOSE/ADMIN_APPROVAL_REQUIRED have no execution path through
`run_tool()` -- a permission grant is exactly as incapable of
unlocking them as a bare capability declaration was (INVARIANT 4/5).

No admin role is persisted in the database this phase (no migration
authorized -- see `AdminRole`'s docstring in
`admin_assistant_tool_governance.py`); roles come from
`Settings.admin_role_overrides_map`, exercised here via
`admin_role_overrides` on isolated `Settings` instances only.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.auth import AdminContext, require_admin, require_csrf
from backend.core.config import Settings
from backend.database.qualification_guard import assert_database_path_is_not_production
from backend.database.repositories.admin_assistant_context import (
    AdminAssistantContextRepository,
)
from backend.main import create_app
from backend.models.auth import AdminPublic, SessionPublic
from backend.services.admin_assistant_chat_service import AdminAssistantChatService
from backend.services.admin_assistant_tool_governance import (
    AdminRole,
    Permission,
    ROLE_PERMISSIONS,
    ToolAuthorizationError,
    ToolCapability,
    authorize_tool_invocation,
    permissions_for_role,
    resolve_admin_role,
)
from backend.services.admin_assistant_tools import (
    READ_ONLY_TOOLS,
    TOOL_BY_NAME,
    ToolDefinition,
    run_tool,
)

SUPER_ADMIN_ID = "10000000-0000-0000-0000-000000000001"
UNMAPPED_ADMIN_ID = "20000000-0000-0000-0000-000000000002"  # absent from overrides -> default ADMIN
AUDITOR_ID = "30000000-0000-0000-0000-000000000003"
REVOKED_ID = "40000000-0000-0000-0000-000000000004"  # explicitly overridden to NONE

_OVERRIDES = f"{SUPER_ADMIN_ID}:SUPER_ADMIN,{AUDITOR_ID}:AUDITOR,{REVOKED_ID}:NONE"


def _fake_admin_context(admin_id: str) -> AdminContext:
    now = datetime.now(UTC)
    return AdminContext(
        admin=AdminPublic(
            public_id=admin_id, username=f"rbac-{admin_id[:8]}", display_name="RBAC Test Admin"
        ),
        session=SessionPublic(expires_at=now + timedelta(hours=1), last_used_at=now),
        session_id=1,
        token="test-token",
    )


def _build_app(tmp_path: Path, name: str, *, admin_id: str) -> FastAPI:
    db_dir = tmp_path / name
    settings = Settings(
        database_path=db_dir / "api.db",
        database_backup_dir=db_dir / "backups",
        allowed_data_dir=db_dir,
        allow_external_storage=True,
        log_level="CRITICAL",
        admin_role_overrides=_OVERRIDES,
    )
    assert_database_path_is_not_production(
        settings.resolved_database_path, context="test_admin_rbac"
    )
    app = create_app(settings)

    async def fake_admin() -> AdminContext:
        return _fake_admin_context(admin_id)

    async def fake_csrf() -> AdminContext:
        return _fake_admin_context(admin_id)

    app.dependency_overrides[require_admin] = fake_admin
    app.dependency_overrides[require_csrf] = fake_csrf
    return app


def _noop_handler(settings, params):  # pragma: no cover - only runs when authorized
    del settings, params
    return {"available": True}


# --- 1/2/3: role resolution --------------------------------------------


def test_1_super_admin_role_resolution() -> None:
    overrides = {SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN}
    assert resolve_admin_role(SUPER_ADMIN_ID, overrides) is AdminRole.SUPER_ADMIN


def test_2_admin_role_resolution_is_the_default_for_an_unmapped_id() -> None:
    assert resolve_admin_role(UNMAPPED_ADMIN_ID, {}) is AdminRole.ADMIN
    # admin_id=None resolves the same way -- explicit "admin_id=None
    # behavior" check (Step 11 security review item).
    assert resolve_admin_role(None, {SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN}) is AdminRole.ADMIN


def test_3_auditor_role_resolution() -> None:
    overrides = {AUDITOR_ID: AdminRole.AUDITOR}
    assert resolve_admin_role(AUDITOR_ID, overrides) is AdminRole.AUDITOR


# --- 4/5: permission allow / deny ---------------------------------------


def test_4_permission_allow_super_admin_has_tool_execute() -> None:
    assert Permission.TOOL_EXECUTE in permissions_for_role(AdminRole.SUPER_ADMIN)


def test_5_permission_deny_auditor_lacks_propose_and_execute() -> None:
    perms = permissions_for_role(AdminRole.AUDITOR)
    assert Permission.TOOL_READ in perms
    assert Permission.TOOL_PROPOSE not in perms
    assert Permission.TOOL_EXECUTE not in perms


# --- 6: default-deny for unknown/unmapped permission state --------------


def test_6_default_deny_for_none_role_and_malformed_override_config() -> None:
    assert permissions_for_role(AdminRole.NONE) == frozenset()
    malformed = Settings(
        database_path=Path("/tmp/brud-rbac-test-unused.db"),
        admin_role_overrides=f"{REVOKED_ID}:NOT_A_REAL_ROLE_NAME",
    ).admin_role_overrides_map
    # A config typo fails CLOSED (AdminRole.NONE), never open onto ADMIN.
    assert malformed[REVOKED_ID] is AdminRole.NONE
    assert permissions_for_role(malformed[REVOKED_ID]) == frozenset()


# --- 7/8: READ_ONLY with / without tool.read -----------------------------


def test_7_read_only_with_tool_read_is_allowed() -> None:
    decision = authorize_tool_invocation(
        "x",
        ToolCapability.READ_ONLY,
        admin_id=SUPER_ADMIN_ID,
        permissions=frozenset({Permission.TOOL_READ}),
    )
    assert decision.allowed is True


def test_8_read_only_without_tool_read_is_denied() -> None:
    decision = authorize_tool_invocation(
        "x", ToolCapability.READ_ONLY, admin_id=REVOKED_ID, permissions=frozenset()
    )
    assert decision.allowed is False


# --- 9/10: WRITE / PROPOSE remain governed regardless of permissions ----


@pytest.mark.parametrize(
    "capability",
    [ToolCapability.WRITE, ToolCapability.PROPOSE, ToolCapability.ADMIN_APPROVAL_REQUIRED],
)
def test_9_10_write_and_propose_capabilities_stay_blocked_even_with_full_permissions(
    capability: ToolCapability,
) -> None:
    """A SUPER_ADMIN's full permission set (including tool.execute) must
    not unlock these -- run_tool()'s Phase 2 unconditional rejection for
    non-READ_ONLY/SYSTEM_ONLY capabilities is untouched by Phase 3.
    Mutation stays governed exclusively by
    AdminAssistantService.propose/review/execute (INVARIANT 5)."""

    full_permissions = frozenset(
        {Permission.TOOL_READ, Permission.TOOL_PROPOSE, Permission.TOOL_EXECUTE}
    )
    decision = authorize_tool_invocation(
        "x", capability, admin_id=SUPER_ADMIN_ID, permissions=full_permissions
    )
    assert decision.allowed is False


def test_9b_write_tool_blocked_end_to_end_even_for_super_admin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    synthetic = ToolDefinition(
        "synthetic_rbac_write_tool", "system", "d", (), _noop_handler, capability=ToolCapability.WRITE
    )
    monkeypatch.setitem(TOOL_BY_NAME, synthetic.name, synthetic)
    app = _build_app(tmp_path, "t9b", admin_id=SUPER_ADMIN_ID)
    with TestClient(app):
        settings = app.state.settings
        with pytest.raises(ToolAuthorizationError):
            run_tool(synthetic.name, settings, {}, admin_id=SUPER_ADMIN_ID)


# --- 11: authorization denial is audited ---------------------------------


def test_11_authorization_denial_is_audited(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    synthetic = ToolDefinition(
        "synthetic_revoked_admin_tool", "system", "d", (), _noop_handler
    )  # capability defaults to READ_ONLY
    monkeypatch.setitem(TOOL_BY_NAME, synthetic.name, synthetic)
    app = _build_app(tmp_path, "t11", admin_id=REVOKED_ID)
    with TestClient(app):
        settings = app.state.settings
        service = AdminAssistantChatService(settings)

        with pytest.raises(ToolAuthorizationError):
            service._run_tool_logged(
                synthetic.name,
                mode="system",
                params={},
                admin_id=REVOKED_ID,
                conversation_session_public_id=None,
            )

        context_repo = AdminAssistantContextRepository(settings.resolved_database_path)
        with context_repo.transaction() as connection:
            row = connection.execute(
                "SELECT status, error_code FROM admin_assistant_tool_invocations "
                "WHERE tool_name=?",
                (synthetic.name,),
            ).fetchone()
        assert row["status"] == "denied"
        assert "tool.read" in row["error_code"]


# --- 12: unauthorized handler never executes -----------------------------


def test_12_denied_handler_is_never_invoked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []

    def tracking_handler(settings, params):
        calls.append("ran")
        return {"available": True}

    synthetic = ToolDefinition("synthetic_revoked_tracked_tool", "system", "d", (), tracking_handler)
    monkeypatch.setitem(TOOL_BY_NAME, synthetic.name, synthetic)
    app = _build_app(tmp_path, "t12", admin_id=REVOKED_ID)
    with TestClient(app):
        settings = app.state.settings
        with pytest.raises(ToolAuthorizationError):
            run_tool(synthetic.name, settings, {}, admin_id=REVOKED_ID)
    assert calls == []


# --- 13/14: existing registry and pool-aware tool remain intact ---------


def test_13_existing_90_tool_registry_remains_intact() -> None:
    assert len(READ_ONLY_TOOLS) == 108  # Phase 11 added get_automation_execution_readiness
    for tool in READ_ONLY_TOOLS:
        assert tool.capability is ToolCapability.READ_ONLY


def test_14_pool_aware_tool_still_functional_for_a_permitted_role(tmp_path: Path) -> None:
    app = _build_app(tmp_path, "t14", admin_id=SUPER_ADMIN_ID)
    with TestClient(app):
        settings = app.state.settings
        pool = app.state.pool
        result = run_tool(
            "get_recent_audit_events", settings, {}, pool=pool, admin_id=SUPER_ADMIN_ID
        )
        assert result["available"] is True


def test_14b_pool_aware_tool_denied_for_revoked_role(tmp_path: Path) -> None:
    app = _build_app(tmp_path, "t14b", admin_id=REVOKED_ID)
    with TestClient(app):
        settings = app.state.settings
        pool = app.state.pool
        with pytest.raises(ToolAuthorizationError):
            run_tool("get_recent_audit_events", settings, {}, pool=pool, admin_id=REVOKED_ID)


# --- security review: direct run_tool() bypass, capability/permission ---
# confusion, raw pool exposure through the RBAC layer -------------------


def test_role_permission_resolution_never_touches_pool_or_connection() -> None:
    """resolve_admin_role/permissions_for_role take only plain strings
    and a plain mapping -- there is no code path by which a
    ConnectionPool or sqlite3.Connection could reach either function
    (INVARIANT 9)."""

    import inspect

    for fn in (resolve_admin_role, permissions_for_role):
        params = inspect.signature(fn).parameters
        for name, param in params.items():
            annotation = str(param.annotation)
            assert "Pool" not in annotation and "Connection" not in annotation


def test_capability_and_permission_are_distinct_and_both_required() -> None:
    """A tool that is READ_ONLY but whose caller lacks tool.read is
    denied (capability alone is not enough); a caller with tool.read
    invoking a WRITE tool is also denied (permission alone is not
    enough either) -- proving neither dimension alone determines the
    outcome (INVARIANT 3)."""

    read_only_no_perm = authorize_tool_invocation(
        "x", ToolCapability.READ_ONLY, admin_id="a", permissions=frozenset()
    )
    assert read_only_no_perm.allowed is False

    write_full_perm = authorize_tool_invocation(
        "x",
        ToolCapability.WRITE,
        admin_id="a",
        permissions=frozenset({Permission.TOOL_READ, Permission.TOOL_PROPOSE, Permission.TOOL_EXECUTE}),
    )
    assert write_full_perm.allowed is False


def test_every_admin_role_has_an_explicit_permission_mapping() -> None:
    for role in AdminRole:
        assert role in ROLE_PERMISSIONS
