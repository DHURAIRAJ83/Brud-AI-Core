"""MB-13: Brud Mini Brain Language Intelligence & Dataset Normalization
Center -- authenticated admin-only APIs. Independent prefix
(`/admin/mini-brain/language-intelligence`), separate from every
system this phase reads from (Dataset Studio, MB-05, the Document
Tamil Correction Registry, the duplicate-detection service). No route
here writes a dataset record, starts training, deploys a model, or
calls RAG Sandbox -- every mutating route only ever writes to MB-13's
own tables.

Each workflow stage gets its own independently-callable route,
mirroring the precedent set by MB-06/MB-09/MB-10/MB-11/MB-12, so every
stage is independently testable.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.models.mini_brain_language_intelligence import (
    AdminReviewRequest,
    CreateSessionRequest,
    RunTranslationAnalysisRequest,
)
from backend.services.mini_brain_language_intelligence_service import (
    MiniBrainLanguageIntelligenceService,
)

router = APIRouter(
    prefix="/admin/mini-brain/language-intelligence",
    tags=["admin-mini-brain-language-intelligence"],
    dependencies=[Depends(require_admin)],
)


def service(settings) -> MiniBrainLanguageIntelligenceService:
    return MiniBrainLanguageIntelligenceService(settings)


@router.get("/diagnostics")
async def diagnostics():
    return {
        "ai_model_used": False,
        "dataset_writes_performed": False,
        "training_started": False,
        "models_deployed": False,
        "rag_called": False,
        "automatic_approval": False,
        "writes_scope": "own tables only (mini_brain_language_sessions/_events)",
        "pipeline_stages": [
            "language_scan", "unicode_validation", "spell_analysis", "grammar_analysis",
            "ocr_analysis", "tanglish_analysis", "translation_analysis", "dataset_draft_generation",
            "language_quality_score", "language_report", "awaiting_admin_review", "certified", "closed",
        ],
    }


# -- sessions ----------------------------------------------------------------


@router.post("/sessions")
async def create_session(payload: CreateSessionRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).create_session(
        dataset_source_public_id=payload.dataset_source_public_id, admin_id=admin.admin.public_id,
    )


@router.get("/sessions")
async def list_sessions(
    settings: SettingsDependency,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    return service(settings).list_sessions(limit=limit, offset=offset)


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, settings: SettingsDependency):
    return service(settings).session(session_id)


@router.get("/sessions/{session_id}/events")
async def list_events(
    session_id: str,
    settings: SettingsDependency,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    return service(settings).events(session_id, limit=limit, offset=offset)


@router.post("/sessions/{session_id}/language-scan")
async def run_language_scan(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_language_scan_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/unicode-validation")
async def run_unicode_validation(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_unicode_validation_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/spell-analysis")
async def run_spell_analysis(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_spell_analysis_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/grammar-analysis")
async def run_grammar_analysis(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_grammar_analysis_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/ocr-analysis")
async def run_ocr_analysis(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_ocr_analysis_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/tanglish-analysis")
async def run_tanglish_analysis(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_tanglish_analysis_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/translation-analysis")
async def run_translation_analysis(
    session_id: str, payload: RunTranslationAnalysisRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).run_translation_analysis_stage(
        session_id, pairs=[p.model_dump() for p in payload.pairs], admin_id=admin.admin.public_id,
    )


@router.post("/sessions/{session_id}/dataset-draft")
async def run_dataset_draft(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_dataset_draft_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/quality-score")
async def run_quality_score(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_quality_score_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/report")
async def generate_report(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).generate_report_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/admin-review")
async def admin_review(
    session_id: str, payload: AdminReviewRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).admin_review(session_id, decision=payload.decision, admin_id=admin.admin.public_id)
