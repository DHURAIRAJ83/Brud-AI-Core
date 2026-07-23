"""Top-level API router."""

from fastapi import APIRouter

from backend.api.routes import (
    admin,
    auth,
    base_training,
    chat,
    core_models,
    datasets,
    documents,
    health,
    imports,
    instruction_tuning,
    pretraining,
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
