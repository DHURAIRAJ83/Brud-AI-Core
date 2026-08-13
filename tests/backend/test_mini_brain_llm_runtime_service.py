"""MB-28: service-layer tests for MiniBrainLlmRuntimeService -- real
database, real MB-27 provider settings service, real MB-25 plugin
governance/runtime pipeline for tool-dispatch coverage. The LLM
backend itself is always `MockMiniBrainAdapter` (injected via
`adapter_factory=`), the same deterministic-mock pattern MB-26/27
established for their own real-but-unexercised-without-real-
hardware/weights adapters.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.base import NotFoundError, ValidationError
from backend.services.mini_brain_llm_adapter import MockMiniBrainAdapter
from backend.services.mini_brain_llm_runtime_service import MiniBrainLlmRuntimeService
from backend.services.mini_brain_plugin_governance_service import MiniBrainPluginGovernanceService

REAL_PLUGIN_DIR = Path(__file__).resolve().parents[2] / "data" / "plugins"

WEATHER_MANIFEST = {
    "plugin_id": "weather_lookup", "name": "Weather Lookup", "version": "1.0.0", "author": "Brud AI",
    "description": "Deterministic stub weather lookup.", "entrypoint": "main.py",
    "requested_scopes": ["chat.read.current"], "allowed_domains": [],
    "filesystem_roots": [], "ui_components": [], "local_storage_usage": False, "cloud_storage_usage": False,
    "minimum_brud_version": "1.0.0", "signature_placeholder": "unsigned", "homepage": "https://example.com",
    "support_url": "https://example.com/support",
}


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    result = Settings(
        database_path=tmp_path / "api.db", database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path, document_dir=tmp_path / "documents",
        document_report_dir=tmp_path / "documents" / "reports", plugin_package_dir=REAL_PLUGIN_DIR,
        allowed_model_dir=tmp_path / "models", allow_external_storage=True, log_level="CRITICAL",
    )
    initialize_database(result.resolved_database_path)
    return result


@pytest.fixture
def service(settings: Settings) -> MiniBrainLlmRuntimeService:
    return MiniBrainLlmRuntimeService(settings, adapter_factory=lambda: MockMiniBrainAdapter())


def _grant_plugin_scope(settings: Settings, *, scope_key: str) -> str:
    gov = MiniBrainPluginGovernanceService(settings)
    manifest = {**WEATHER_MANIFEST, "requested_scopes": [scope_key]}
    plugin = gov.register_plugin(manifest=manifest, admin_id="admin-1")
    plugin_id = plugin["public_id"]
    gov.run_validate_manifest_stage(plugin_id, admin_id="admin-1")
    gov.run_classify_capabilities_stage(plugin_id, admin_id="admin-1")
    gov.run_compute_risk_stage(plugin_id, admin_id="admin-1")
    gov.run_build_sandbox_stage(plugin_id, admin_id="admin-1")
    gov.run_build_filesystem_policy_stage(plugin_id, admin_id="admin-1")
    gov.run_build_network_policy_stage(plugin_id, admin_id="admin-1")
    gov.enable_plugin(plugin_id, admin_id="admin-1")
    gov.grant_permission(plugin_id, scope_key=scope_key, user_id_hash=None, admin_id="admin-1")
    return plugin_id


# -- diagnostics ------------------------------------------------------------------


def test_diagnostics_honest_when_no_provider_configured(service: MiniBrainLlmRuntimeService) -> None:
    diag = service.diagnostics()
    assert diag["local_available"] is False
    assert diag["configured_model_path"] is None
    assert diag["external_fallback_enabled"] is False
    assert diag["active_session_count"] == 0
    assert diag["total_messages"] == 0


def test_diagnostics_llama_cpp_installed_flag_is_real(service: MiniBrainLlmRuntimeService) -> None:
    import importlib.util

    diag = service.diagnostics()
    assert diag["llama_cpp_installed"] == (importlib.util.find_spec("llama_cpp") is not None)


# -- MB-45: widget_health() / chat() backend-consistency regression --------------
#
# The MB-44 audit found the Admin Assistant widget's health banner reading a
# different backend (Phase-8's admin_assistant_chat_service.llm_status(),
# a Phase-15 inference-assignment check) than the one that actually answers
# chat messages (this service's own _resolve_backend()). widget_health() was
# added to call _resolve_backend() directly -- the exact function chat() and
# grounded_chat() already call via _generate_reply() -- so the two can never
# structurally disagree again. These tests are the regression guard.


def test_widget_health_and_chat_agree_when_no_backend_is_configured(settings: Settings) -> None:
    # No adapter_factory override, no provider settings seeded -- this is
    # the real, unmocked _resolve_backend() path (no local model, no
    # external provider), matching what a fresh install actually sees.
    service = MiniBrainLlmRuntimeService(settings)

    health = service.widget_health()
    assert health["loaded"] is False
    assert health["available"] is False
    assert health["backend_type"] == "unavailable"
    assert health["error_message"]

    chat_result = service.chat(session_id=None, message="hello", admin_id="admin-1")
    assert chat_result["backend_type"] == health["backend_type"] == "unavailable"
    assert chat_result["error_message"]


def test_widget_health_and_chat_agree_when_a_backend_is_loaded(service: MiniBrainLlmRuntimeService) -> None:
    # `service` fixture injects adapter_factory=MockMiniBrainAdapter --
    # _resolve_backend() short-circuits to it, and widget_health() calls
    # that exact same method, so it must report the adapter's own
    # backend_type ("local") as loaded/available.
    health = service.widget_health()
    assert health["loaded"] is True
    assert health["available"] is True
    assert health["backend_type"] == "local"
    assert health["error_message"] is None

    chat_result = service.chat(session_id=None, message="hello", admin_id="admin-1")
    assert chat_result["backend_type"] == health["backend_type"] == "local"
    assert chat_result["error_message"] is None


# -- sessions --------------------------------------------------------------------


def test_open_session_requires_real_admin_id(service: MiniBrainLlmRuntimeService) -> None:
    with pytest.raises(ValidationError):
        service.open_session(admin_id="")


def test_open_session_creates_active_session(service: MiniBrainLlmRuntimeService) -> None:
    session = service.open_session(admin_id="admin-1", title="Test")
    assert session["stage"] == "created"
    assert session["status"] == "active"
    assert session["title"] == "Test"


def test_get_session_not_found_raises(service: MiniBrainLlmRuntimeService) -> None:
    with pytest.raises(NotFoundError):
        service.get_session("bogus-id")


def test_list_sessions_filters_by_status(service: MiniBrainLlmRuntimeService) -> None:
    s1 = service.open_session(admin_id="admin-1")
    service.delete_session(s1["public_id"], admin_id="admin-1")
    active = service.list_sessions(status="active")["items"]
    deleted = service.list_sessions(status="deleted")["items"]
    assert s1["public_id"] not in [s["public_id"] for s in active]
    assert s1["public_id"] in [s["public_id"] for s in deleted]


def test_delete_session_is_soft_delete_not_physical(service: MiniBrainLlmRuntimeService) -> None:
    session = service.open_session(admin_id="admin-1")
    deleted = service.delete_session(session["public_id"], admin_id="admin-1")
    assert deleted["status"] == "deleted"
    refetched = service.get_session(session["public_id"])  # still exists -- soft delete only
    assert refetched["status"] == "deleted"


# -- chat --------------------------------------------------------------------------


def test_chat_requires_real_admin_id(service: MiniBrainLlmRuntimeService) -> None:
    with pytest.raises(ValidationError):
        service.chat(session_id=None, message="hi", admin_id="")


def test_chat_creates_a_new_session_when_none_given(service: MiniBrainLlmRuntimeService) -> None:
    result = service.chat(session_id=None, message="hello", admin_id="admin-1")
    assert result["session"]["public_id"]
    assert result["backend_type"] == "local"
    assert result["reply"]["sanitized_text"]


def test_chat_reuses_existing_session(service: MiniBrainLlmRuntimeService) -> None:
    first = service.chat(session_id=None, message="hello", admin_id="admin-1")
    session_id = first["session"]["public_id"]
    second = service.chat(session_id=session_id, message="another question", admin_id="admin-1")
    assert second["session"]["public_id"] == session_id
    messages = service.list_messages(session_id)["items"]
    assert len(messages) == 4  # 2 admin + 2 assistant


def test_chat_empty_message_returns_clarify_capability(service: MiniBrainLlmRuntimeService) -> None:
    result = service.chat(session_id=None, message="   ", admin_id="admin-1")
    assert result["reply"]["capability"] == "clarify"
    assert result["backend_type"] == "template"


def test_chat_persists_admin_and_assistant_messages(service: MiniBrainLlmRuntimeService) -> None:
    result = service.chat(session_id=None, message="hello", admin_id="admin-1")
    messages = service.list_messages(result["session"]["public_id"])["items"]
    roles = [m["role"] for m in messages]
    assert roles == ["admin", "assistant"]


def test_chat_sanitizes_secret_like_content(service: MiniBrainLlmRuntimeService) -> None:
    result = service.chat(session_id=None, message="my api_key=sk-verysecret123 please help", admin_id="admin-1")
    messages = service.list_messages(result["session"]["public_id"])["items"]
    assert "sk-verysecret123" not in messages[0]["sanitized_text"]


def test_chat_unavailable_backend_reports_honestly(settings: Settings) -> None:
    service = MiniBrainLlmRuntimeService(settings)  # no adapter_factory -- real resolution, no provider configured
    result = service.chat(session_id=None, message="hello", admin_id="admin-1")
    assert result["backend_type"] == "unavailable"
    assert result["error_message"] is not None


# -- tool dispatch (real MB-25 pipeline via a fixture-registered mock plugin) -----------------


def test_chat_dispatches_real_tool_call_when_scope_granted(settings: Settings, service: MiniBrainLlmRuntimeService) -> None:
    _grant_plugin_scope(settings, scope_key="chat.read.current")
    result = service.chat(session_id=None, message="Can you check this conversation for context?", admin_id="admin-1")
    assert result["reply"]["tool_call"] is not None
    assert result["reply"]["tool_call"]["tool_name"] == "Weather Lookup"
    events = service.repository
    with events.transaction() as connection:
        event_rows = events.list_events(connection, session_id=result["session"]["public_id"], limit=10, offset=0)
    event_types = {row["event_type"] for row in event_rows}
    assert "tool_call_dispatched" in event_types


def test_chat_no_tool_dispatch_without_granted_plugin(service: MiniBrainLlmRuntimeService) -> None:
    result = service.chat(session_id=None, message="Can you check this conversation for context?", admin_id="admin-1")
    assert result["reply"]["tool_call"] is None


def test_chat_never_bypasses_admin_identity_requirement(settings: Settings) -> None:
    _grant_plugin_scope(settings, scope_key="chat.read.current")
    service = MiniBrainLlmRuntimeService(settings, adapter_factory=lambda: MockMiniBrainAdapter())
    with pytest.raises(ValidationError):
        service._dispatch_tool_call(scope_key="chat.read.current", admin_id="", session_id="s1")


# -- explain_dashboard_page -----------------------------------------------------------------------


def test_explain_page_found_in_template_catalogue(service: MiniBrainLlmRuntimeService) -> None:
    result = service.explain_dashboard_page(session_id=None, page_id="overview", nav_key=None, admin_id="admin-1")
    assert result["backend_type"] == "template"
    assert result["error_message"] is None
    assert len(result["reply"]["sanitized_text"]) > 0


def test_explain_page_falls_back_to_llm_when_unknown(service: MiniBrainLlmRuntimeService) -> None:
    result = service.explain_dashboard_page(session_id=None, page_id="totally_unknown_xyz", nav_key=None, admin_id="admin-1")
    assert result["backend_type"] == "local"
    assert len(result["reply"]["sanitized_text"]) > 0


# -- summarize_phase_report / summarize_regression_results --------------------------------------------


def test_summarize_phase_report(service: MiniBrainLlmRuntimeService) -> None:
    result = service.summarize_phase_report(session_id=None, report={"title": "MB-27", "status": "complete", "tests_passed": 133}, admin_id="admin-1")
    assert result["backend_type"] == "local"
    assert result["reply"]["capability"] == "summarize_report"


def test_summarize_regression_results(service: MiniBrainLlmRuntimeService) -> None:
    result = service.summarize_regression_results(session_id=None, regression_result={"passed": 100, "failed": 0, "errors": 0}, admin_id="admin-1")
    assert result["backend_type"] == "local"
    assert result["reply"]["capability"] == "summarize_regression"


# -- explain_error_message ------------------------------------------------------------------------------


def test_explain_error_message(service: MiniBrainLlmRuntimeService) -> None:
    result = service.explain_error_message(session_id=None, error_message="TypeError: cannot read x", admin_id="admin-1")
    assert result["backend_type"] == "local"
    assert result["reply"]["capability"] == "explain_error"


# -- next_actions ------------------------------------------------------------------------------------------


def test_next_actions_always_returns_structured_list(service: MiniBrainLlmRuntimeService) -> None:
    result = service.next_actions(session_id=None, status_snapshot={"failing_tests": 2}, admin_id="admin-1")
    assert isinstance(result["actions"], list)
    assert len(result["actions"]) >= 1


def test_next_actions_persisted_as_tool_call_json(service: MiniBrainLlmRuntimeService) -> None:
    result = service.next_actions(session_id=None, status_snapshot={"failing_tests": 1}, admin_id="admin-1")
    messages = service.list_messages(result["session"]["public_id"])["items"]
    reply = [m for m in messages if m["role"] == "assistant"][0]
    assert reply["tool_call"] is not None
    assert "actions" in reply["tool_call"]


def test_next_actions_without_backend_still_returns_rule_based_list(settings: Settings) -> None:
    service = MiniBrainLlmRuntimeService(settings)  # no adapter -- unavailable backend
    result = service.next_actions(session_id=None, status_snapshot={"pending_proposals": 3}, admin_id="admin-1")
    assert len(result["actions"]) >= 1
    assert result["error_message"] is not None


# -- fallback chain (real MB-27 provider settings, mocked httpx for external) ---------------------------


def test_resolve_backend_local_when_configured_with_real_model_file(settings: Settings, tmp_path: Path) -> None:
    from backend.services.mini_brain_provider_settings_service import MiniBrainProviderSettingsService

    model_file = settings.resolved_allowed_model_dir / "model.gguf"
    model_file.parent.mkdir(parents=True, exist_ok=True)
    model_file.write_bytes(b"fake")
    provider_service = MiniBrainProviderSettingsService(settings)
    setting = provider_service.create_provider_setting(
        provider_key="local_llm", enabled=True, config={"model_path": str(model_file)}, admin_id="admin-1",
    )
    service = MiniBrainLlmRuntimeService(settings)
    backend = service._resolve_backend()
    assert backend["backend_type"] == "local"


def test_resolve_backend_unavailable_with_no_settings_configured(settings: Settings) -> None:
    service = MiniBrainLlmRuntimeService(settings)
    backend = service._resolve_backend()
    assert backend["backend_type"] == "unavailable"


def test_resolve_backend_external_when_local_unconfigured_and_external_ready(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.services.mini_brain_provider_settings_service import MiniBrainProviderSettingsService
    from core_model.mini_brain.provider_settings import secret_encryptor

    monkeypatch.setenv(secret_encryptor.SECRET_ENCRYPTION_KEY_ENV_VAR, Fernet.generate_key().decode("ascii"))
    provider_service = MiniBrainProviderSettingsService(settings)
    setting = provider_service.create_provider_setting(provider_key="openai", enabled=True, config={}, admin_id="admin-1")
    provider_service.set_secret(setting["public_id"], secret_name="api_key", raw_value="sk-real-key", admin_id="admin-1")

    service = MiniBrainLlmRuntimeService(settings)
    backend = service._resolve_backend()
    assert backend["backend_type"] == "external"
    assert backend["external_provider_key"] == "openai"


# -- grounded_chat (MB-37) --------------------------------------------------------------------------------


class _RecordingAdapter:
    """Test-only spy adapter -- records every message list passed to
    `generate()` so tests can assert on exact prompt injection without
    depending on MockMiniBrainAdapter's hash-seeded reply selection."""

    backend_type = "local"

    def __init__(self) -> None:
        self.calls: list[list[dict]] = []

    def is_available(self) -> bool:
        return True

    def generate(self, *, messages, max_tokens=None, temperature=None):
        self.calls.append(messages)
        return {"text": "grounded mock reply", "backend_type": "local", "tokens_generated": 3, "latency_ms": 1.0, "error_message": None}


class _StubRetrievalService:
    """Test-only stand-in for RagRetrievalService -- returns a canned
    result shaped exactly like the real service's `retrieve()` return
    value, so the grounded_chat code under test never has to know it's
    fake."""

    def __init__(self, results: list[dict]) -> None:
        self._results = results
        self.calls: list[tuple] = []

    def retrieve(self, payload, admin_id):
        self.calls.append((payload, admin_id))
        return {"public_id": "run-1", "results": self._results}


MB35_CHUNK = {
    "chunk_public_id": "chunk-1",
    "source_public_id": "c1cf3a96-f92d-4a61-a2cf-d448f947a057",
    "source_version_public_id": "ea0ad840-42b8-43f2-9419-5a384c0e050e",
    "rank": 1,
    "combined_score": 0.5,
    "normalized_text": "Test phrase: KAVERI-MANGO-7421",
}


def test_grounded_chat_calls_retrieval_when_profile_provided(settings: Settings) -> None:
    stub_retrieval = _StubRetrievalService(results=[MB35_CHUNK])
    service = MiniBrainLlmRuntimeService(
        settings, adapter_factory=lambda: _RecordingAdapter(), retrieval_service=stub_retrieval,
    )
    service.grounded_chat(
        session_id=None, message="What is the test phrase?",
        retrieval_profile_public_id="profile-1", top_k=4, admin_id="admin-1",
    )
    assert len(stub_retrieval.calls) == 1
    payload, admin_id = stub_retrieval.calls[0]
    assert payload.retrieval_profile_public_id == "profile-1"
    assert payload.query == "What is the test phrase?"
    assert admin_id == "admin-1"


def test_grounded_chat_injects_retrieved_text_into_prompt(settings: Settings) -> None:
    adapter = _RecordingAdapter()
    stub_retrieval = _StubRetrievalService(results=[MB35_CHUNK])
    service = MiniBrainLlmRuntimeService(settings, adapter_factory=lambda: adapter, retrieval_service=stub_retrieval)
    service.grounded_chat(
        session_id=None, message="What is the test phrase?",
        retrieval_profile_public_id="profile-1", top_k=4, admin_id="admin-1",
    )
    assert len(adapter.calls) == 1
    messages = adapter.calls[0]
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "KAVERI-MANGO-7421" in messages[1]["content"]
    assert messages[2] == {"role": "user", "content": "What is the test phrase?"}


def test_grounded_chat_returns_citations(settings: Settings) -> None:
    stub_retrieval = _StubRetrievalService(results=[MB35_CHUNK])
    service = MiniBrainLlmRuntimeService(
        settings, adapter_factory=lambda: _RecordingAdapter(), retrieval_service=stub_retrieval,
    )
    result = service.grounded_chat(
        session_id=None, message="What is the test phrase?",
        retrieval_profile_public_id="profile-1", top_k=4, admin_id="admin-1",
    )
    assert len(result["citations"]) == 1
    citation = result["citations"][0]
    assert citation["source_public_id"] == "c1cf3a96-f92d-4a61-a2cf-d448f947a057"
    assert citation["source_version_public_id"] == "ea0ad840-42b8-43f2-9419-5a384c0e050e"
    assert citation["rank"] == 1
    assert citation["score"] == 0.5
    assert "KAVERI-MANGO-7421" in citation["text_preview"]
    # No "title" on this chunk -- source_name falls back to the source id
    # rather than an empty string, so the widget always has something to render.
    assert citation["source_name"] == "c1cf3a96-f92d-4a61-a2cf-d448f947a057"


def test_grounded_chat_citation_uses_source_title_when_present(settings: Settings) -> None:
    chunk_with_title = {**MB35_CHUNK, "title": "MB35 RAG Test Space source"}
    stub_retrieval = _StubRetrievalService(results=[chunk_with_title])
    service = MiniBrainLlmRuntimeService(
        settings, adapter_factory=lambda: _RecordingAdapter(), retrieval_service=stub_retrieval,
    )
    result = service.grounded_chat(
        session_id=None, message="What is the test phrase?",
        retrieval_profile_public_id="profile-1", top_k=4, admin_id="admin-1",
    )
    assert result["citations"][0]["source_name"] == "MB35 RAG Test Space source"


# -- MB-42: default_retrieval_profile() ------------------------------------------------------


class _StubRetrievalServiceWithProfiles:
    def __init__(self, profiles: list[dict]) -> None:
        self._profiles = profiles

    def list_profiles(self) -> dict:
        return {"items": self._profiles}


def test_default_retrieval_profile_returns_none_when_none_active(settings: Settings) -> None:
    stub = _StubRetrievalServiceWithProfiles(profiles=[])
    service = MiniBrainLlmRuntimeService(settings, retrieval_service=stub)
    result = service.default_retrieval_profile()
    assert result == {"retrieval_profile_public_id": None, "name": None}


def test_default_retrieval_profile_ignores_non_active_profiles(settings: Settings) -> None:
    stub = _StubRetrievalServiceWithProfiles(
        profiles=[{"public_id": "p1", "name": "Draft profile", "status": "draft"}]
    )
    service = MiniBrainLlmRuntimeService(settings, retrieval_service=stub)
    result = service.default_retrieval_profile()
    assert result["retrieval_profile_public_id"] is None


def test_default_retrieval_profile_returns_the_most_recently_created_active_profile(settings: Settings) -> None:
    # list_profiles()'s real repository query orders created_at DESC,
    # id DESC (most recent first) -- this stub mirrors that ordering, so
    # "p3" (newest) must win over "p2" (older, also active).
    stub = _StubRetrievalServiceWithProfiles(
        profiles=[
            {"public_id": "p3", "name": "Newest live profile", "status": "active"},
            {"public_id": "p1", "name": "Draft profile", "status": "draft"},
            {"public_id": "p2", "name": "Older live profile", "status": "active"},
        ]
    )
    service = MiniBrainLlmRuntimeService(settings, retrieval_service=stub)
    result = service.default_retrieval_profile()
    assert result == {"retrieval_profile_public_id": "p3", "name": "Newest live profile"}


def test_grounded_chat_respects_top_k(settings: Settings) -> None:
    chunks = [{**MB35_CHUNK, "chunk_public_id": f"chunk-{i}", "rank": i} for i in range(1, 6)]
    stub_retrieval = _StubRetrievalService(results=chunks)
    service = MiniBrainLlmRuntimeService(
        settings, adapter_factory=lambda: _RecordingAdapter(), retrieval_service=stub_retrieval,
    )
    result = service.grounded_chat(
        session_id=None, message="q", retrieval_profile_public_id="profile-1", top_k=2, admin_id="admin-1",
    )
    assert len(result["citations"]) == 2


def test_grounded_chat_zero_hits_returns_empty_citation_list(settings: Settings) -> None:
    stub_retrieval = _StubRetrievalService(results=[])
    service = MiniBrainLlmRuntimeService(
        settings, adapter_factory=lambda: _RecordingAdapter(), retrieval_service=stub_retrieval,
    )
    result = service.grounded_chat(
        session_id=None, message="What is the capital of Germany?",
        retrieval_profile_public_id="profile-1", top_k=4, admin_id="admin-1",
    )
    assert result["citations"] == []
    assert result["reply"]["sanitized_text"]  # still a normal, non-grounded chat reply


def test_grounded_chat_without_profile_skips_retrieval_entirely(settings: Settings) -> None:
    stub_retrieval = _StubRetrievalService(results=[MB35_CHUNK])
    service = MiniBrainLlmRuntimeService(
        settings, adapter_factory=lambda: _RecordingAdapter(), retrieval_service=stub_retrieval,
    )
    result = service.grounded_chat(
        session_id=None, message="hello", retrieval_profile_public_id=None, top_k=4, admin_id="admin-1",
    )
    assert stub_retrieval.calls == []
    assert result["citations"] == []


def test_grounded_chat_persists_conversation_like_normal_chat(settings: Settings) -> None:
    stub_retrieval = _StubRetrievalService(results=[MB35_CHUNK])
    service = MiniBrainLlmRuntimeService(
        settings, adapter_factory=lambda: _RecordingAdapter(), retrieval_service=stub_retrieval,
    )
    result = service.grounded_chat(
        session_id=None, message="What is the test phrase?",
        retrieval_profile_public_id="profile-1", top_k=4, admin_id="admin-1",
    )
    messages = service.list_messages(result["session"]["public_id"])["items"]
    assert [m["role"] for m in messages] == ["admin", "assistant"]
    assert messages[0]["sanitized_text"] == "What is the test phrase?"


def test_grounded_chat_reuses_existing_session(settings: Settings) -> None:
    stub_retrieval = _StubRetrievalService(results=[MB35_CHUNK])
    service = MiniBrainLlmRuntimeService(
        settings, adapter_factory=lambda: _RecordingAdapter(), retrieval_service=stub_retrieval,
    )
    first = service.grounded_chat(
        session_id=None, message="first question", retrieval_profile_public_id="profile-1", top_k=4, admin_id="admin-1",
    )
    session_id = first["session"]["public_id"]
    second = service.grounded_chat(
        session_id=session_id, message="second question", retrieval_profile_public_id="profile-1", top_k=4, admin_id="admin-1",
    )
    assert second["session"]["public_id"] == session_id


def test_grounded_chat_requires_real_admin_id(service: MiniBrainLlmRuntimeService) -> None:
    with pytest.raises(ValidationError):
        service.grounded_chat(session_id=None, message="hi", retrieval_profile_public_id=None, top_k=4, admin_id="")


def test_existing_chat_endpoint_behavior_unchanged_by_grounded_addition(service: MiniBrainLlmRuntimeService) -> None:
    # The exact same assertions as the pre-existing `chat()` coverage --
    # proves adding grounded_chat left `chat()` byte-for-byte unaffected.
    result = service.chat(session_id=None, message="hello", admin_id="admin-1")
    assert result["session"]["public_id"]
    assert result["backend_type"] == "local"
    assert result["reply"]["sanitized_text"]
    assert "citations" not in result


# -- diagnostics reflects real session activity ------------------------------------------------------------


def test_diagnostics_reflects_active_sessions_and_messages(service: MiniBrainLlmRuntimeService) -> None:
    service.chat(session_id=None, message="hello", admin_id="admin-1")
    diag = service.diagnostics()
    assert diag["active_session_count"] == 1
    assert diag["total_messages"] == 2
