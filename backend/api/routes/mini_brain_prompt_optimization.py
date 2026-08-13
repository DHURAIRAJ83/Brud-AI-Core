"""MB-04A: Prompt & Context Optimization -- authenticated admin-only
APIs. Independent prefix (`/admin/mini-brain/prompt-optimization`),
separate from MB-04's own `/admin/mini-brain/runtime` routes -- the
Runtime Manager itself is unchanged; this is a new orchestration layer
in front of it.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.database.repositories.mini_brain_knowledge import MiniBrainKnowledgeRepository
from backend.models.mini_brain_prompt_optimization import LanguageDetectRequest, PromptOptimizeRequest
from backend.services.mini_brain_intelligence_service import MiniBrainIntelligenceService
from backend.services.mini_brain_prompt_optimization_service import MiniBrainPromptOptimizationService
from backend.services.mini_brain_runtime_manager_service import MiniBrainInMemoryModelLoader
from backend.services.pilot_metrics import record_pilot_metric
from core_model.mini_brain.prompting.prompt_templates import TEMPLATES
from core_model.mini_brain.prompting.response_validator import validate_response

router = APIRouter(
    prefix="/admin/mini-brain/prompt-optimization",
    tags=["admin-mini-brain-prompt-optimization"],
    dependencies=[Depends(require_admin)],
)


def service(settings) -> MiniBrainPromptOptimizationService:
    repo = MiniBrainKnowledgeRepository(settings.resolved_database_path)
    return MiniBrainPromptOptimizationService(
        repo, MiniBrainIntelligenceService(repo, settings), MiniBrainInMemoryModelLoader(), settings,
    )


@router.post("/language-detect")
async def language_detect(payload: LanguageDetectRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).language_detect(payload.question)


@router.get("/templates")
async def templates():
    return {"templates": TEMPLATES}


@router.post("/generate")
async def generate(payload: PromptOptimizeRequest, settings: SettingsDependency, admin: CsrfDependency):
    result = service(settings).optimize_and_generate(
        payload.question, max_tokens=payload.max_tokens, timeout_seconds=payload.timeout_seconds,
        knowledge_budget_chars=payload.knowledge_budget_chars,
    )
    record_pilot_metric(settings, "prompt_optimization_run_count")
    return result


@router.post("/compare")
async def compare(payload: PromptOptimizeRequest, settings: SettingsDependency, admin: CsrfDependency):
    """MB-04.1 baseline (unchanged `_build_prompt()`, no optimization)
    vs MB-04A optimized, run back to back against the same currently
    loaded model and the same Response Plan, for the benchmark this
    phase's own report requires."""

    svc = service(settings)
    built = svc.build_optimized_prompt(payload.question, knowledge_budget_chars=payload.knowledge_budget_chars)

    t0 = time.perf_counter()
    baseline = svc.runtime_manager.generate_response(
        built["response_plan"], max_tokens=payload.max_tokens, timeout_seconds=payload.timeout_seconds,
    )
    baseline_seconds = round(time.perf_counter() - t0, 3)

    t0 = time.perf_counter()
    optimized = svc.runtime_manager.generate_response(
        built["response_plan"], max_tokens=payload.max_tokens, timeout_seconds=payload.timeout_seconds,
        prebuilt_prompt=built["prompt"],
    )
    optimized_seconds = round(time.perf_counter() - t0, 3)

    optimized_validation = validate_response(
        optimized["text"], expected_output_language=built["output_language"],
        confidence_band=built["response_plan"]["confidence_band"],
    )
    baseline_validation = validate_response(
        baseline["text"], expected_output_language=built["output_language"],
        confidence_band=built["response_plan"]["confidence_band"],
    )

    record_pilot_metric(settings, "prompt_optimization_run_count")
    return {
        "question": payload.question,
        "language_analysis": built["language_analysis"],
        "output_language": built["output_language"],
        "template_category": built["template_category"],
        "baseline": {
            "prompt_length_chars": baseline["generation_stats"]["prompt_size_chars"],
            "response": baseline,
            "response_length_chars": len(baseline["text"]),
            "seconds": baseline_seconds,
            "validation": baseline_validation,
        },
        "optimized": {
            "prompt_length_chars": len(built["prompt"]),
            "response": optimized,
            "response_length_chars": len(optimized["text"]),
            "seconds": optimized_seconds,
            "validation": optimized_validation,
        },
    }
