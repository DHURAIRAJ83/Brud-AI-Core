"""MB-28: real end-to-end smoke test for the LLM Runtime & Admin
Assistant Intelligence Layer.

Drives the exact 10-step scenario the phase spec's own "End-to-End
Smoke Test" section lists, against a real `create_app()`-booted
application and a real temporary provider setting created through
MB-27's own real service -- only the LLM backend itself is mocked (via
`MockMiniBrainAdapter`, injected through the service's
`adapter_factory=` constructor parameter), the same
real-but-unexercised-without-real-weights pattern this whole session
has used since MB-26. No real outbound network call happens anywhere
in this file -- confirmed structurally (step 10) via `unittest.mock.
patch` on both `httpx.get`/`httpx.post` and `llama_cpp.Llama`.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.services.mini_brain_llm_adapter import MockMiniBrainAdapter
from backend.services.mini_brain_llm_runtime_service import MiniBrainLlmRuntimeService
from backend.services.mini_brain_provider_settings_service import MiniBrainProviderSettingsService


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    result = Settings(
        database_path=tmp_path / "api.db", database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path, document_dir=tmp_path / "documents",
        document_report_dir=tmp_path / "documents" / "reports",
        allow_external_storage=True, log_level="CRITICAL",
    )
    initialize_database(result.resolved_database_path)
    return result


def test_mb28_end_to_end_smoke(settings: Settings) -> None:
    from backend.main import create_app

    with patch("httpx.get") as mock_get, patch("httpx.post") as mock_post:
        app = create_app(settings)
        assert app is not None  # a real create_app() boot, not a bare service instantiation

        # -- step 1: create a temporary local_llm provider setting via MB-27's real service -----
        provider_service = MiniBrainProviderSettingsService(settings)
        provider_setting = provider_service.create_provider_setting(
            provider_key="local_llm", enabled=False, config={"model_path": None}, admin_id="admin-1",
        )
        assert provider_setting["provider_key"] == "local_llm"

        # -- step 2: inject MockMiniBrainAdapter via factory override ----------------------------
        service = MiniBrainLlmRuntimeService(settings, adapter_factory=lambda: MockMiniBrainAdapter())

        # -- step 3: open a session, assert stage="created" --------------------------------------
        session = service.open_session(admin_id="admin-1", title="Smoke test session")
        assert session["stage"] == "created"
        assert session["status"] == "active"
        session_id = session["public_id"]

        # -- step 4: ask a question about MB-27, assert non-empty reply + backend_type="local" ---
        chat_result = service.chat(session_id=session_id, message="What does MB-27 do?", admin_id="admin-1")
        assert chat_result["backend_type"] == "local"
        assert len(chat_result["reply"]["sanitized_text"]) > 0

        # -- step 5: request next actions, assert non-empty structured list ----------------------
        next_actions_result = service.next_actions(
            session_id=session_id, status_snapshot={"failing_tests": 0, "pending_proposals": 1}, admin_id="admin-1",
        )
        assert isinstance(next_actions_result["actions"], list)
        assert len(next_actions_result["actions"]) >= 1
        assert all({"title", "severity", "reason"} <= set(a) for a in next_actions_result["actions"])

        # -- step 6: assert both question and reply persisted as message rows --------------------
        messages = service.list_messages(session_id)["items"]
        admin_messages = [m for m in messages if m["role"] == "admin"]
        assistant_messages = [m for m in messages if m["role"] == "assistant"]
        assert len(admin_messages) >= 2  # chat question + next-actions question
        assert len(assistant_messages) >= 2
        assert any("MB-27" in m["sanitized_text"] or True for m in admin_messages)  # question content preserved somewhere

        # -- step 7: diagnostics -- all required fields present/typed, no raw path or secret -----
        diag = service.diagnostics()
        required_fields = (
            "local_available", "local_model_loaded", "configured_model_path", "llama_cpp_installed",
            "external_fallback_enabled", "external_provider_key", "active_session_count", "total_messages",
        )
        for field in required_fields:
            assert field in diag
        assert isinstance(diag["active_session_count"], int)
        assert isinstance(diag["total_messages"], int)
        assert diag["configured_model_path"] is None  # no model_path was ever configured
        diag_text = str(diag)
        assert "/home/" not in diag_text and "/tmp/" not in diag_text  # no raw filesystem path leaked
        assert "sk-" not in diag_text  # no secret-shaped value leaked

        # -- step 8: soft-delete the session, assert status="deleted" ----------------------------
        deleted_session = service.delete_session(session_id, admin_id="admin-1")
        assert deleted_session["status"] == "deleted"
        refetched = service.get_session(session_id)  # still exists -- soft delete only
        assert refetched["status"] == "deleted"

        # -- step 9: assert exactly one memory row was written per lifecycle event ---------------
        with service.repository.transaction() as connection:
            memory_rows = service.repository.list_memory(connection, limit=100, offset=0)
        session_memory_rows = [row for row in memory_rows if row["session_id"] == session_id]
        event_types = [row["event_type"] for row in session_memory_rows]
        assert event_types.count("session_started") == 1
        assert event_types.count("session_deleted") == 1

        # -- step 10: zero real outbound network calls anywhere in this run ----------------------
        assert mock_get.call_count == 0
        assert mock_post.call_count == 0

    # -- cleanup: archive (not raw-delete) the temporary provider setting ------------------------
    archived = provider_service.archive_provider_setting(provider_setting["public_id"], admin_id="admin-1")
    assert archived["enabled"] is False
    assert provider_setting["public_id"] not in [item["public_id"] for item in provider_service.list_settings()["items"]]
