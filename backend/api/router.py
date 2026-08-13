"""Top-level API router."""

from fastapi import APIRouter

from backend.api.routes import (
    admin,
    admin_assistant,
    auth,
    base_training,
    chat,
    conversation_memory,
    core_models,
    corpus,
    data_lineage,
    data_sources,
    deterministic_tools_admin,
    external_data_providers,
    external_gateway_dataset_bridge,
    feedback,
    governance,
    governed_builds,
    health,
    imports,
    incremental_training,
    inference_runtime,
    instruction_tuning,
    knowledge_gap_admin,
    knowledge_routing,
    manual_data,
    model_evaluation,
    model_release,
    pretraining,
    pretraining_readiness,
    public_chat_admin,
    public_chat_runtime,
    public_plugin_policy,
    public_plugin_runtime,
    public_voice_runtime,
    rag,
    semantic_chunks,
    structured_records,
    system,
    tokenizers,
    training_reliability,
    trusted_web_admin,
)
from backend.core.config import get_settings

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(chat.router)
api_router.include_router(public_chat_runtime.router)
api_router.include_router(public_plugin_policy.router)
api_router.include_router(public_plugin_runtime.router)
api_router.include_router(public_voice_runtime.router)
api_router.include_router(auth.router)
api_router.include_router(admin.router)
api_router.include_router(admin_assistant.router)
api_router.include_router(external_gateway_dataset_bridge.router)
api_router.include_router(system.router)
api_router.include_router(imports.router)
api_router.include_router(tokenizers.router)
api_router.include_router(core_models.router)
api_router.include_router(pretraining.router)
api_router.include_router(training_reliability.router)
api_router.include_router(base_training.router)
api_router.include_router(instruction_tuning.router)
api_router.include_router(model_evaluation.router)
api_router.include_router(model_release.router)
api_router.include_router(inference_runtime.router)
api_router.include_router(rag.router)
api_router.include_router(conversation_memory.router)
api_router.include_router(feedback.router)
api_router.include_router(corpus.router)
api_router.include_router(pretraining_readiness.router)
api_router.include_router(data_sources.router)
api_router.include_router(manual_data.router)
api_router.include_router(semantic_chunks.router)
api_router.include_router(structured_records.router)
api_router.include_router(governance.router)
api_router.include_router(governed_builds.router)
api_router.include_router(data_lineage.router)
api_router.include_router(external_data_providers.router)
api_router.include_router(incremental_training.router)
api_router.include_router(knowledge_routing.router)
api_router.include_router(knowledge_gap_admin.router)
api_router.include_router(public_chat_admin.router)
api_router.include_router(trusted_web_admin.router)
api_router.include_router(deterministic_tools_admin.router)


# Phase 5D-A/5D-B: Mini Brain, Production Readiness, RAG Sandbox, and the
# dataset/document admin-management routes are admin-only tooling -- never
# reached by the public chatbot/voice runtime -- so their route modules
# (and the module-level imports that trigger, e.g. torch via some Mini
# Brain services) can be registered lazily instead of unconditionally at
# process startup. This is purely a registration-time optimization: once
# registered (eagerly here, or later via register_deferred_admin_routes()),
# these routes behave identically -- same prefixes, tags, dependencies,
# and paths.
def _register_admin_tool_routes(router: APIRouter) -> None:
    from backend.api.routes import (
        dataset_discovery,
        dataset_sample_import,
        dataset_verification,
        datasets,
        documents,
        mini_brain,
        mini_brain_advanced_dataset,
        mini_brain_capability,
        mini_brain_continuous_learning,
        mini_brain_continuous_learning_center,
        mini_brain_dataset_evolution,
        mini_brain_dataset_intelligence,
        mini_brain_evaluation_center,
        mini_brain_external_ai_gateway,
        mini_brain_health,
        mini_brain_intelligence,
        mini_brain_knowledge,
        mini_brain_language_intelligence,
        mini_brain_learning_supervisor,
        mini_brain_llm_runtime,
        mini_brain_local_setup,
        mini_brain_multimodal_dataset_generator,
        mini_brain_pipeline_coordinator,
        mini_brain_plugin_governance,
        mini_brain_plugin_runtime,
        mini_brain_prompt_optimization,
        mini_brain_provider_settings,
        mini_brain_public_chat_runtime,
        mini_brain_quality,
        mini_brain_release_governance,
        mini_brain_release_pipeline,
        mini_brain_research_center,
        mini_brain_runtime,
        mini_brain_runtime_manager,
        mini_brain_training_engine,
        mini_brain_training_pipeline,
        mini_brain_vision_intelligence,
        mini_brain_vision_model,
        mini_brain_vision_rag,
        mini_brain_voice_runtime,
        production_readiness,
        rag_sandbox,
    )

    router.include_router(documents.router)
    router.include_router(documents.tamil_correction_rules_router)
    router.include_router(datasets.router)
    router.include_router(dataset_discovery.router)
    router.include_router(dataset_verification.router)
    router.include_router(dataset_sample_import.router)
    router.include_router(mini_brain.router)
    router.include_router(mini_brain_knowledge.router)
    router.include_router(mini_brain_intelligence.router)
    router.include_router(mini_brain_runtime.router)
    router.include_router(mini_brain_prompt_optimization.router)
    router.include_router(mini_brain_quality.router)
    router.include_router(mini_brain_capability.router)
    router.include_router(mini_brain_dataset_intelligence.router)
    router.include_router(mini_brain_advanced_dataset.router)
    router.include_router(mini_brain_learning_supervisor.router)
    router.include_router(mini_brain_release_pipeline.router)
    router.include_router(mini_brain_continuous_learning.router)
    router.include_router(mini_brain_continuous_learning_center.router)
    router.include_router(mini_brain_research_center.router)
    router.include_router(mini_brain_dataset_evolution.router)
    router.include_router(mini_brain_pipeline_coordinator.router)
    router.include_router(mini_brain_language_intelligence.router)
    router.include_router(mini_brain_vision_intelligence.router)
    router.include_router(mini_brain_vision_model.router)
    router.include_router(mini_brain_multimodal_dataset_generator.router)
    router.include_router(mini_brain_vision_rag.router)
    router.include_router(mini_brain_training_pipeline.router)
    router.include_router(mini_brain_evaluation_center.router)
    router.include_router(mini_brain_release_governance.router)
    router.include_router(mini_brain_external_ai_gateway.router)
    router.include_router(mini_brain_training_engine.router)
    router.include_router(mini_brain_public_chat_runtime.router)
    router.include_router(mini_brain_plugin_governance.router)
    router.include_router(mini_brain_plugin_runtime.router)
    router.include_router(mini_brain_voice_runtime.router)
    router.include_router(mini_brain_provider_settings.router)
    router.include_router(mini_brain_llm_runtime.router)
    router.include_router(mini_brain_local_setup.router)
    router.include_router(mini_brain_runtime_manager.router)
    router.include_router(mini_brain_health.router)
    router.include_router(production_readiness.router)
    router.include_router(rag_sandbox.router)


if get_settings().defer_admin_tool_routes is False:
    _register_admin_tool_routes(api_router)


def register_deferred_admin_routes() -> None:
    """Explicit opt-in hook for a future admin-only startup path.

    When BRUD_DEFER_ADMIN_TOOL_ROUTES=true, Mini Brain / Production
    Readiness / RAG Sandbox / dataset & document admin routes are not
    registered above -- call this once, before serving traffic, to
    register them on demand instead.
    """

    _register_admin_tool_routes(api_router)
