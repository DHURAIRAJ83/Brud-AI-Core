"""Declarative registry of route plugins for backend.api.router.

Each RoutePlugin describes one `include_router()` call. This file holds
only data (ROUTE_PLUGINS) and the loader that walks it -- no
deployment-mode filtering lives here yet (that is Phase 5D-C Commit 2).

The registry is a single explicit list, not filesystem discovery
(pkgutil.iter_modules), so adding a route module always requires a
reviewable, one-line decision about its `public`/`enabled_by_default`
classification rather than being picked up implicitly.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Tuple

if TYPE_CHECKING:
    from fastapi import APIRouter


@dataclass(frozen=True)
class RoutePlugin:
    name: str
    public: bool
    enabled_by_default: bool
    import_path: str
    router_attr: str = "router"
    tags: Tuple[str, ...] = ()


def _get_registered_plugin_names(api_router) -> set[str]:
    names = getattr(api_router, "_brud_registered_plugins", None)
    if names is None:
        names = set()
        setattr(api_router, "_brud_registered_plugins", names)
    return names


def should_load_plugin(plugin: RoutePlugin, mode: str) -> bool:
    if mode in ("dev", "admin"):
        return True
    if mode == "public":
        return plugin.public
    if mode == "worker":
        return plugin.name in {"auth", "health"}
    raise ValueError(f"Unknown deployment mode: {mode}")


ROUTE_PLUGINS: Tuple[RoutePlugin, ...] = (
    # -- Public APIs (must remain eager, per Phase 5D-C hard constraints) --
    RoutePlugin("health", True, True, "backend.api.routes.health", tags=("public", "health")),
    RoutePlugin("chat", True, True, "backend.api.routes.chat", tags=("public",)),
    RoutePlugin("public_chat_runtime", True, True, "backend.api.routes.public_chat_runtime", tags=("public",)),
    RoutePlugin("public_plugin_policy", True, True, "backend.api.routes.public_plugin_policy", tags=("public",)),
    RoutePlugin("public_plugin_runtime", True, True, "backend.api.routes.public_plugin_runtime", tags=("public",)),
    RoutePlugin("public_voice_runtime", True, True, "backend.api.routes.public_voice_runtime", tags=("public",)),
    RoutePlugin("auth", True, True, "backend.api.routes.auth", tags=("public", "auth")),
    RoutePlugin("rag", True, True, "backend.api.routes.rag", tags=("public", "rag")),

    # -- Remaining admin tools (currently eager, never deferred by any
    # prior phase; admin-only per Phase 5D-C Step 1's classification) --
    RoutePlugin("admin", False, True, "backend.api.routes.admin", tags=("admin",)),
    RoutePlugin("admin_assistant", False, True, "backend.api.routes.admin_assistant", tags=("admin",)),
    RoutePlugin("external_gateway_dataset_bridge", False, True, "backend.api.routes.external_gateway_dataset_bridge", tags=("admin",)),
    RoutePlugin("system", False, True, "backend.api.routes.system", tags=("admin",)),
    RoutePlugin("imports", False, True, "backend.api.routes.imports", tags=("admin",)),
    RoutePlugin("tokenizers", False, True, "backend.api.routes.tokenizers", tags=("admin",)),
    RoutePlugin("core_models", False, True, "backend.api.routes.core_models", tags=("admin",)),
    RoutePlugin("pretraining", False, True, "backend.api.routes.pretraining", tags=("admin", "training")),
    RoutePlugin("training_reliability", False, True, "backend.api.routes.training_reliability", tags=("admin", "training")),
    RoutePlugin("base_training", False, True, "backend.api.routes.base_training", tags=("admin", "training")),
    RoutePlugin("instruction_tuning", False, True, "backend.api.routes.instruction_tuning", tags=("admin", "training")),
    RoutePlugin("model_evaluation", False, True, "backend.api.routes.model_evaluation", tags=("admin", "training")),
    RoutePlugin("model_release", False, True, "backend.api.routes.model_release", tags=("admin", "training")),
    RoutePlugin("inference_runtime", False, True, "backend.api.routes.inference_runtime", tags=("admin",)),
    RoutePlugin("conversation_memory", False, True, "backend.api.routes.conversation_memory", tags=("admin",)),
    RoutePlugin("feedback", False, True, "backend.api.routes.feedback", tags=("admin",)),
    RoutePlugin("corpus", False, True, "backend.api.routes.corpus", tags=("admin",)),
    RoutePlugin("pretraining_readiness", False, True, "backend.api.routes.pretraining_readiness", tags=("admin", "training")),
    RoutePlugin("data_sources", False, True, "backend.api.routes.data_sources", tags=("admin",)),
    RoutePlugin("manual_data", False, True, "backend.api.routes.manual_data", tags=("admin",)),
    RoutePlugin("semantic_chunks", False, True, "backend.api.routes.semantic_chunks", tags=("admin",)),
    RoutePlugin("structured_records", False, True, "backend.api.routes.structured_records", tags=("admin",)),
    RoutePlugin("governance", False, True, "backend.api.routes.governance", tags=("admin",)),
    RoutePlugin("governed_builds", False, True, "backend.api.routes.governed_builds", tags=("admin",)),
    RoutePlugin("data_lineage", False, True, "backend.api.routes.data_lineage", tags=("admin",)),
    RoutePlugin("external_data_providers", False, True, "backend.api.routes.external_data_providers", tags=("admin",)),
    RoutePlugin("incremental_training", False, True, "backend.api.routes.incremental_training", tags=("admin", "training")),
    RoutePlugin("knowledge_routing", False, True, "backend.api.routes.knowledge_routing", tags=("admin",)),
    RoutePlugin("knowledge_gap_admin", False, True, "backend.api.routes.knowledge_gap_admin", tags=("admin",)),
    RoutePlugin("public_chat_admin", False, True, "backend.api.routes.public_chat_admin", tags=("admin",)),
    RoutePlugin("trusted_web_admin", False, True, "backend.api.routes.trusted_web_admin", tags=("admin",)),
    RoutePlugin("deterministic_tools_admin", False, True, "backend.api.routes.deterministic_tools_admin", tags=("admin",)),

    # -- Dataset/document admin tooling (deferred by BRUD_DEFER_ADMIN_TOOL_ROUTES
    # since Phase 5D-B) --
    RoutePlugin("documents", False, False, "backend.api.routes.documents", tags=("admin", "document")),
    RoutePlugin("documents_tamil_correction_rules", False, False, "backend.api.routes.documents", router_attr="tamil_correction_rules_router", tags=("admin", "document")),
    RoutePlugin("datasets", False, False, "backend.api.routes.datasets", tags=("admin", "dataset")),
    RoutePlugin("dataset_discovery", False, False, "backend.api.routes.dataset_discovery", tags=("admin", "dataset")),
    RoutePlugin("dataset_verification", False, False, "backend.api.routes.dataset_verification", tags=("admin", "dataset")),
    RoutePlugin("dataset_sample_import", False, False, "backend.api.routes.dataset_sample_import", tags=("admin", "dataset")),

    # -- Mini Brain admin tooling (deferred by BRUD_DEFER_ADMIN_TOOL_ROUTES
    # since Phase 5D-A) --
    RoutePlugin("mini_brain", False, False, "backend.api.routes.mini_brain", tags=("admin", "mini_brain")),
    RoutePlugin("mini_brain_knowledge", False, False, "backend.api.routes.mini_brain_knowledge", tags=("admin", "mini_brain")),
    RoutePlugin("mini_brain_intelligence", False, False, "backend.api.routes.mini_brain_intelligence", tags=("admin", "mini_brain")),
    RoutePlugin("mini_brain_runtime", False, False, "backend.api.routes.mini_brain_runtime", tags=("admin", "mini_brain")),
    RoutePlugin("mini_brain_prompt_optimization", False, False, "backend.api.routes.mini_brain_prompt_optimization", tags=("admin", "mini_brain")),
    RoutePlugin("mini_brain_quality", False, False, "backend.api.routes.mini_brain_quality", tags=("admin", "mini_brain")),
    RoutePlugin("mini_brain_capability", False, False, "backend.api.routes.mini_brain_capability", tags=("admin", "mini_brain")),
    RoutePlugin("mini_brain_dataset_intelligence", False, False, "backend.api.routes.mini_brain_dataset_intelligence", tags=("admin", "mini_brain")),
    RoutePlugin("mini_brain_advanced_dataset", False, False, "backend.api.routes.mini_brain_advanced_dataset", tags=("admin", "mini_brain")),
    RoutePlugin("mini_brain_learning_supervisor", False, False, "backend.api.routes.mini_brain_learning_supervisor", tags=("admin", "mini_brain")),
    RoutePlugin("mini_brain_release_pipeline", False, False, "backend.api.routes.mini_brain_release_pipeline", tags=("admin", "mini_brain")),
    RoutePlugin("mini_brain_continuous_learning", False, False, "backend.api.routes.mini_brain_continuous_learning", tags=("admin", "mini_brain")),
    RoutePlugin("mini_brain_continuous_learning_center", False, False, "backend.api.routes.mini_brain_continuous_learning_center", tags=("admin", "mini_brain")),
    RoutePlugin("mini_brain_research_center", False, False, "backend.api.routes.mini_brain_research_center", tags=("admin", "mini_brain")),
    RoutePlugin("mini_brain_dataset_evolution", False, False, "backend.api.routes.mini_brain_dataset_evolution", tags=("admin", "mini_brain")),
    RoutePlugin("mini_brain_pipeline_coordinator", False, False, "backend.api.routes.mini_brain_pipeline_coordinator", tags=("admin", "mini_brain")),
    RoutePlugin("mini_brain_language_intelligence", False, False, "backend.api.routes.mini_brain_language_intelligence", tags=("admin", "mini_brain")),
    RoutePlugin("mini_brain_vision_intelligence", False, False, "backend.api.routes.mini_brain_vision_intelligence", tags=("admin", "mini_brain")),
    RoutePlugin("mini_brain_vision_model", False, False, "backend.api.routes.mini_brain_vision_model", tags=("admin", "mini_brain")),
    RoutePlugin("mini_brain_multimodal_dataset_generator", False, False, "backend.api.routes.mini_brain_multimodal_dataset_generator", tags=("admin", "mini_brain")),
    RoutePlugin("mini_brain_vision_rag", False, False, "backend.api.routes.mini_brain_vision_rag", tags=("admin", "mini_brain")),
    RoutePlugin("mini_brain_training_pipeline", False, False, "backend.api.routes.mini_brain_training_pipeline", tags=("admin", "mini_brain")),
    RoutePlugin("mini_brain_evaluation_center", False, False, "backend.api.routes.mini_brain_evaluation_center", tags=("admin", "mini_brain")),
    RoutePlugin("mini_brain_release_governance", False, False, "backend.api.routes.mini_brain_release_governance", tags=("admin", "mini_brain")),
    RoutePlugin("mini_brain_external_ai_gateway", False, False, "backend.api.routes.mini_brain_external_ai_gateway", tags=("admin", "mini_brain")),
    RoutePlugin("mini_brain_training_engine", False, False, "backend.api.routes.mini_brain_training_engine", tags=("admin", "mini_brain")),
    RoutePlugin("mini_brain_public_chat_runtime", False, False, "backend.api.routes.mini_brain_public_chat_runtime", tags=("admin", "mini_brain")),
    RoutePlugin("mini_brain_plugin_governance", False, False, "backend.api.routes.mini_brain_plugin_governance", tags=("admin", "mini_brain")),
    RoutePlugin("mini_brain_plugin_runtime", False, False, "backend.api.routes.mini_brain_plugin_runtime", tags=("admin", "mini_brain")),
    RoutePlugin("mini_brain_voice_runtime", False, False, "backend.api.routes.mini_brain_voice_runtime", tags=("admin", "mini_brain")),
    RoutePlugin("mini_brain_provider_settings", False, False, "backend.api.routes.mini_brain_provider_settings", tags=("admin", "mini_brain")),
    RoutePlugin("mini_brain_llm_runtime", False, False, "backend.api.routes.mini_brain_llm_runtime", tags=("admin", "mini_brain")),
    RoutePlugin("mini_brain_local_setup", False, False, "backend.api.routes.mini_brain_local_setup", tags=("admin", "mini_brain")),
    RoutePlugin("mini_brain_runtime_manager", False, False, "backend.api.routes.mini_brain_runtime_manager", tags=("admin", "mini_brain")),
    RoutePlugin("mini_brain_health", False, False, "backend.api.routes.mini_brain_health", tags=("admin", "mini_brain")),
    RoutePlugin("production_readiness", False, False, "backend.api.routes.production_readiness", tags=("admin", "production_readiness")),
    RoutePlugin("rag_sandbox", False, False, "backend.api.routes.rag_sandbox", tags=("admin", "rag_sandbox")),
)


def load_plugins(
    api_router: "APIRouter",
    mode: str = "dev",
    plugins: Tuple[RoutePlugin, ...] = None,
) -> None:
    """Register every plugin in `plugins` that passes `should_load_plugin`
    for the given `mode` onto `api_router`.

    Imports are lazy (inside the loop) so callers -- or a mode filter --
    that skip a subset only pay the import cost for what actually loads.
    `plugins` defaults to the full ROUTE_PLUGINS registry; callers may
    still pass a pre-filtered subset (see backend/api/router.py for the
    eager/deferred split preserved from Phase 5D-A/5D-B).
    """

    if plugins is None:
        plugins = ROUTE_PLUGINS

    seen = _get_registered_plugin_names(api_router)
    for plugin in plugins:
        if not should_load_plugin(plugin, mode):
            continue
        if plugin.name in seen:
            raise RuntimeError(f"duplicate route plugin name: {plugin.name!r}")
        seen.add(plugin.name)
        module = importlib.import_module(plugin.import_path)
        api_router.include_router(getattr(module, plugin.router_attr))
