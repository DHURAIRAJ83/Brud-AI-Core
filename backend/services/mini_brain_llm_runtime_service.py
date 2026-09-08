"""MB-28: Real Mini Brain LLM Runtime & Admin Assistant Intelligence
Layer -- orchestration layer.

This is a new, additive, parallel capability -- it does NOT touch the
separate, pre-existing "Phase 8" Admin Assistant system
(`AdminAssistantService`, `AdminAssistantChatService`,
`admin_assistant_tools.py`, `conversation_sessions`/
`conversation_turns`) at all, with exactly one narrow, deliberate
exception (Phase 16.5): `chat()` calls the existing, unmodified
`AdminAssistantService.propose()` -- via the shared
`core_model.admin_assistant.chat_action_bridge.propose_chat_action()`
bridge, the same one Phase-8's own chat already used -- when a message
names one of the four already-registered MB-39 actionable scopes. This
never calls `review()`/`execute()`, never duplicates a governance rule,
and never grants MB-28 any capability Phase-8 didn't already expose;
see `_maybe_propose_governed_action()` below.

Fallback chain: read the `local_llm` provider setting via MB-27's own
`MiniBrainProviderSettingsService.list_settings(provider_type=
"local_model")` (the real existing service method -- there is no
service-layer `get_setting_by_provider_key`, only a repository-layer
one) to build a `LlamaCppMiniBrainAdapter`; on unavailability, check
`list_settings(provider_type="external_ai", enabled=True)` plus
`provider_validator.is_fully_configured()` for an external fallback.
`provider_fallback_policy.decide()` makes the actual decision from
pre-resolved booleans -- this service only gathers data and acts.

Tool dispatch (`_dispatch_tool_call`) never bypasses MB-25's real
governance pipeline: it looks for an already-enabled plugin with an
already-granted permission for the classified scope, issues a fresh
execution token via `MiniBrainPluginGovernanceService.
issue_execution_token()`, and calls `MiniBrainPluginRuntimeService.
execute_for_admin_assistant()` -- the same, only sanctioned
admin-assistant-initiated tool-execution entrypoint, which itself
hard-requires a real `requester_admin_public_id`. No plugin ships in
this phase, so this path is real but exercised only via a
test-registered mock plugin fixture.

Every capability writes a `mini_brain_llm_runtime_events` row
regardless of whether the LLM was actually called, so diagnostics and
audit trails stay honest even when only the deterministic rule-based
path (e.g. `next_action_planner`) ran.
"""

from __future__ import annotations

import time
from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.database.repositories.mini_brain_llm_runtime import (
    MiniBrainLlmRuntimeRepository,
    public_message_row,
    public_session_row,
)
from backend.database.repositories.mini_brain_provider_settings import MiniBrainProviderSettingsRepository
from backend.database.repositories.base import NotFoundError, ValidationError
from backend.database.repositories.phase2 import SettingsRepository
from backend.database.repositories.rag import RagRepository
from backend.models.rag import RetrieveRequest
from backend.services.rag_retrieval_service import RagRetrievalService
from backend.services.mini_brain_llm_adapter import (
    DEFAULT_CONTEXT_LENGTH,
    DEFAULT_MAX_TOKENS,
    DEFAULT_TEMPERATURE,
    DEFAULT_THREADS,
    ExternalProviderMiniBrainAdapter,
    LlamaCppMiniBrainAdapter,
)
from backend.services.admin_assistant_service import AdminAssistantService
from backend.services.mini_brain_plugin_governance_service import MiniBrainPluginGovernanceService
from backend.services.mini_brain_plugin_runtime_service import MiniBrainPluginRuntimeService
from backend.services.mini_brain_provider_settings_service import MiniBrainProviderSettingsService
from backend.services.pilot_metrics import record_pilot_metric
from core_model.admin_assistant.chat_action_bridge import match_actionable_intent, propose_chat_action
from core_model.mini_brain.llm_runtime import (
    admin_explainer_templates,
    answer_style_policy,
    citation_formatter,
    context_window_manager,
    conversation_title_builder,
    message_sanitizer,
    next_action_planner,
    prompt_builder,
    provider_fallback_policy,
    report_summarizer,
    runtime_diagnostics_builder,
    token_budget,
    tool_intent_classifier,
)
from core_model.mini_brain.intelligence.context_intelligence import ContextIntelligenceManager
from core_model.mini_brain.provider_settings import provider_validator, secret_encryptor

# MB-43: the admin-chosen default grounded-chat retrieval profile is
# stored under this key in the existing, previously-unused `app_settings`
# table (via SettingsRepository) -- no new table, no new column.
DEFAULT_RETRIEVAL_PROFILE_SETTING_KEY = "mini_brain_grounded_chat_default_retrieval_profile_public_id"


class MiniBrainLlmRuntimeService:
    def __init__(
        self, settings: Settings, *, adapter_factory: Any = None, retrieval_service: Any = None,
        app_settings_repository: Any = None, assistant_service: Any = None,
    ) -> None:
        self.settings = settings
        self.repository = MiniBrainLlmRuntimeRepository(settings.resolved_database_path)
        self.provider_service = MiniBrainProviderSettingsService(settings)
        self._provider_repository = MiniBrainProviderSettingsRepository(settings.resolved_database_path)
        self.plugin_governance = MiniBrainPluginGovernanceService(settings)
        self.plugin_runtime = MiniBrainPluginRuntimeService(settings, governance=self.plugin_governance)
        self.context_intelligence = ContextIntelligenceManager()
        # test seam only -- production always resolves real adapters via
        # `_resolve_backend()`; a fixed adapter here lets tests inject
        # `MockMiniBrainAdapter()` without touching provider settings.
        self._adapter_factory = adapter_factory
        # MB-37: real reuse of the existing RAG retrieval service (same
        # construction the /admin/rag routes use) -- never a new,
        # bespoke retrieval path. Overridable only for tests.
        self.retrieval_service = retrieval_service or RagRetrievalService(
            RagRepository(settings.resolved_database_path), settings,
        )
        # MB-43: real reuse of the existing, previously-unused generic
        # settings repository.
        self._app_settings_repository = app_settings_repository or SettingsRepository(
            settings.resolved_database_path
        )
        # Phase 16.5: real reuse of the existing, unmodified Phase-8
        # proposal service -- MB-28 only ever calls .propose() through
        # it (see _maybe_propose_governed_action()), never .review() or
        # .execute(). Overridable only for tests.
        self.assistant_service = assistant_service or AdminAssistantService(settings)

    # -- backend resolution --------------------------------------------------------

    def _local_config(self) -> dict[str, Any] | None:
        items = self.provider_service.list_settings(provider_type="local_model")["items"]
        for item in items:
            if item["provider_key"] == "local_llm":
                return item
        return None

    def _external_config_and_key(self) -> tuple[dict[str, Any], str] | None:
        items = self.provider_service.list_settings(provider_type="external_ai", enabled=True)["items"]
        for item in items:
            present = [secret["secret_name"] for secret in item["secrets"] if secret["is_set"]]
            if not provider_validator.is_fully_configured(provider_key=item["provider_key"], present_secret_names=present):
                continue
            secret_row = self._provider_repository_get_secret(item["public_id"], "api_key")
            if secret_row is None:
                continue
            decrypted = secret_encryptor.decrypt_secret(secret_row["encrypted_value"])
            return item, decrypted
        return None

    def _provider_repository_get_secret(self, setting_public_id: str, secret_name: str):
        with self._provider_repository.transaction() as connection:
            return self._provider_repository.get_secret(connection, setting_public_id=setting_public_id, secret_name=secret_name)

    def _resolve_backend(
        self,
        execution_mode: str = "auto",
        provider_key: str | None = None,
        model_override: str | None = None,
    ) -> dict[str, Any]:
        if self._adapter_factory is not None:
            adapter = self._adapter_factory()
            backend_type = getattr(adapter, "backend_type", "local")
            return {"adapter": adapter, "backend_type": backend_type, "reason": "test adapter factory override"}

        local_config = self._local_config()
        local_adapter: LlamaCppMiniBrainAdapter | None = None
        local_available = False
        if local_config is not None:
            config = local_config.get("config", {})
            local_adapter = LlamaCppMiniBrainAdapter(
                settings=self.settings,
                model_path=config.get("model_path"),
                context_length=int(config.get("context_length") or DEFAULT_CONTEXT_LENGTH),
                threads=int(config.get("threads") or DEFAULT_THREADS),
                temperature=float(config.get("temperature") if config.get("temperature") is not None else DEFAULT_TEMPERATURE),
            )
            local_available = local_adapter.is_available()

        if execution_mode == "local":
            if local_available:
                return {"adapter": local_adapter, "backend_type": "local", "reason": "local model selected and available"}
            return {"adapter": None, "backend_type": "unavailable", "reason": "local model is not available or configured"}

        if provider_key == "ollama":
            model_name = model_override or "llama3"
            adapter = ExternalProviderMiniBrainAdapter(
                provider_key="ollama", api_key="", model=model_name,
                base_url=getattr(self.settings, "ollama_url", None),
            )
            return {
                "adapter": adapter,
                "backend_type": "external",
                "external_provider_key": "ollama",
                "model": model_name,
                "reason": "local ollama provider requested",
            }

        # Resolve external provider if specific or fallback
        external = None
        if provider_key:
            items = self.provider_service.list_settings(provider_type="external_ai", enabled=True).get("items", [])
            for item in items:
                if item["provider_key"] == provider_key:
                    secret_row = self._provider_repository_get_secret(item["public_id"], "api_key")
                    if secret_row is not None:
                        decrypted = secret_encryptor.decrypt_secret(secret_row["encrypted_value"])
                        external = (item, decrypted)
                        break
        if external is None:
            external = self._external_config_and_key()

        if execution_mode == "provider":
            if external is not None:
                item, api_key = external
                model_name = model_override or item.get("config", {}).get("model")
                adapter = ExternalProviderMiniBrainAdapter(
                    provider_key=item["provider_key"], api_key=api_key, model=model_name,
                )
                return {
                    "adapter": adapter,
                    "backend_type": "external",
                    "external_provider_key": item["provider_key"],
                    "model": model_name,
                    "reason": f"provider {item['provider_key']} configured",
                }
            return {"adapter": None, "backend_type": "unavailable", "reason": "requested external provider is not configured or enabled"}

        # Auto mode
        external_enabled = external is not None
        external_configured = external is not None

        decision = provider_fallback_policy.decide(
            local_available=local_available, local_model_loaded=local_available,
            external_enabled=external_enabled, external_configured=external_configured,
        )

        if decision["backend"] == "local":
            return {"adapter": local_adapter, "backend_type": "local", "reason": decision["reason"]}
        if decision["backend"] == "external" and external is not None:
            item, api_key = external
            model_name = model_override or item.get("config", {}).get("model")
            adapter = ExternalProviderMiniBrainAdapter(
                provider_key=item["provider_key"], api_key=api_key, model=model_name,
            )
            return {
                "adapter": adapter,
                "backend_type": "external",
                "external_provider_key": item["provider_key"],
                "model": model_name,
                "reason": decision["reason"],
            }
        return {"adapter": None, "backend_type": "unavailable", "reason": decision["reason"]}

    def _list_available_fallback_candidates(
        self,
        *,
        primary_provider_key: str | None = None,
        model_override: str | None = None,
    ) -> list[dict[str, Any]]:
        """Resolve ordered list of fallback provider candidates:
        1. Secondary external providers (enabled & fully configured, excluding primary)
        2. Local Ollama (probed for live availability: configured != available)
        3. Local GGUF (probed for live availability: configured != available)
        """
        if self._adapter_factory is not None:
            return []

        candidates: list[dict[str, Any]] = []

        # 1. Secondary external providers from settings
        items = self.provider_service.list_settings(provider_type="external_ai", enabled=True).get("items", [])
        for item in items:
            pkey = item["provider_key"]
            if pkey == primary_provider_key:
                continue
            present = [secret["secret_name"] for secret in item["secrets"] if secret["is_set"]]
            if not provider_validator.is_fully_configured(provider_key=pkey, present_secret_names=present):
                continue
            secret_row = self._provider_repository_get_secret(item["public_id"], "api_key")
            if secret_row is None:
                continue
            decrypted = secret_encryptor.decrypt_secret(secret_row["encrypted_value"])
            model_name = model_override or item.get("config", {}).get("model")
            adapter = ExternalProviderMiniBrainAdapter(
                provider_key=pkey, api_key=decrypted, model=model_name,
            )
            candidates.append({
                "adapter": adapter,
                "backend_type": "external",
                "external_provider_key": pkey,
                "model": model_name,
                "reason": f"secondary external provider '{pkey}'",
            })

        # 2. Local Ollama candidate (check availability: configured != available)
        if primary_provider_key != "ollama":
            ollama_adapter = ExternalProviderMiniBrainAdapter(
                provider_key="ollama", api_key="", model=model_override or "llama3",
                base_url=getattr(self.settings, "ollama_url", None),
            )
            candidates.append({
                "adapter": ollama_adapter,
                "backend_type": "external",
                "external_provider_key": "ollama",
                "model": model_override or "llama3",
                "reason": "fallback local ollama",
            })

        # 3. Local GGUF candidate
        if primary_provider_key != "local_llm":
            local_config = self._local_config()
            if local_config is not None:
                config = local_config.get("config", {})
                local_adapter = LlamaCppMiniBrainAdapter(
                    settings=self.settings,
                    model_path=config.get("model_path"),
                    context_length=int(config.get("context_length") or DEFAULT_CONTEXT_LENGTH),
                    threads=int(config.get("threads") or DEFAULT_THREADS),
                    temperature=float(config.get("temperature") if config.get("temperature") is not None else DEFAULT_TEMPERATURE),
                )
                candidates.append({
                    "adapter": local_adapter,
                    "backend_type": "local",
                    "external_provider_key": None,
                    "model": "local-gguf",
                    "reason": "fallback local llama-cpp",
                })

        return candidates


    # -- diagnostics ------------------------------------------------------------

    def diagnostics(self) -> dict[str, Any]:
        import importlib.util

        local_config = self._local_config()
        local_adapter = None
        model_path = None
        if local_config is not None:
            config = local_config.get("config", {})
            model_path = config.get("model_path")
            local_adapter = LlamaCppMiniBrainAdapter(settings=self.settings, model_path=model_path)
        local_available = local_adapter.is_available() if local_adapter else False

        external = self._external_config_and_key()

        cache_metrics = None
        try:
            from backend.services.mini_brain_dashboard_context_service import MiniBrainDashboardContextService
            cache_metrics = MiniBrainDashboardContextService(self.settings).cache.stats()
        except Exception:
            cache_metrics = {}

        resilience_metrics = {
            "total_replies": 0,
            "total_errors": 0,
            "total_retries": 0,
            "failovers": 0,
        }

        with self.repository.transaction() as connection:
            active_session_count = self.repository.count_sessions(connection, status="active")
            total_message_count = self.repository.total_message_count(connection)
            try:
                events = self.repository.list_events(connection, limit=100, offset=0)
                for ev in events:
                    etype = ev["event_type"]
                    if etype == "reply_generated":
                        resilience_metrics["total_replies"] += 1
                    elif etype in ("generation_error", "stream_error", "provider_error"):
                        resilience_metrics["total_errors"] += 1
                    elif etype == "provider_retry":
                        resilience_metrics["total_retries"] += 1
                    elif etype == "provider_failover":
                        resilience_metrics["failovers"] += 1
            except Exception:
                pass

        provider_probes = {
            "local": {
                "available": local_available,
                "loaded": local_available,
                "model": runtime_diagnostics_builder.mask_model_path(model_path),
            },
            "external": {
                "configured": external is not None,
                "provider_key": external[0]["provider_key"] if external else None,
            },
        }

        return runtime_diagnostics_builder.build_diagnostics(
            local_available=local_available,
            local_model_loaded=local_available,
            configured_model_path=model_path,
            external_fallback_enabled=external is not None,
            external_provider_key=external[0]["provider_key"] if external else None,
            active_session_count=active_session_count,
            total_messages=total_message_count,
            llama_cpp_installed=importlib.util.find_spec("llama_cpp") is not None,
            cache_metrics=cache_metrics,
            resilience_metrics=resilience_metrics,
            provider_probes=provider_probes,
        )

    def widget_health(self) -> dict[str, Any]:
        """MB-45: single source of truth for the Admin Assistant widget's
        health banner. Calls the exact same `_resolve_backend()` decision
        `chat()`/`grounded_chat()` use to pick an adapter -- the banner can
        therefore never disagree with what actually answers a message,
        closing the MB-44-audited divergence against the previous
        Phase-8 `admin_assistant_chat_service.llm_status()` check (which
        read an unrelated Phase-15 inference assignment). Never reads
        Phase-8 state."""
        backend = self._resolve_backend()
        backend_type = backend["backend_type"]
        loaded = backend_type in ("local", "external")

        current_model = None
        if backend_type == "local":
            local_config = self._local_config()
            current_model = (local_config or {}).get("config", {}).get("model_path")
        elif backend_type == "external":
            current_model = backend.get("external_provider_key")

        return {
            "loaded": loaded,
            "backend_type": backend_type,
            "current_model": current_model,
            "available": loaded,
            "error_message": None if loaded else backend["reason"],
        }

    # -- sessions --------------------------------------------------------------

    def open_session(self, *, admin_id: str, title: str | None = None) -> dict[str, Any]:
        if not admin_id:
            raise ValidationError("a real admin identity is required to open a session")
        with self.repository.transaction() as connection:
            session_id = self.repository.create_session(connection, admin_public_id=admin_id, title=title)
            self.repository.create_event(
                connection, session_id=session_id, event_type="session_created", backend_type=None,
                admin_id=admin_id, detail={},
            )
            self.repository.create_memory(
                connection, session_id=session_id, admin_public_id=admin_id, event_type="session_started",
                backend_type=None, total_messages=0,
            )
            return public_session_row(self.repository.get_session(connection, session_id))

    def get_session(self, session_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_session_row(self.repository.get_session(connection, session_id))

    def list_sessions(self, *, admin_id: str | None = None, status: str | None = None, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_sessions(connection, admin_public_id=admin_id, status=status, limit=limit, offset=offset)
        return {"items": [public_session_row(row) for row in rows]}

    def list_messages(self, session_id: str, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            self.repository.get_session(connection, session_id)
            rows = self.repository.list_messages(connection, session_id=session_id, limit=limit, offset=offset)
        return {"items": [public_message_row(row) for row in rows]}

    def delete_session(self, session_id: str, *, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session_row = self.repository.update_session(connection, session_id, {"status": "deleted"})
            self.repository.create_event(
                connection, session_id=session_id, event_type="session_deleted", backend_type=None,
                admin_id=admin_id, detail={},
            )
            self.repository.create_memory(
                connection, session_id=session_id, admin_public_id=admin_id, event_type="session_deleted",
                backend_type=None, total_messages=session_row["total_messages"],
            )
            return public_session_row(session_row)

    # -- MB-39/Phase 16.5: governance proposal bridge ------------------------------
    #
    # Detection is not authorization: a match here only means "this message
    # names one of the four already-registered admin_assistant action
    # types" -- it creates a real, pending proposal through the existing,
    # unmodified AdminAssistantService.propose() and returns immediately
    # (this method never calls, and cannot reach, review()/execute()).
    # Human review and approval on the Admin Assistant page remain the
    # only path to execution, exactly as for a proposal created through
    # Phase-8's own chat.

    def _maybe_propose_governed_action(self, message: str, admin_id: str) -> dict[str, Any] | None:
        match = match_actionable_intent(message)
        if match is None:
            return None
        # MB-28's chat() has no page/entity context to pass along (unlike
        # Phase-8's chat, which receives page_id/entity_type/
        # entity_public_id from the dashboard). Scopes that require real
        # entity context the bridge was never given (run_sample_quality_checks,
        # build_rag_sandbox_index, run_rag_sandbox_evaluation) therefore
        # always decline here and fall through to normal chat -- this
        # bridge never invents a target it was not actually given.
        return propose_chat_action(
            self.assistant_service, match=match, message=message, admin_id=admin_id,
            entity_type=None, entity_public_id=None,
        )

    def _reply_governed_action_proposed(self, proposal: dict[str, Any]) -> str:
        return (
            f"This action ({proposal['action_type']}) is not performed directly here. "
            f"A proposal (id {proposal['public_id']}, status: {proposal['status']}) has "
            "been created for it. Nothing will run until an admin reviews and approves "
            "it on the Admin Assistant page.\n\n"
            f"இந்த நடவடிக்கை ({proposal['action_type']}) நேரடியாக செய்யப்படாது. "
            f"இதற்காக ஒரு proposal (id {proposal['public_id']}, நிலை: {proposal['status']}) "
            "உருவாக்கப்பட்டுள்ளது. ஒரு admin அதை Admin Assistant பக்கத்தில் review "
            "செய்து approve செய்யும் வரை எதுவும் இயக்கப்படாது."
        )

    # -- tool dispatch ------------------------------------------------------------

    def _find_authorized_plugin_for_scope(self, scope_key: str) -> dict[str, Any] | None:
        plugins = self.plugin_governance.list_plugins(status="enabled")["items"]
        for plugin in plugins:
            permissions = self.plugin_governance.list_permissions(plugin["public_id"])["items"]
            if any(permission["scope_key"] == scope_key and permission["status"] == "granted" for permission in permissions):
                return plugin
        return None

    def _dispatch_tool_call(self, *, scope_key: str, admin_id: str, session_id: str) -> dict[str, Any] | None:
        plugin = self._find_authorized_plugin_for_scope(scope_key)
        if plugin is None:
            return None
        token = self.plugin_governance.issue_execution_token(
            plugin["public_id"], scope_keys=[scope_key], raw_user_identity=admin_id,
            raw_session_identity=session_id, admin_id=admin_id,
        )
        result = self.plugin_runtime.execute_for_admin_assistant(
            plugin_public_id=plugin["public_id"], scope_key=scope_key, arguments={},
            requester_admin_public_id=admin_id, execution_token=token,
        )
        return {
            "tool_name": plugin.get("name", plugin["public_id"]),
            "summary": str(result.get("output") or result.get("status") or "")[:500],
            "plugin_public_id": plugin["public_id"],
            "status": result.get("status"),
        }

    def _get_dashboard_context(self) -> dict[str, Any] | None:
        try:
            from backend.services.mini_brain_dashboard_context_service import (
                MiniBrainDashboardContextService,
            )
            return MiniBrainDashboardContextService(self.settings).get_system_context()
        except Exception:
            return None

    # -- reply generation core ---------------------------------------------------

    def _generate_reply(
        self, *, session_id: str, capability: str, question: str, history: list[dict[str, Any]],
        tool_results: list[dict[str, Any]] | None = None,
        execution_mode: str = "auto",
        provider_key: str | None = None,
        model_override: str | None = None,
        admin_id: str | None = None,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        backend = self._resolve_backend(
            execution_mode=execution_mode,
            provider_key=provider_key,
            model_override=model_override,
        )
        adapter = backend["adapter"]
        backend_type = backend["backend_type"]

        if adapter is None:
            return {"text": "", "backend_type": backend_type, "error_message": backend["reason"], "truncated": False}

        style = answer_style_policy.style_for(capability=capability)
        budget = token_budget.compute_budget(context_length=DEFAULT_CONTEXT_LENGTH, max_tokens=DEFAULT_MAX_TOKENS)
        context_selection = context_window_manager.select_context_messages(
            messages=history, input_budget_tokens=budget["input_budget_tokens"],
        )
        t_ctx0 = time.perf_counter()
        dashboard_ctx = self._get_dashboard_context()
        context_ms = round((time.perf_counter() - t_ctx0) * 1000, 2)
        prompt = prompt_builder.build_prompt(
            style_directives=style, context_messages=context_selection["messages"],
            question=question, tool_results=tool_results, dashboard_context=dashboard_ctx,
        )
        messages = [{"role": "system", "content": prompt["system_prompt"]}] + prompt["messages"]
        t_gen0 = time.perf_counter()
        result = adapter.generate(messages=messages, max_tokens=budget["output_budget_tokens"], temperature=DEFAULT_TEMPERATURE)
        generation_ms = round((time.perf_counter() - t_gen0) * 1000, 2)

        # Provider Resilience: if primary failed after its own retries and auto mode is enabled, attempt failover chain
        if result.get("error_message") and execution_mode == "auto":
            primary_error = result["error_message"]
            primary_provider = backend.get("external_provider_key") or backend_type
            fallback_candidates = self._list_available_fallback_candidates(
                primary_provider_key=backend.get("external_provider_key"),
                model_override=model_override,
            )
            failover_succeeded = False
            for candidate in fallback_candidates:
                cand_adapter = candidate["adapter"]
                cand_provider = candidate.get("external_provider_key") or candidate["backend_type"]
                # Availability check: configured != available
                if not cand_adapter.is_available():
                    continue
                try:
                    with self.repository.transaction() as conn:
                        self.repository.create_event(
                            conn,
                            session_id=session_id,
                            event_type="provider_failover",
                            backend_type=candidate["backend_type"],
                            admin_id=admin_id,
                            detail={
                                "from_provider": primary_provider,
                                "to_provider": cand_provider,
                                "failure_reason": primary_error,
                                "trace_id": trace_id,
                            },
                        )
                except Exception:
                    pass

                t_cand0 = time.perf_counter()
                cand_result = cand_adapter.generate(
                    messages=messages, max_tokens=budget["output_budget_tokens"], temperature=DEFAULT_TEMPERATURE
                )
                if not cand_result.get("error_message"):
                    result = cand_result
                    backend = candidate
                    generation_ms = round((time.perf_counter() - t_cand0) * 1000, 2)
                    failover_succeeded = True
                    break

            if not failover_succeeded:
                result["error_message"] = f"PROVIDER_EXHAUSTION: all providers failed or unavailable. Primary error: {primary_error}"
                result["backend_type"] = "unavailable"
                try:
                    with self.repository.transaction() as conn:
                        self.repository.create_event(
                            conn,
                            session_id=session_id,
                            event_type="provider_exhaustion",
                            backend_type="unavailable",
                            admin_id=admin_id,
                            detail={
                                "primary_provider": primary_provider,
                                "primary_error": primary_error,
                                "attempted_providers": [
                                    c.get("external_provider_key") or c["backend_type"]
                                    for c in fallback_candidates
                                ],
                                "trace_id": trace_id,
                            },
                        )
                except Exception:
                    pass

        text = result["text"]
        if text and tool_results:
            text = citation_formatter.append_citations(text=text, tool_results=tool_results)
        sanitized = message_sanitizer.sanitize_message(raw_text=text) if text else {"sanitized_text": "", "truncated": False}

        return {
            "text": sanitized["sanitized_text"],
            "backend_type": result["backend_type"] if result.get("error_message") is None else "unavailable",
            "error_message": result.get("error_message"),
            "truncated": sanitized["truncated"] or context_selection["truncated"],
            "external_provider_key": backend.get("external_provider_key"),
            "model": backend.get("model"),
            "stage_latencies": {
                "context_latency_ms": context_ms,
                "generation_latency_ms": generation_ms,
            },
        }

    def _persist_turn(
        self, *, session_id: str, admin_id: str, capability: str, question: str,
        reply_text: str, backend_type: str, tool_result: dict[str, Any] | None, truncated: bool,
        trace_id: str | None = None, stage_latencies: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        from backend.core.json_utils import redact_secrets
        safe_question = redact_secrets(question) if isinstance(question, str) else question
        safe_reply = redact_secrets(reply_text) if isinstance(reply_text, str) else reply_text
        with self.repository.transaction() as connection:
            self.repository.create_message(
                connection, session_id=session_id, role="admin", capability=capability, sanitized_text=safe_question,
                backend_type=None, tool_call=None, truncated=False, token_estimate=None,
            )
            reply_id = self.repository.create_message(
                connection, session_id=session_id, role="assistant", capability=capability, sanitized_text=safe_reply,
                backend_type=backend_type, tool_call=tool_result, truncated=truncated, token_estimate=None,
            )
            self.repository.update_session(connection, session_id, {"stage": "reply_received", "backend_type": backend_type})
            event_detail: dict[str, Any] = {"capability": capability}
            if trace_id:
                event_detail["trace_id"] = trace_id
            if stage_latencies:
                event_detail["stage_latencies_ms"] = stage_latencies
            self.repository.create_event(
                connection, session_id=session_id, event_type="reply_generated", backend_type=backend_type,
                admin_id=admin_id, detail=event_detail,
            )
            session_row = self.repository.get_session(connection, session_id)
            self.repository.create_memory(
                connection, session_id=session_id, admin_public_id=admin_id, event_type="reply_generated",
                backend_type=backend_type, total_messages=session_row["total_messages"],
            )
            return public_message_row(self.repository.get_message(connection, reply_id))

    def _ensure_session(self, *, session_id: str | None, admin_id: str, first_message: str | None = None) -> str:
        if session_id:
            with self.repository.transaction() as connection:
                self.repository.get_session(connection, session_id)
            return session_id
        title = conversation_title_builder.build_title(first_message=first_message or "New conversation")
        return self.open_session(admin_id=admin_id, title=title)["public_id"]

    # -- capability: chat / answer_admin_question --------------------------------

    def chat(
        self,
        *,
        session_id: str | None,
        message: str,
        admin_id: str,
        execution_mode: str = "auto",
        provider_key: str | None = None,
        model_override: str | None = None,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        if not admin_id:
            raise ValidationError("a real admin identity is required to chat")
        trace_id = trace_id or f"trc_{uuid4().hex[:16]}"
        t_start = time.perf_counter()
        record_pilot_metric(self.settings, "widget_plain_chat_count")
        sanitized = message_sanitizer.sanitize_message(raw_text=message)
        clean_message = sanitized["sanitized_text"]
        from backend.core.json_utils import redact_secrets
        clean_message = redact_secrets(clean_message)
        session_id = self._ensure_session(session_id=session_id, admin_id=admin_id, first_message=clean_message)

        if not clean_message.strip():
            reply_text = "Could you clarify what you'd like help with?"
            saved = self._persist_turn(
                session_id=session_id, admin_id=admin_id, capability="clarify", question=clean_message,
                reply_text=reply_text, backend_type=None, tool_result=None, truncated=False,
                trace_id=trace_id, stage_latencies={"total_latency_ms": round((time.perf_counter() - t_start) * 1000, 2)},
            )
            return {"session": self.get_session(session_id), "reply": saved, "backend_type": "template", "error_message": None, "trace_id": trace_id}

        proposal = self._maybe_propose_governed_action(clean_message, admin_id)
        if proposal is not None:
            reply_text = self._reply_governed_action_proposed(proposal)
            saved = self._persist_turn(
                session_id=session_id, admin_id=admin_id, capability="chat",
                question=clean_message, reply_text=reply_text, backend_type=None,
                tool_result=proposal, truncated=False,
                trace_id=trace_id, stage_latencies={"total_latency_ms": round((time.perf_counter() - t_start) * 1000, 2)},
            )
            return {
                "session": self.get_session(session_id), "reply": saved,
                "backend_type": "proposal_bridge", "error_message": None,
                "trace_id": trace_id,
            }

        with self.repository.transaction() as connection:
            history_rows = self.repository.list_messages(connection, session_id=session_id, limit=100, offset=0)

        # Guardrail 8: Deduplicate rapid identical submissions within the same session
        if (
            history_rows
            and len(history_rows) >= 2
            and history_rows[-2]["role"] == "admin"
            and history_rows[-2]["sanitized_text"] == clean_message
            and history_rows[-1]["role"] == "assistant"
        ):
            return {
                "session": self.get_session(session_id),
                "reply": public_message_row(history_rows[-1]),
                "backend_type": history_rows[-1]["backend_type"],
                "error_message": None,
                "trace_id": trace_id,
            }

        history = [{"role": row["role"], "content": row["sanitized_text"]} for row in history_rows]

        classification = tool_intent_classifier.classify(message=clean_message)
        tool_result = None
        if classification["intent"] == "tool_call" and classification["candidate_scope_key"]:
            with self.repository.transaction() as connection:
                self.repository.create_event(
                    connection, session_id=session_id, event_type="tool_call_dispatched", backend_type=None,
                    admin_id=admin_id, detail={"scope_key": classification["candidate_scope_key"], "trace_id": trace_id},
                )
            tool_result = self._dispatch_tool_call(scope_key=classification["candidate_scope_key"], admin_id=admin_id, session_id=session_id)

        outcome = self._generate_reply(
            session_id=session_id,
            capability="chat",
            question=clean_message,
            history=history,
            tool_results=[tool_result] if tool_result else None,
            execution_mode=execution_mode,
            provider_key=provider_key,
            model_override=model_override,
            admin_id=admin_id,
            trace_id=trace_id,
        )
        stage_timings = outcome.get("stage_latencies", {})
        stage_timings["total_latency_ms"] = round((time.perf_counter() - t_start) * 1000, 2)
        reply_text = outcome["text"] or (outcome["error_message"] or "The assistant is unavailable right now.")
        saved = self._persist_turn(
            session_id=session_id, admin_id=admin_id, capability="chat", question=clean_message,
            reply_text=reply_text, backend_type=outcome["backend_type"], tool_result=tool_result,
            truncated=outcome["truncated"], trace_id=trace_id, stage_latencies=stage_timings,
        )
        return {
            "session": self.get_session(session_id), "reply": saved,
            "backend_type": outcome["backend_type"], "error_message": outcome["error_message"],
            "trace_id": trace_id,
        }

    # -- capability: grounded_chat (MB-37) -----------------------------------------

    def _generate_grounded_reply(
        self,
        *,
        capability: str,
        question: str,
        history: list[dict[str, Any]],
        retrieved_chunks: list[dict[str, Any]],
        execution_mode: str = "auto",
        provider_key: str | None = None,
        model_override: str | None = None,
        admin_id: str | None = None,
        session_id: str | None = None,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        backend = self._resolve_backend(
            execution_mode=execution_mode,
            provider_key=provider_key,
            model_override=model_override,
        )
        adapter = backend["adapter"]
        backend_type = backend["backend_type"]

        if adapter is None:
            return {"text": "", "backend_type": backend_type, "error_message": backend["reason"], "truncated": False}

        style = answer_style_policy.style_for(capability=capability)
        budget = token_budget.compute_budget(context_length=DEFAULT_CONTEXT_LENGTH, max_tokens=DEFAULT_MAX_TOKENS)

        t_ctx0 = time.perf_counter()
        dashboard_ctx = self._get_dashboard_context()
        context_ms = round((time.perf_counter() - t_ctx0) * 1000, 2)
        if retrieved_chunks:
            prompt = prompt_builder.build_grounded_messages(
                system_prompt=style.get("system_prompt", ""), user_message=question,
                retrieved_chunks=retrieved_chunks, dashboard_context=dashboard_ctx,
            )
            messages = [{"role": "system", "content": prompt["system_prompt"]}] + prompt["messages"]
            truncated_context = False
        else:
            context_selection = context_window_manager.select_context_messages(
                messages=history, input_budget_tokens=budget["input_budget_tokens"],
            )
            prompt = prompt_builder.build_prompt(
                style_directives=style, context_messages=context_selection["messages"],
                question=question, dashboard_context=dashboard_ctx,
            )
            messages = [{"role": "system", "content": prompt["system_prompt"]}] + prompt["messages"]
            truncated_context = context_selection["truncated"]

        t_gen0 = time.perf_counter()
        result = adapter.generate(messages=messages, max_tokens=budget["output_budget_tokens"], temperature=DEFAULT_TEMPERATURE)
        generation_ms = round((time.perf_counter() - t_gen0) * 1000, 2)

        # Provider Resilience: failover if primary failed and auto mode is enabled
        if result.get("error_message") and execution_mode == "auto":
            primary_error = result["error_message"]
            primary_provider = backend.get("external_provider_key") or backend_type
            fallback_candidates = self._list_available_fallback_candidates(
                primary_provider_key=backend.get("external_provider_key"),
                model_override=model_override,
            )
            failover_succeeded = False
            for candidate in fallback_candidates:
                cand_adapter = candidate["adapter"]
                cand_provider = candidate.get("external_provider_key") or candidate["backend_type"]
                if not cand_adapter.is_available():
                    continue
                try:
                    with self.repository.transaction() as conn:
                        self.repository.create_event(
                            conn,
                            session_id=session_id,
                            event_type="provider_failover",
                            backend_type=candidate["backend_type"],
                            admin_id=admin_id,
                            detail={
                                "from_provider": primary_provider,
                                "to_provider": cand_provider,
                                "failure_reason": primary_error,
                                "trace_id": trace_id,
                            },
                        )
                except Exception:
                    pass

                t_cand0 = time.perf_counter()
                cand_result = cand_adapter.generate(
                    messages=messages, max_tokens=budget["output_budget_tokens"], temperature=DEFAULT_TEMPERATURE
                )
                if not cand_result.get("error_message"):
                    result = cand_result
                    backend = candidate
                    generation_ms = round((time.perf_counter() - t_cand0) * 1000, 2)
                    failover_succeeded = True
                    break

            if not failover_succeeded:
                result["error_message"] = f"PROVIDER_EXHAUSTION: all providers failed or unavailable. Primary error: {primary_error}"
                result["backend_type"] = "unavailable"
                try:
                    with self.repository.transaction() as conn:
                        self.repository.create_event(
                            conn,
                            session_id=session_id,
                            event_type="provider_exhaustion",
                            backend_type="unavailable",
                            admin_id=admin_id,
                            detail={
                                "primary_provider": primary_provider,
                                "primary_error": primary_error,
                                "attempted_providers": [
                                    c.get("external_provider_key") or c["backend_type"]
                                    for c in fallback_candidates
                                ],
                                "trace_id": trace_id,
                            },
                        )
                except Exception:
                    pass

        text = result["text"]
        sanitized = message_sanitizer.sanitize_message(raw_text=text) if text else {"sanitized_text": "", "truncated": False}

        return {
            "text": sanitized["sanitized_text"],
            "backend_type": result["backend_type"] if result.get("error_message") is None else "unavailable",
            "error_message": result.get("error_message"),
            "truncated": sanitized["truncated"] or truncated_context,
            "external_provider_key": backend.get("external_provider_key"),
            "model": backend.get("model"),
            "stage_latencies": {
                "context_latency_ms": context_ms,
                "generation_latency_ms": generation_ms,
            },
        }

    def grounded_chat(
        self,
        *,
        session_id: str | None,
        message: str,
        retrieval_profile_public_id: str | None,
        top_k: int,
        admin_id: str,
        execution_mode: str = "auto",
        provider_key: str | None = None,
        model_override: str | None = None,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        if not admin_id:
            raise ValidationError("a real admin identity is required to chat")
        trace_id = trace_id or f"trc_{uuid4().hex[:16]}"
        t_start = time.perf_counter()
        record_pilot_metric(self.settings, "widget_grounded_chat_count")
        sanitized = message_sanitizer.sanitize_message(raw_text=message)
        clean_message = sanitized["sanitized_text"]
        from backend.core.json_utils import redact_secrets
        clean_message = redact_secrets(clean_message)
        session_id = self._ensure_session(session_id=session_id, admin_id=admin_id, first_message=clean_message)

        if not clean_message.strip():
            reply_text = "Could you clarify what you'd like help with?"
            saved = self._persist_turn(
                session_id=session_id, admin_id=admin_id, capability="clarify", question=clean_message,
                reply_text=reply_text, backend_type=None, tool_result=None, truncated=False,
                trace_id=trace_id, stage_latencies={"total_latency_ms": round((time.perf_counter() - t_start) * 1000, 2)},
            )
            return {
                "session": self.get_session(session_id), "reply": saved,
                "backend_type": "template", "error_message": None, "citations": [],
                "trace_id": trace_id,
            }

        with self.repository.transaction() as connection:
            history_rows = self.repository.list_messages(connection, session_id=session_id, limit=100, offset=0)

        # Guardrail 8: Deduplicate rapid identical submissions within the same session
        if (
            history_rows
            and len(history_rows) >= 2
            and history_rows[-2]["role"] == "admin"
            and history_rows[-2]["sanitized_text"] == clean_message
            and history_rows[-1]["role"] == "assistant"
        ):
            return {
                "session": self.get_session(session_id),
                "reply": public_message_row(history_rows[-1]),
                "backend_type": history_rows[-1]["backend_type"],
                "error_message": None,
                "citations": [],
                "trace_id": trace_id,
            }

        history = [{"role": row["role"], "content": row["sanitized_text"]} for row in history_rows]

        retrieved_chunks: list[dict[str, Any]] = []
        citations: list[dict[str, Any]] = []
        rag_latency_ms = 0.0
        if retrieval_profile_public_id:
            # Real reuse of the existing retrieval pipeline
            t_rag0 = time.perf_counter()
            retrieval_result = self.retrieval_service.retrieve(
                RetrieveRequest(retrieval_profile_public_id=retrieval_profile_public_id, query=clean_message),
                admin_id,
            )
            rag_latency_ms = round((time.perf_counter() - t_rag0) * 1000, 2)
            retrieved_chunks = retrieval_result["results"][:top_k]
            citations = [
                {
                    "source_public_id": chunk.get("source_public_id", ""),
                    "source_version_public_id": chunk.get("source_version_public_id", ""),
                    "source_name": chunk.get("source_title") or chunk.get("title") or chunk.get("source_public_id", ""),
                    "rank": chunk.get("rank", idx + 1),
                    "score": chunk.get("combined_score", chunk.get("score", 0.0)),
                    "text_preview": (chunk.get("normalized_text") or chunk.get("text", ""))[:280],
                }
                for idx, chunk in enumerate(retrieved_chunks)
            ]

            if citations:
                record_pilot_metric(self.settings, "grounded_chat_citation_render_count")

        outcome = self._generate_grounded_reply(
            capability="chat",
            question=clean_message,
            history=history,
            retrieved_chunks=retrieved_chunks,
            execution_mode=execution_mode,
            provider_key=provider_key,
            model_override=model_override,
            admin_id=admin_id,
            session_id=session_id,
            trace_id=trace_id,
        )
        stage_timings = outcome.get("stage_latencies", {})
        stage_timings["rag_latency_ms"] = rag_latency_ms
        stage_timings["total_latency_ms"] = round((time.perf_counter() - t_start) * 1000, 2)
        reply_text = outcome["text"] or (outcome["error_message"] or "The assistant is unavailable right now.")
        saved = self._persist_turn(
            session_id=session_id, admin_id=admin_id, capability="chat", question=clean_message,
            reply_text=reply_text, backend_type=outcome["backend_type"], tool_result=None, truncated=outcome["truncated"],
            trace_id=trace_id, stage_latencies=stage_timings,
        )
        return {
            "session": self.get_session(session_id), "reply": saved,
            "backend_type": outcome["backend_type"], "error_message": outcome["error_message"],
            "citations": citations,
            "trace_id": trace_id,
        }

    def stream_chat(
        self,
        *,
        session_id: str | None,
        message: str,
        admin_id: str,
        execution_mode: str = "auto",
        provider_key: str | None = None,
        model_override: str | None = None,
        grounded: bool = False,
        retrieval_profile_public_id: str | None = None,
        top_k: int = 4,
        trace_id: str | None = None,
    ):
        """Streaming chat capability yielding SSE event dicts while preserving G1-G6 invariants.

        Yields:
          - start (includes trace_id)
          - metadata (model, backend_type, citations)
          - token (progressive text chunks)
          - done (final token counts / timing / trace_id)
          - error (structured honest error if failed)
        Memory invariant:
          Buffers tokens in memory and persists ONE assistant turn upon completion.
        """
        trace_id = trace_id or f"trc_{uuid4().hex[:16]}"
        t_stream_start = time.perf_counter()
        stage_timings: dict[str, Any] = {}

        if not admin_id:
            yield {"event": "error", "data": {"code": "UNAUTHORIZED", "message": "a real admin identity is required to chat", "retryable": False, "trace_id": trace_id}}
            return

        record_pilot_metric(self.settings, "widget_plain_chat_count" if not grounded else "widget_grounded_chat_count")
        sanitized = message_sanitizer.sanitize_message(raw_text=message)
        clean_message = sanitized["sanitized_text"]
        from backend.core.json_utils import redact_secrets
        clean_message = redact_secrets(clean_message)
        session_id = self._ensure_session(session_id=session_id, admin_id=admin_id, first_message=clean_message)

        yield {"event": "start", "data": {"session_id": session_id, "admin_id": admin_id, "trace_id": trace_id}}

        if not clean_message.strip():
            reply_text = "Could you clarify what you'd like help with?"
            stage_timings["total_duration_ms"] = round((time.perf_counter() - t_stream_start) * 1000, 2)
            saved = self._persist_turn(
                session_id=session_id, admin_id=admin_id, capability="clarify", question=clean_message,
                reply_text=reply_text, backend_type=None, tool_result=None, truncated=False,
                trace_id=trace_id, stage_latencies=stage_timings,
            )
            yield {"event": "metadata", "data": {"model": "template", "backend_type": "template", "citations": []}}
            yield {"event": "token", "data": {"text": reply_text}}
            yield {"event": "done", "data": {"session_id": session_id, "message_id": saved["public_id"], "trace_id": trace_id, "stage_latencies_ms": stage_timings}}
            return

        proposal = self._maybe_propose_governed_action(clean_message, admin_id)
        if proposal is not None:
            reply_text = self._reply_governed_action_proposed(proposal)
            stage_timings["total_duration_ms"] = round((time.perf_counter() - t_stream_start) * 1000, 2)
            saved = self._persist_turn(
                session_id=session_id, admin_id=admin_id, capability="chat",
                question=clean_message, reply_text=reply_text, backend_type=None,
                tool_result=proposal, truncated=False,
                trace_id=trace_id, stage_latencies=stage_timings,
            )
            yield {"event": "metadata", "data": {"model": "governance_bridge", "backend_type": "proposal_bridge", "citations": []}}
            yield {"event": "token", "data": {"text": reply_text}}
            yield {"event": "done", "data": {"session_id": session_id, "message_id": saved["public_id"], "trace_id": trace_id, "stage_latencies_ms": stage_timings}}
            return

        with self.repository.transaction() as connection:
            history_rows = self.repository.list_messages(connection, session_id=session_id, limit=100, offset=0)

        # Deduplication check
        if (
            history_rows
            and len(history_rows) >= 2
            and history_rows[-2]["role"] == "admin"
            and history_rows[-2]["sanitized_text"] == clean_message
            and history_rows[-1]["role"] == "assistant"
        ):
            prior_reply = public_message_row(history_rows[-1])
            yield {"event": "metadata", "data": {"model": "cache_dedup", "backend_type": prior_reply["backend_type"], "citations": []}}
            yield {"event": "token", "data": {"text": prior_reply["sanitized_text"]}}
            yield {"event": "done", "data": {"session_id": session_id, "message_id": prior_reply["public_id"], "trace_id": trace_id}}
            return

        history = [{"role": row["role"], "content": row["sanitized_text"]} for row in history_rows]

        retrieved_chunks: list[dict[str, Any]] = []
        citations: list[dict[str, Any]] = []
        if grounded and retrieval_profile_public_id:
            try:
                t_rag0 = time.perf_counter()
                retrieval_result = self.retrieval_service.retrieve(
                    RetrieveRequest(retrieval_profile_public_id=retrieval_profile_public_id, query=clean_message),
                    admin_id,
                )
                stage_timings["rag_latency_ms"] = round((time.perf_counter() - t_rag0) * 1000, 2)
                retrieved_chunks = retrieval_result.get("results", [])[:top_k]
                citations = [
                    {
                        "source_public_id": chunk.get("source_public_id", ""),
                        "source_version_public_id": chunk.get("source_version_public_id", ""),
                        "source_name": chunk.get("source_title") or chunk.get("title") or chunk.get("source_public_id", ""),
                        "rank": chunk.get("rank", idx + 1),
                        "score": chunk.get("combined_score", chunk.get("score", 0.0)),
                        "text_preview": (chunk.get("normalized_text") or chunk.get("text", ""))[:280],
                    }
                    for idx, chunk in enumerate(retrieved_chunks)
                ]
            except Exception:
                citations = []
                retrieved_chunks = []

        backend = self._resolve_backend(
            execution_mode=execution_mode,
            provider_key=provider_key,
            model_override=model_override,
        )
        adapter = backend["adapter"]
        backend_type = backend["backend_type"]
        model_name = backend.get("model") or "unknown"

        yield {
            "event": "metadata",
            "data": {
                "model": model_name,
                "backend_type": backend_type,
                "citations": citations,
            },
        }

        if adapter is None:
            err_msg = backend.get("reason", "No adapter available")
            yield {"event": "error", "data": {"code": "ADAPTER_UNAVAILABLE", "message": err_msg, "retryable": False, "trace_id": trace_id}}
            return

        style = answer_style_policy.style_for(capability="chat")
        budget = token_budget.compute_budget(context_length=DEFAULT_CONTEXT_LENGTH, max_tokens=DEFAULT_MAX_TOKENS)

        t_ctx0 = time.perf_counter()
        dashboard_ctx = self._get_dashboard_context()
        stage_timings["context_latency_ms"] = round((time.perf_counter() - t_ctx0) * 1000, 2)

        if grounded and retrieved_chunks:
            prompt = prompt_builder.build_grounded_messages(
                system_prompt=style.get("system_prompt", ""), user_message=clean_message,
                retrieved_chunks=retrieved_chunks, dashboard_context=dashboard_ctx,
            )
            messages = [{"role": "system", "content": prompt["system_prompt"]}] + prompt["messages"]
            truncated_context = False
        else:
            context_selection = context_window_manager.select_context_messages(
                messages=history, input_budget_tokens=budget["input_budget_tokens"],
            )
            prompt = prompt_builder.build_prompt(
                style_directives=style, context_messages=context_selection["messages"],
                question=clean_message, dashboard_context=dashboard_ctx,
            )
            messages = [{"role": "system", "content": prompt["system_prompt"]}] + prompt["messages"]
            truncated_context = context_selection["truncated"]

        # Progressive token accumulation buffer for single persistence turn
        token_buffer: list[str] = []
        error_encountered = None
        ttfb_ms: float | None = None

        if hasattr(adapter, "stream_generate"):
            stream_iter = adapter.stream_generate(messages=messages, max_tokens=budget["output_budget_tokens"], temperature=DEFAULT_TEMPERATURE)
            for item in stream_iter:
                if item.get("type") == "token":
                    if ttfb_ms is None:
                        ttfb_ms = round((time.perf_counter() - t_stream_start) * 1000, 2)
                        stage_timings["ttfb_ms"] = ttfb_ms
                    t = item.get("text", "")
                    # Redact potential secrets from token stream in flight
                    t_safe = redact_secrets(t) if isinstance(t, str) else t
                    token_buffer.append(t_safe)
                    yield {"event": "token", "data": {"text": t_safe}}
                elif item.get("type") == "error":
                    error_encountered = item.get("error", "Generation error")
                    break
        else:
            # Fallback to truthful non-streaming generation
            t_gen0 = time.perf_counter()
            res = adapter.generate(messages=messages, max_tokens=budget["output_budget_tokens"], temperature=DEFAULT_TEMPERATURE)
            stage_timings["generation_latency_ms"] = round((time.perf_counter() - t_gen0) * 1000, 2)
            if res.get("error_message"):
                error_encountered = res["error_message"]
            else:
                text = res.get("text", "")
                t_safe = redact_secrets(text) if isinstance(text, str) else text
                if t_safe:
                    token_buffer.append(t_safe)
                    yield {"event": "token", "data": {"text": t_safe}}

        # Failover in auto mode if primary failed before producing tokens
        if error_encountered and not token_buffer and execution_mode == "auto":
            primary_error = error_encountered
            primary_provider = backend.get("external_provider_key") or backend_type
            fallback_candidates = self._list_available_fallback_candidates(
                primary_provider_key=backend.get("external_provider_key"),
                model_override=model_override,
            )
            for candidate in fallback_candidates:
                cand_adapter = candidate["adapter"]
                cand_provider = candidate.get("external_provider_key") or candidate["backend_type"]
                if not cand_adapter.is_available():
                    continue
                try:
                    with self.repository.transaction() as conn:
                        self.repository.create_event(
                            conn,
                            session_id=session_id,
                            event_type="provider_failover",
                            backend_type=candidate["backend_type"],
                            admin_id=admin_id,
                            detail={
                                "from_provider": primary_provider,
                                "to_provider": cand_provider,
                                "failure_reason": primary_error,
                                "trace_id": trace_id,
                            },
                        )
                except Exception:
                    pass

                candidate_err = None
                if hasattr(cand_adapter, "stream_generate"):
                    for item in cand_adapter.stream_generate(messages=messages, max_tokens=budget["output_budget_tokens"], temperature=DEFAULT_TEMPERATURE):
                        if item.get("type") == "token":
                            if ttfb_ms is None:
                                ttfb_ms = round((time.perf_counter() - t_stream_start) * 1000, 2)
                                stage_timings["ttfb_ms"] = ttfb_ms
                            t = item.get("text", "")
                            t_safe = redact_secrets(t) if isinstance(t, str) else t
                            token_buffer.append(t_safe)
                            yield {"event": "token", "data": {"text": t_safe}}
                        elif item.get("type") == "error":
                            candidate_err = item.get("error", "Candidate generation error")
                            break
                else:
                    t_cand0 = time.perf_counter()
                    res = cand_adapter.generate(messages=messages, max_tokens=budget["output_budget_tokens"], temperature=DEFAULT_TEMPERATURE)
                    stage_timings["generation_latency_ms"] = round((time.perf_counter() - t_cand0) * 1000, 2)
                    if res.get("error_message"):
                        candidate_err = res["error_message"]
                    else:
                        text = res.get("text", "")
                        t_safe = redact_secrets(text) if isinstance(text, str) else text
                        if t_safe:
                            token_buffer.append(t_safe)
                            yield {"event": "token", "data": {"text": t_safe}}

                if token_buffer:
                    error_encountered = None
                    backend = candidate
                    backend_type = candidate["backend_type"]
                    break
                else:
                    error_encountered = candidate_err or error_encountered

            if not token_buffer and error_encountered:
                error_encountered = f"PROVIDER_EXHAUSTION: all providers failed or unavailable. Primary error: {primary_error}"
                try:
                    with self.repository.transaction() as conn:
                        self.repository.create_event(
                            conn,
                            session_id=session_id,
                            event_type="provider_exhaustion",
                            backend_type="unavailable",
                            admin_id=admin_id,
                            detail={
                                "primary_provider": primary_provider,
                                "primary_error": primary_error,
                                "attempted_providers": [
                                    c.get("external_provider_key") or c["backend_type"]
                                    for c in fallback_candidates
                                ],
                                "trace_id": trace_id,
                            },
                        )
                except Exception:
                    pass
                yield {"event": "error", "data": {"code": "PROVIDER_EXHAUSTION", "message": error_encountered, "retryable": False, "trace_id": trace_id}}
        elif error_encountered and not token_buffer:
            yield {"event": "error", "data": {"code": "GENERATION_ERROR", "message": error_encountered, "retryable": False, "trace_id": trace_id}}

        full_reply = "".join(token_buffer)
        if not full_reply and error_encountered:
            full_reply = f"Error: {error_encountered}"

        sanitized_final = message_sanitizer.sanitize_message(raw_text=full_reply)
        final_text = sanitized_final["sanitized_text"] or "No response generated."
        final_text = redact_secrets(final_text)

        stage_timings["total_duration_ms"] = round((time.perf_counter() - t_stream_start) * 1000, 2)

        # Persist final turn exactly once
        saved = self._persist_turn(
            session_id=session_id, admin_id=admin_id, capability="chat", question=clean_message,
            reply_text=final_text, backend_type=backend_type, tool_result=None,
            truncated=sanitized_final["truncated"] or truncated_context,
            trace_id=trace_id, stage_latencies=stage_timings,
        )

        yield {
            "event": "done",
            "data": {
                "session_id": session_id,
                "message_id": saved["public_id"],
                "trace_id": trace_id,
                "total_tokens": len(token_buffer),
                "error": error_encountered,
                "stage_latencies_ms": stage_timings,
            },
        }

    # -- MB-42/MB-43: default retrieval profile lookup + admin override -----------

    def _explicit_default_retrieval_profile_public_id(self) -> str | None:
        try:
            setting = self._app_settings_repository.get_safe(DEFAULT_RETRIEVAL_PROFILE_SETTING_KEY)
        except NotFoundError:
            return None
        return setting["value"] or None

    def default_retrieval_profile(self) -> dict[str, Any]:
        """MB-43: first honors an admin-chosen default (stored via
        `set_default_retrieval_profile`) -- but only while that profile
        is still real and still "active"; a profile that was deactivated
        or deleted after being set as default is silently dropped from
        selection rather than ever being returned stale, and this falls
        through to the same MB-42 auto-detection (most recently created
        active profile) as before. Real reuse of the existing
        RagRetrievalService.list_profiles() throughout -- never a new
        query, never a new table for the profiles themselves. Returns
        nulls, never an error, when no active profile exists yet."""

        profiles = self.retrieval_service.list_profiles()["items"]
        explicit_id = self._explicit_default_retrieval_profile_public_id()
        if explicit_id:
            for profile in profiles:
                if profile["public_id"] == explicit_id and profile["status"] == "active":
                    return {"retrieval_profile_public_id": profile["public_id"], "name": profile["name"]}

        for profile in profiles:
            if profile["status"] == "active":
                return {"retrieval_profile_public_id": profile["public_id"], "name": profile["name"]}
        return {"retrieval_profile_public_id": None, "name": None}

    def set_default_retrieval_profile(self, retrieval_profile_public_id: str, admin_id: str) -> dict[str, Any]:
        if not admin_id:
            raise ValidationError("a real admin identity is required to change the default retrieval profile")
        # Real reuse of RagRetrievalService.get_profile() -- the only
        # gate this method enforces: only an already-active profile may
        # become the default (a draft/validated/archived profile cannot
        # be selected, matching what retrieve() itself would refuse).
        profile = self.retrieval_service.get_profile(retrieval_profile_public_id)
        if profile["status"] != "active":
            raise ValidationError("only an active retrieval profile can be set as the default")
        self._app_settings_repository.set(
            DEFAULT_RETRIEVAL_PROFILE_SETTING_KEY, retrieval_profile_public_id, value_type="string",
            description="MB-43: admin-chosen default retrieval profile for grounded chat",
        )
        record_pilot_metric(self.settings, "retrieval_profile_switch_count")
        return self.default_retrieval_profile()

    # -- capability: explain_dashboard_page ---------------------------------------

    def explain_dashboard_page(self, *, session_id: str | None, page_id: str | None, nav_key: str | None, admin_id: str) -> dict[str, Any]:
        session_id = self._ensure_session(session_id=session_id, admin_id=admin_id, first_message=f"Explain page {page_id or nav_key}")
        template = admin_explainer_templates.explain_page(page_id=page_id, nav_key=nav_key)
        if template["found"]:
            # Answered from the deterministic page catalogue -- no LLM
            # backend was consulted, so this is neither "local" nor
            # "external" nor a genuine "unavailable" failure. Not
            # persisted as the message's own backend_type (that column's
            # CHECK constraint only allows local/external/unavailable;
            # None/NULL is stored instead, which is what happens below).
            reply_text = template["explanation"]
            backend_type = None
            error_message = None
            response_backend_type = "template"
        else:
            with self.repository.transaction() as connection:
                history_rows = self.repository.list_messages(connection, session_id=session_id, limit=100, offset=0)
            history = [{"role": row["role"], "content": row["sanitized_text"]} for row in history_rows]
            outcome = self._generate_reply(
                session_id=session_id, capability="explain_page",
                question=f"Explain the dashboard page identified by page_id={page_id!r} nav_key={nav_key!r}.", history=history,
            )
            reply_text = outcome["text"] or "This page is not in the known catalogue and no LLM backend is available to explain it."
            backend_type, error_message = outcome["backend_type"], outcome["error_message"]
            response_backend_type = backend_type
        saved = self._persist_turn(
            session_id=session_id, admin_id=admin_id, capability="explain_page",
            question=f"page_id={page_id} nav_key={nav_key}", reply_text=reply_text,
            backend_type=backend_type, tool_result=None, truncated=False,
        )
        return {"session": self.get_session(session_id), "reply": saved, "backend_type": response_backend_type, "error_message": error_message}

    # -- capability: summarize_phase_report / summarize_regression_results --------

    def summarize_phase_report(self, *, session_id: str | None, report: dict[str, Any], admin_id: str) -> dict[str, Any]:
        facts = report_summarizer.extract_report_facts(report=report)
        facts_text = report_summarizer.build_summary_prompt_facts(facts=facts)
        return self._summarize_facts(session_id=session_id, admin_id=admin_id, capability="summarize_report", facts_text=facts_text)

    def summarize_regression_results(self, *, session_id: str | None, regression_result: dict[str, Any], admin_id: str) -> dict[str, Any]:
        facts = report_summarizer.extract_regression_facts(regression_result=regression_result)
        facts_text = report_summarizer.build_summary_prompt_facts(facts=facts)
        return self._summarize_facts(session_id=session_id, admin_id=admin_id, capability="summarize_regression", facts_text=facts_text)

    def _summarize_facts(self, *, session_id: str | None, admin_id: str, capability: str, facts_text: str) -> dict[str, Any]:
        session_id = self._ensure_session(session_id=session_id, admin_id=admin_id, first_message=f"Summarize: {facts_text[:60]}")
        outcome = self._generate_reply(session_id=session_id, capability=capability, question=facts_text, history=[])
        reply_text = outcome["text"] or facts_text
        saved = self._persist_turn(
            session_id=session_id, admin_id=admin_id, capability=capability, question=facts_text,
            reply_text=reply_text, backend_type=outcome["backend_type"], tool_result=None, truncated=outcome["truncated"],
        )
        return {"session": self.get_session(session_id), "reply": saved, "backend_type": outcome["backend_type"], "error_message": outcome["error_message"]}

    # -- capability: explain_error_message -----------------------------------------

    def explain_error_message(self, *, session_id: str | None, error_message: str, admin_id: str) -> dict[str, Any]:
        session_id = self._ensure_session(session_id=session_id, admin_id=admin_id, first_message=f"Explain error: {error_message[:60]}")
        outcome = self._generate_reply(
            session_id=session_id, capability="explain_error", question=f"Explain this error: {error_message}", history=[],
        )
        reply_text = outcome["text"] or "No LLM backend is available to explain this error right now."
        saved = self._persist_turn(
            session_id=session_id, admin_id=admin_id, capability="explain_error", question=error_message,
            reply_text=reply_text, backend_type=outcome["backend_type"], tool_result=None, truncated=outcome["truncated"],
        )
        return {"session": self.get_session(session_id), "reply": saved, "backend_type": outcome["backend_type"], "error_message": outcome["error_message"]}

    # -- capability: next_actions / propose_next_phase -------------------------------

    def next_actions(self, *, session_id: str | None, status_snapshot: dict[str, Any], admin_id: str) -> dict[str, Any]:
        session_id = self._ensure_session(session_id=session_id, admin_id=admin_id, first_message="Next actions")
        actions = next_action_planner.plan_next_actions(status_snapshot=status_snapshot)

        backend = self._resolve_backend()
        backend_type = backend["backend_type"]
        error_message = None
        if backend["adapter"] is not None:
            style = answer_style_policy.style_for(capability="next_actions")
            prompt = prompt_builder.build_prompt(
                style_directives=style, context_messages=[],
                question="Rephrase these action titles, one per line, in priority order: " + "; ".join(a["title"] for a in actions),
            )
            result = backend["adapter"].generate(messages=[{"role": "system", "content": prompt["system_prompt"]}] + prompt["messages"], max_tokens=200, temperature=DEFAULT_TEMPERATURE)
            if not result.get("error_message") and result["text"]:
                actions = next_action_planner.parse_llm_output(llm_text=result["text"], fallback_actions=actions)
            else:
                error_message = result.get("error_message")
                backend_type = "unavailable" if error_message else backend_type
        else:
            error_message = backend["reason"]

        reply_text = "\n".join(f"- {action['title']} ({action['severity']})" for action in actions)
        saved = self._persist_turn(
            session_id=session_id, admin_id=admin_id, capability="next_actions", question="next actions",
            reply_text=reply_text, backend_type=backend_type if backend["adapter"] is not None else None,
            tool_result={"actions": actions}, truncated=False,
        )
        return {"session": self.get_session(session_id), "reply": saved, "actions": actions, "backend_type": backend_type, "error_message": error_message}


__all__ = ["MiniBrainLlmRuntimeService"]
