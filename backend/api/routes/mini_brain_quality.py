"""MB-04B: Response Quality Engine -- authenticated admin-only APIs.

Independent prefix (`/admin/mini-brain/quality`), separate from
`/admin/mini-brain/runtime` and `/admin/mini-brain/prompt-optimization`
-- these routes never touch either. The 5 endpoints the task named are
check/validate/report/format/diagnostics; `/generate` is one disclosed
addition beyond that list, added because without it the phase's own
"sits after generation, before the final response" architecture claim
is never actually demonstrated end-to-end through the API.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.database.repositories.mini_brain_knowledge import MiniBrainKnowledgeRepository
from backend.models.mini_brain_quality import QualityCheckRequest, QualityFormatRequest, QualityGenerateRequest
from backend.services.mini_brain_intelligence_service import MiniBrainIntelligenceService
from backend.services.mini_brain_prompt_optimization_service import MiniBrainPromptOptimizationService
from backend.services.mini_brain_quality_service import MiniBrainQualityService
from backend.services.mini_brain_runtime_manager_service import MiniBrainInMemoryModelLoader
from core_model.mini_brain.quality.response_formatter import format_response_text

router = APIRouter(
    prefix="/admin/mini-brain/quality",
    tags=["admin-mini-brain-quality"],
    dependencies=[Depends(require_admin)],
)


def service(settings) -> MiniBrainQualityService:
    repo = MiniBrainKnowledgeRepository(settings.resolved_database_path)
    prompt_optimization = MiniBrainPromptOptimizationService(
        repo, MiniBrainIntelligenceService(repo, settings), MiniBrainInMemoryModelLoader(), settings,
    )
    return MiniBrainQualityService(prompt_optimization)


@router.post("/check")
async def check(payload: QualityCheckRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).check(
        payload.response_text, prompt_text=payload.prompt_text,
        expected_output_language=payload.expected_output_language,
        response_plan=payload.response_plan, final_response=payload.final_response,
    )


@router.post("/validate")
async def validate(payload: QualityCheckRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).validate_only(
        payload.response_text, prompt_text=payload.prompt_text,
        expected_output_language=payload.expected_output_language,
        response_plan=payload.response_plan, final_response=payload.final_response,
    )


@router.post("/report")
async def report(payload: QualityCheckRequest, settings: SettingsDependency, admin: CsrfDependency):
    result = service(settings).check(
        payload.response_text, prompt_text=payload.prompt_text,
        expected_output_language=payload.expected_output_language,
        response_plan=payload.response_plan, final_response=payload.final_response,
    )
    warnings = []
    if result["echo"]["severity"] == "partial":
        warnings.append("response contains a partial verbatim overlap with the prompt")
    if result["tamil_fluency"] and not result["tamil_fluency"]["passed"]:
        warnings.append("Tamil script-level quality issues detected")

    issues = []
    if result["echo"]["severity"] == "dominant":
        issues.append("response is dominated by echoed prompt text, not a real answer")
    if not result["language"]["matches_expectation"]:
        issues.append("response language does not match the expected output language")
    if not result["consistency"]["passed"]:
        issues.extend(result["consistency"]["issues"])

    return {
        "issues_found": issues,
        "warnings": warnings,
        "quality_score": result["quality_score"],
        "processing_time_ms": result["processing_time_ms"],
        "actions_performed": result["actions_performed"],
    }


@router.post("/format")
async def format_text(payload: QualityFormatRequest, admin: CsrfDependency):
    return format_response_text(payload.text)


@router.post("/generate")
async def generate(payload: QualityGenerateRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).generate_and_check(
        payload.question, max_tokens=payload.max_tokens, timeout_seconds=payload.timeout_seconds,
        knowledge_budget_chars=payload.knowledge_budget_chars,
    )


@router.get("/diagnostics")
async def diagnostics(settings: SettingsDependency):
    return service(settings).diagnostics()
