"""Top-level API router."""

from fastapi import APIRouter

from backend.api.routes import (
    admin,
    auth,
    base_training,
    chat,
    conversation_memory,
    core_models,
    corpus,
    datasets,
    documents,
    feedback,
    health,
    imports,
    inference_runtime,
    instruction_tuning,
    model_evaluation,
    model_release,
    pretraining,
    pretraining_readiness,
    rag,
    system,
    tokenizers,
    training_reliability,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(chat.router)
api_router.include_router(auth.router)
api_router.include_router(admin.router)
api_router.include_router(system.router)
api_router.include_router(imports.router)
api_router.include_router(documents.router)
api_router.include_router(datasets.router)
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
