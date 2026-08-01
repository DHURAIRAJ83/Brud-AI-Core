"""Phase 19 Knowledge-Gap Registry -- Admin-only API, under
`/api/admin/knowledge-gaps`. Every write here goes through a thin
service (never raw SQL in this layer); no endpoint here can create a
RAG source, start a RAG trial, create a training dataset, start
training, or release a model -- eligibility flags are advisory reads
only.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.database.repositories.knowledge_gap import KnowledgeGapRepository
from backend.models.knowledge_gap import (
    GapClassifyRequest,
    GapConfirmMergeRequest,
    GapDeletionRequest,
    GapNoteRequest,
    GapProposeMergeRequest,
    GapResolveRequest,
    GapReviewRequest,
)
from backend.services.knowledge_gap_daily_report_service import KnowledgeGapDailyReportService
from backend.services.knowledge_gap_deletion_service import KnowledgeGapDeletionService
from backend.services.knowledge_gap_handoff_assessment_service import (
    KnowledgeGapHandoffAssessmentService,
)
from backend.services.knowledge_gap_merge_service import KnowledgeGapMergeService
from backend.services.knowledge_gap_priority_service import (
    KnowledgeGapPriorityService,
    PriorityInput,
)
from backend.services.knowledge_gap_research_service import KnowledgeGapResearchService
from backend.services.knowledge_gap_resolution_service import KnowledgeGapResolutionService
from backend.services.knowledge_gap_review_service import KnowledgeGapReviewService

router = APIRouter(
    prefix="/admin/knowledge-gaps",
    tags=["knowledge-gaps"],
    dependencies=[Depends(require_admin)],
)


def repository(settings: SettingsDependency) -> KnowledgeGapRepository:
    return KnowledgeGapRepository(settings.resolved_database_path)


# -- overview / cases / clusters (read-only) -------------------------------------------------


@router.get("/overview")
async def get_overview(settings: SettingsDependency) -> dict[str, Any]:
    repo = repository(settings)
    overview = repo.aggregate_overview()
    overview["tamil"] = repo.tamil_capability_summary()
    overview["web_demand"] = repo.web_demand_summary()
    overview["tool_demand"] = repo.tool_demand_summary()
    overview["language_failures"] = repo.language_failure_summary()
    return overview


@router.get("/cases")
async def list_cases(
    settings: SettingsDependency,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: str | None = None,
    event_type: str | None = None,
    priority_band: str | None = None,
) -> dict[str, Any]:
    repo = repository(settings)
    cases = repo.list_cases(
        limit=limit,
        offset=offset,
        status=status,
        event_type=event_type,
        priority_band=priority_band,
    )
    return {"cases": cases, "count": len(cases)}


@router.get("/cases/{case_public_id}")
async def get_case(case_public_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return repository(settings).get_case(case_public_id)


@router.get("/cases/{case_public_id}/occurrences")
async def list_occurrences(
    case_public_id: str,
    settings: SettingsDependency,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    repo = repository(settings)
    occurrences = repo.list_occurrences_for_case(case_public_id, limit=limit, offset=offset)
    return {"occurrences": occurrences, "count": len(occurrences)}


@router.get("/cases/{case_public_id}/reviews")
async def list_reviews(case_public_id: str, settings: SettingsDependency) -> dict[str, Any]:
    reviews = repository(settings).list_reviews_for_case(case_public_id)
    return {"reviews": reviews, "count": len(reviews)}


@router.get("/cases/{case_public_id}/notes")
async def list_notes(case_public_id: str, settings: SettingsDependency) -> dict[str, Any]:
    service = KnowledgeGapResearchService(settings)
    notes = service.list_notes(case_public_id)
    return {"notes": notes, "count": len(notes)}


@router.get("/cases/{case_public_id}/events")
async def list_events(case_public_id: str, settings: SettingsDependency) -> dict[str, Any]:
    repo = repository(settings)
    events = repo.list_status_events_for_case(case_public_id)
    return {"events": events, "count": len(events)}


# -- case mutations (Admin-confirmed) ----------------------------------------------------------


@router.post("/cases/{case_public_id}/classify")
async def classify_case(
    case_public_id: str,
    payload: GapClassifyRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    service = KnowledgeGapReviewService(settings)
    return service.review(
        case_public_id,
        decision="reclassify",
        comment=payload.comment,
        reviewed_by_admin_public_id=admin.admin.public_id,
    )


@router.post("/cases/{case_public_id}/review")
async def review_case(
    case_public_id: str,
    payload: GapReviewRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    service = KnowledgeGapReviewService(settings)
    return service.review(
        case_public_id,
        decision=payload.decision,
        comment=payload.comment,
        reviewed_by_admin_public_id=admin.admin.public_id,
    )


@router.post("/cases/{case_public_id}/notes")
async def add_note(
    case_public_id: str,
    payload: GapNoteRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    service = KnowledgeGapResearchService(settings)
    return service.add_note(
        case_public_id,
        note_type=payload.note_type,
        note_text=payload.note_text,
        source_reference=payload.source_reference,
        author_admin_id=admin.admin.public_id,
    )


@router.post("/cases/{case_public_id}/resolve")
async def resolve_case(
    case_public_id: str,
    payload: GapResolveRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    service = KnowledgeGapResolutionService(settings)
    return service.resolve(
        case_public_id,
        resolution_type=payload.resolution_type,
        notes=payload.notes,
        resolved_by_admin_public_id=admin.admin.public_id,
    )


@router.post("/cases/{case_public_id}/archive")
async def archive_case(
    case_public_id: str,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    service = KnowledgeGapReviewService(settings)
    return service.review(
        case_public_id,
        decision="archive",
        comment=None,
        reviewed_by_admin_public_id=admin.admin.public_id,
    )


@router.post("/cases/{case_public_id}/assess-handoff")
async def assess_handoff(
    case_public_id: str,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    """Advisory only -- recomputes and stores
    `eligible_for_rag_research`/`eligible_for_training_assessment` and
    their reason codes. Never creates a RAG source, RAG trial,
    training dataset, or training run."""

    del admin
    service = KnowledgeGapHandoffAssessmentService(settings)
    return service.assess(case_public_id)


# -- clusters -----------------------------------------------------------------------------------


@router.get("/clusters")
async def list_clusters(
    settings: SettingsDependency,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    repo = repository(settings)
    clusters = repo.list_clusters(limit=limit, offset=offset)
    return {"clusters": clusters, "count": len(clusters)}


@router.get("/clusters/{cluster_public_id}")
async def get_cluster(cluster_public_id: str, settings: SettingsDependency) -> dict[str, Any]:
    repo = repository(settings)
    cluster = repo.get_cluster(cluster_public_id)
    cluster["members"] = repo.list_cluster_members(cluster_public_id)
    return cluster


@router.post("/clusters/propose-merge")
async def propose_merge(
    payload: GapProposeMergeRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    del admin
    service = KnowledgeGapMergeService(settings)
    return service.propose_merge(payload.case_public_ids)


@router.post("/clusters/confirm-merge")
async def confirm_merge(
    payload: GapConfirmMergeRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    service = KnowledgeGapMergeService(settings)
    return service.confirm_merge(
        case_public_ids=payload.case_public_ids,
        stale_check_fingerprint=payload.stale_check_fingerprint,
        admin_public_id=admin.admin.public_id,
        canonical_question=payload.canonical_question,
        primary_language=payload.primary_language,
    )


@router.post("/clusters/{cluster_public_id}/recalculate-priority")
async def recalculate_cluster_priority(
    cluster_public_id: str,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    del admin
    repo = repository(settings)
    cluster = repo.recalculate_cluster_frequency(cluster_public_id)
    priority = KnowledgeGapPriorityService().score(
        PriorityInput(
            event_type=cluster["cluster_type"],
            reason_codes=(),
            frequency=cluster["frequency"],
            last_seen_at=datetime.now(UTC),
        )
    )
    return repo.update_cluster_priority(
        cluster_public_id,
        priority_score=priority.priority_score,
        priority_band=priority.priority_band,
        priority_reason_codes=list(priority.priority_reason_codes),
    )


# -- daily reports --------------------------------------------------------------------------------


@router.get("/reports/daily")
async def get_daily_reports(
    settings: SettingsDependency, limit: int = Query(default=30, ge=1, le=100)
) -> dict[str, Any]:
    service = KnowledgeGapDailyReportService(settings)
    reports = service.list_reports(limit=limit)
    return {"reports": reports, "count": len(reports)}


@router.post("/reports/daily/generate")
async def generate_daily_report(
    settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    del admin
    service = KnowledgeGapDailyReportService(settings)
    return service.generate()


# -- deletion / forgetting -------------------------------------------------------------------------


@router.post("/cases/{case_public_id}/request-deletion")
async def request_deletion(
    case_public_id: str,
    payload: GapDeletionRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    service = KnowledgeGapDeletionService(settings)
    return service.request(
        case_public_id, requested_by_admin_public_id=admin.admin.public_id, reason=payload.reason
    )


@router.get("/cases/{case_public_id}/deletion-preview")
async def deletion_preview(case_public_id: str, settings: SettingsDependency) -> dict[str, Any]:
    service = KnowledgeGapDeletionService(settings)
    return service.impact_preview(case_public_id)


@router.post("/cases/{case_public_id}/confirm-deletion")
async def confirm_deletion(
    case_public_id: str,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    service = KnowledgeGapDeletionService(settings)
    return service.confirm(case_public_id, admin_public_id=admin.admin.public_id)


@router.post("/cases/{case_public_id}/execute-deletion")
async def execute_deletion(
    case_public_id: str,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    service = KnowledgeGapDeletionService(settings)
    return service.execute(case_public_id, admin_public_id=admin.admin.public_id)


__all__ = ["router"]
