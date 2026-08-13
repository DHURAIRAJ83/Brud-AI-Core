"""MB-03: Brud Intelligence Engine -- authenticated admin-only APIs.

Every stage endpoint below runs the exact same underlying pipeline
(`MiniBrainIntelligenceService.analyze`) and returns just that stage's
slice of the result -- one pipeline implementation, never eight
divergent ones. `POST` is used throughout (never `GET`) to match this
codebase's own established convention that every POST admin route,
computation-only or not, requires CSRF (see
`deterministic_tools_admin.py`'s own `/test` endpoint for precedent).
"""

from fastapi import APIRouter, Depends

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.database.repositories.mini_brain_knowledge import MiniBrainKnowledgeRepository
from backend.models.mini_brain_intelligence import QuestionAnalyzeRequest
from backend.services.mini_brain_intelligence_service import MiniBrainIntelligenceService

router = APIRouter(
    prefix="/admin/mini-brain/intelligence",
    tags=["admin-mini-brain-intelligence"],
    dependencies=[Depends(require_admin)],
)


def service(settings) -> MiniBrainIntelligenceService:
    return MiniBrainIntelligenceService(
        MiniBrainKnowledgeRepository(settings.resolved_database_path), settings
    )


@router.post("/analyze")
async def analyze(payload: QuestionAnalyzeRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).analyze(payload.question)


@router.post("/question-analysis")
async def question_analysis(payload: QuestionAnalyzeRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).analyze(payload.question)["question_analysis"]


@router.post("/intent")
async def intent(payload: QuestionAnalyzeRequest, settings: SettingsDependency, admin: CsrfDependency):
    result = service(settings).analyze(payload.question)
    qa = result["question_analysis"]
    return {"intent": qa["intent"], "confidence_signal": qa["intent_confidence_signal"]}


@router.post("/context")
async def context(payload: QuestionAnalyzeRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).analyze(payload.question)["context"]


@router.post("/workflow")
async def workflow(payload: QuestionAnalyzeRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).analyze(payload.question)["workflow"]


@router.post("/features")
async def features(payload: QuestionAnalyzeRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).analyze(payload.question)["features"]


@router.post("/knowledge-plan")
async def knowledge_plan(payload: QuestionAnalyzeRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).analyze(payload.question)["knowledge_plan"]


@router.post("/response-plan")
async def response_plan(payload: QuestionAnalyzeRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).analyze(payload.question)["response_plan"]


@router.post("/diagnostics")
async def diagnostics(payload: QuestionAnalyzeRequest, settings: SettingsDependency, admin: CsrfDependency):
    """Per-question diagnostics (processing time, candidate counts).
    Requires a question because MB-03 keeps no history -- there is no
    engine-wide state to report on independent of a specific run."""

    return service(settings).analyze(payload.question)["diagnostics"]
