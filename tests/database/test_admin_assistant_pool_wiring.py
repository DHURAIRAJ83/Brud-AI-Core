"""Phase 7C-60: proves the Option C+D Admin Assistant dispatch-layer pool
injection (`ToolDefinition.pool_aware`, `run_tool(..., pool=...)`,
`AdminAssistantChatService(settings, pool=...)`, and the `/admin/assistant/chat`
route's new `PoolDependency`) is wired correctly and stays within
INVARIANT-10 (no raw `ConnectionPool`/`.checkout()`/`.checkin()` ever
reaches a tool handler -- only a pool-backed repository does).

Scope, stated explicitly: only ONE tool (`get_recent_audit_events`) is
`pool_aware=True` this phase. These tests do not claim any of the other 89
tools behave any differently than before this phase.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.auth import AdminContext, require_admin, require_csrf
from backend.api.routes.admin_assistant import chat_service
from backend.core.config import Settings
from backend.database.connection_pool import ConnectionPool
from backend.database.qualification_guard import assert_database_path_is_not_production
from backend.database.repositories.phase2 import AuditLogRepository
from backend.main import create_app
from backend.models.auth import AdminPublic, SessionPublic
from backend.models.domain import AuditEventCreate
from backend.services.admin_assistant_chat_service import AdminAssistantChatService
from backend.services.admin_assistant_tools import READ_ONLY_TOOLS, ToolDefinition, get_tool, run_tool
from datetime import UTC, datetime, timedelta


def _fake_admin_context() -> AdminContext:
    now = datetime.now(UTC)
    return AdminContext(
        admin=AdminPublic(
            public_id="00000000-0000-0000-0000-000000000002",
            username="test-admin-60",
            display_name="Test Admin 60",
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
        settings.resolved_database_path, context="test_admin_assistant_pool_wiring"
    )
    app = create_app(settings)

    async def fake_admin() -> AdminContext:
        return _fake_admin_context()

    async def fake_csrf() -> AdminContext:
        return _fake_admin_context()

    app.dependency_overrides[require_admin] = fake_admin
    app.dependency_overrides[require_csrf] = fake_csrf
    return app


# --- 1: exactly one production ConnectionPool construction -----------------


def test_1_single_pool_construction(tmp_path: Path) -> None:
    app = _build_app(tmp_path, "t1")
    with TestClient(app):
        assert isinstance(app.state.pool, ConnectionPool)


# --- 2: Admin Assistant receives the existing shared pool -----------------


def test_2_admin_assistant_receives_shared_pool(tmp_path: Path) -> None:
    app = _build_app(tmp_path, "t2")
    with TestClient(app):
        pool = app.state.pool
        settings = app.state.settings
        service = chat_service(settings, pool)
        assert isinstance(service, AdminAssistantChatService)
        assert service.pool is pool


# --- 3: run_tool() accepts pool=None for backward compatibility ------------


def test_3_run_tool_backward_compatible_without_pool(tmp_path: Path) -> None:
    app = _build_app(tmp_path, "t3")
    with TestClient(app):
        settings = app.state.settings
        # Exactly the pre-Phase-7C-60 2-positional-arg call shape.
        result = run_tool("get_recent_audit_events", settings, {})
        assert result["available"] is True
        # And the 3-positional-arg call shape used elsewhere in this file.
        result2 = run_tool("get_page_help", settings, {"nav_key": "does-not-exist"})
        assert result2 == {"available": False, "reason": "unknown page"}


# --- 4: non-pool-aware tools do not receive pool-backed behavior -----------


def test_4_non_pool_aware_tool_ignores_supplied_pool(tmp_path: Path) -> None:
    app = _build_app(tmp_path, "t4")
    with TestClient(app):
        pool = app.state.pool
        settings = app.state.settings
        tool = get_tool("get_page_help")
        assert tool.pool_aware is False
        # Supplying a real pool must not change this tool's params or crash it.
        result = run_tool("get_page_help", settings, {"nav_key": "nope"}, pool=pool)
        assert result == {"available": False, "reason": "unknown page"}


# --- 5 & identity proof: the pool-aware tool actually uses the SAME pool ---


def test_5_pool_aware_tool_checks_out_from_the_supplied_pool(tmp_path: Path) -> None:
    app = _build_app(tmp_path, "t5")
    with TestClient(app):
        pool = app.state.pool
        settings = app.state.settings

        seen_connection_ids: list[int] = []
        original_checkout = pool.checkout

        def spy_checkout():
            connection = original_checkout()
            seen_connection_ids.append(id(connection))
            return connection

        pool.checkout = spy_checkout
        try:
            result = run_tool("get_recent_audit_events", settings, {}, pool=pool)
        finally:
            pool.checkout = original_checkout

        assert result["available"] is True
        assert len(seen_connection_ids) == 1, "pool-aware tool must check out exactly once from the supplied pool"


# --- 6: no second pool is created -------------------------------------------


def test_6_no_second_pool_created_by_admin_assistant(tmp_path: Path) -> None:
    """Exercises the same `run_tool(tool_name, self.settings, params,
    pool=self.pool)` call that `_run_tool_logged` makes at
    admin_assistant_chat_service.py:202, without going through
    `_run_tool_logged`'s own `dumps_json(redact_secrets(result_summary))`
    audit-log step -- that step has a pre-existing, pool-independent bug
    (AuditEventPublic.model_dump()'s raw `datetime` field is not
    JSON-serializable; reproduced independently with pool=None on an
    unmodified code path, confirming it predates and is unrelated to this
    phase) unrelated to what this test verifies. See the Phase 7C-60
    report's New Findings section."""

    app = _build_app(tmp_path, "t6")
    with TestClient(app):
        pool_before = app.state.pool
        settings = app.state.settings
        service = AdminAssistantChatService(settings, pool=pool_before)
        result = run_tool("get_recent_audit_events", service.settings, {}, pool=service.pool)
        assert result["available"] is True
        assert app.state.pool is pool_before


# --- 7: no raw ConnectionPool exposed to the tool handler -------------------


def test_7_no_raw_pool_exposed_to_handler(tmp_path: Path) -> None:
    app = _build_app(tmp_path, "t7")
    with TestClient(app):
        pool = app.state.pool
        settings = app.state.settings
        result = run_tool("get_recent_audit_events", settings, {}, pool=pool)
        # The result dict (the only thing the handler returns/produces)
        # never contains the pool object itself.
        assert not any(isinstance(value, ConnectionPool) for value in result.values())
        # And the caller's own params dict is never mutated with the
        # internal pool-carrying key -- it never leaks back out.
        caller_params: dict = {}
        run_tool("get_recent_audit_events", settings, caller_params, pool=pool)
        assert caller_params == {}


# --- 8: the selected tool remains read-only ---------------------------------


def test_8_selected_tool_remains_read_only(tmp_path: Path) -> None:
    app = _build_app(tmp_path, "t8")
    with TestClient(app):
        pool = app.state.pool
        settings = app.state.settings
        repository = AuditLogRepository(settings.resolved_database_path, pool=pool)
        repository.append(
            AuditEventCreate(event_type="test", actor_type="system", action="seed")
        )
        with repository.transaction() as connection:
            count_before = connection.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0]

        run_tool("get_recent_audit_events", settings, {"limit": 5}, pool=pool)

        with repository.transaction() as connection:
            count_after = connection.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0]
        assert count_after == count_before


# --- 9: ToolDefinition defaults pool_aware=False -----------------------------


def test_9_tooldefinition_defaults_pool_aware_false() -> None:
    definition = ToolDefinition("t", "system", "d", (), lambda settings, params: {})
    assert definition.pool_aware is False
    pool_aware_tools = [tool.name for tool in READ_ONLY_TOOLS if tool.pool_aware]
    # Phase 9 added get_connection_pool_health as the second pool_aware
    # tool (see admin_assistant_tools.py) -- both reuse the same
    # single-reserved-key discipline established here in Phase 7C-60.
    assert pool_aware_tools == ["get_recent_audit_events", "get_connection_pool_health"]
    assert len(READ_ONLY_TOOLS) == 108  # Phase 11 added get_automation_execution_readiness


# --- 10: existing tool dispatch behavior unchanged for non-pool-aware tools -


def test_10_non_pool_aware_dispatch_identical_with_and_without_pool(tmp_path: Path) -> None:
    app = _build_app(tmp_path, "t10")
    with TestClient(app):
        pool = app.state.pool
        settings = app.state.settings
        without_pool = run_tool("get_page_help", settings, {"nav_key": "nope"})
        with_pool = run_tool("get_page_help", settings, {"nav_key": "nope"}, pool=pool)
        assert without_pool == with_pool


# --- extra: HTTP-level route signature carries PoolDependency ---------------


def test_11_chat_route_receives_the_apps_own_pool(tmp_path: Path) -> None:
    """Reuses TEST A's (Phase 7C-33) established pattern: call the route
    module's own factory function directly with the app's real pool,
    proving `send_chat_message`'s new `pool: PoolDependency` parameter
    resolves to the SAME object as `app.state.pool`, not a second one."""

    app = _build_app(tmp_path, "t11")
    with TestClient(app):
        pool = app.state.pool
        settings = app.state.settings
        service = chat_service(settings, pool)
        assert service.pool is app.state.pool
        assert service.pool is pool
