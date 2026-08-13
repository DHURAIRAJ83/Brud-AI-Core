"""MB-04C: Model Capability Optimization -- authenticated admin-only
APIs. Independent prefix (`/admin/mini-brain/capability`), separate
from `/admin/mini-brain/runtime`, `/prompt-optimization`, and
`/quality` -- these routes never touch any of them beyond calling
their existing public methods.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.database.repositories.mini_brain_knowledge import MiniBrainKnowledgeRepository
from backend.models.mini_brain_capability import (
    CapabilityAnalyzeRequest,
    CapabilityGenerateRequest,
    CapabilityProfileRequest,
)
from backend.services.mini_brain_capability_service import MiniBrainCapabilityService
from backend.services.mini_brain_intelligence_service import MiniBrainIntelligenceService
from backend.services.mini_brain_prompt_optimization_service import MiniBrainPromptOptimizationService
from backend.services.mini_brain_runtime_manager_service import MiniBrainInMemoryModelLoader
from core_model.mini_brain.capability.model_profiles import list_profiles

router = APIRouter(
    prefix="/admin/mini-brain/capability",
    tags=["admin-mini-brain-capability"],
    dependencies=[Depends(require_admin)],
)


def service(settings) -> MiniBrainCapabilityService:
    repo = MiniBrainKnowledgeRepository(settings.resolved_database_path)
    prompt_optimization = MiniBrainPromptOptimizationService(
        repo, MiniBrainIntelligenceService(repo, settings), MiniBrainInMemoryModelLoader(), settings,
    )
    return MiniBrainCapabilityService(prompt_optimization)


@router.post("/analyze")
async def analyze(payload: CapabilityAnalyzeRequest, settings: SettingsDependency, admin: CsrfDependency):
    result = service(settings).analyze(payload.question)
    return {
        "category": result["category"], "strategy": result["strategy"], "profile": result["profile"],
        "response_plan": result["built"]["response_plan"],
    }


@router.post("/generate")
async def generate(payload: CapabilityGenerateRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).generate(payload.question, timeout_seconds=payload.timeout_seconds)


@router.post("/profile")
async def profile(payload: CapabilityProfileRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).profile_for(payload.model_name, payload.quantization)


@router.get("/models")
async def models():
    return {"profiles": list_profiles()}


@router.get("/diagnostics")
async def diagnostics(settings: SettingsDependency):
    return service(settings).diagnostics()
