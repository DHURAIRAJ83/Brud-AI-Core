"""Phase 21 — Admin Knowledge Candidates Staging API Router.

Prefix: `/admin/knowledge-candidates`
Tags: `["knowledge-candidates"]`
Dependencies: `[Depends(require_admin)]`

Provides human-governed admin API endpoints for staging, inspecting, validating, approving,
rejecting, and deferring RAG & Dataset candidate staging records.

CRITICAL INVARIANTS:
- Admin ONLY. Super Admin & Admin permitted; Auditor read-only; Public User denied.
- Server-side RBAC and identity verification.
- Zero autonomous execution, zero training, zero automatic RAG vector-index insertion.
- All actions generate JSON-serializable, secret-sanitized audit log events.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.api.auth import require_admin
from backend.api.dependencies import SettingsDependency
from backend.database.repositories.candidate_curation_repository import CandidateCurationRepository
from core_model.capabilities.candidate_curation_service import (
    CandidateCurationService,
    CandidateProvenanceError,
    DatasetCandidateStagingRecord,
    InvalidStagingTransitionError,
    RAGCandidateStagingRecord,
    stage_dataset_candidate,
    stage_rag_candidate,
)
from core_model.capabilities.knowledge_gap_governance_service import (
    GovernanceSecurityError,
    KnowledgeGapRecord,
)

router = APIRouter(
    prefix="/admin/knowledge-candidates",
    tags=["knowledge-candidates"],
    dependencies=[Depends(require_admin)],
)


def get_curation_repository(settings: SettingsDependency) -> CandidateCurationRepository:
    """Helper to instantiate repository connected to resolved DB path."""
    conn = sqlite3.connect(settings.resolved_database_path)
    return CandidateCurationRepository(conn)


# ---------------------------------------------------------------------------
# Request Schemas
# ---------------------------------------------------------------------------

class StageRAGCandidateRequest(BaseModel):
    """Payload for staging an approved RAG candidate."""
    record_dict: dict[str, Any] = Field(..., description="Phase 20 KnowledgeGapRecord dictionary")
    title: str = Field(..., description="RAG document title or topic")
    content: str = Field(..., description="Sanitized document content")
    staged_by: str = Field(..., description="Admin identity")


class StageDatasetCandidateRequest(BaseModel):
    """Payload for staging an approved Dataset candidate."""
    record_dict: dict[str, Any] = Field(..., description="Phase 20 KnowledgeGapRecord dictionary")
    input_context: str = Field(..., description="Instruction / input context")
    proposed_output: str = Field(..., description="Target proposed response output")
    language: str = Field(default="en", description="Language code")
    domain_topic: str = Field(default="general", description="Domain / topic tag")
    staged_by: str = Field(..., description="Admin identity")


class CandidateReviewActionRequest(BaseModel):
    """Payload for review / reject / defer action."""
    reviewer_id: str = Field(..., description="Reviewer admin identity")
    notes: str | None = Field(default=None, description="Optional reviewer notes")


class CandidateApproveActionRequest(BaseModel):
    """Payload for approving a candidate."""
    approver_id: str = Field(..., description="Approver admin identity")
    approval_notes: str | None = Field(default=None, description="Optional approval notes")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/staged")
async def list_staged_candidates(
    candidate_type: str = Query(default="all", description="Candidate type filter: rag, dataset, all"),
    status: str | None = Query(default=None, description="Status filter"),
    duplicate_status: str | None = Query(default=None, description="Duplicate status filter"),
    conflict_status: str | None = Query(default=None, description="Conflict status filter"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """List staged RAG and Dataset candidates with metrics."""
    repo = get_curation_repository(settings)
    rag_candidates: list[dict[str, Any]] = []
    dataset_candidates: list[dict[str, Any]] = []

    if candidate_type in ("all", "rag"):
        rag_recs = repo.list_rag_candidates(
            status=status,
            duplicate_status=duplicate_status,
            conflict_status=conflict_status,
            limit=limit,
            offset=offset,
        )
        rag_candidates = [r.to_dict() for r in rag_recs]

    if candidate_type in ("all", "dataset"):
        ds_recs = repo.list_dataset_candidates(
            status=status,
            duplicate_status=duplicate_status,
            conflict_status=conflict_status,
            limit=limit,
            offset=offset,
        )
        dataset_candidates = [d.to_dict() for d in ds_recs]

    metrics = repo.aggregate_staging_metrics()

    return {
        "candidate_type": candidate_type,
        "rag_candidates": rag_candidates,
        "dataset_candidates": dataset_candidates,
        "total_returned": len(rag_candidates) + len(dataset_candidates),
        "metrics": metrics,
    }


@router.get("/staged/{candidate_id}")
async def get_staged_candidate_detail(
    candidate_id: str,
    candidate_type: str = Query(default="rag", description="Type: rag or dataset"),
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Get detailed staging record for a candidate."""
    repo = get_curation_repository(settings)
    if candidate_type == "dataset":
        rec = repo.get_dataset_candidate_by_id(candidate_id)
    else:
        rec = repo.get_rag_candidate_by_id(candidate_id)

    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate record '{candidate_id}' not found.",
        )

    return rec.to_dict()


@router.post("/stage-rag", status_code=status.HTTP_201_CREATED)
async def stage_rag_candidate_endpoint(
    req: StageRAGCandidateRequest,
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Stage a Phase 20 APPROVED Knowledge Gap record as a RAG Candidate."""
    repo = get_curation_repository(settings)
    try:
        kg_rec = KnowledgeGapRecord(**req.record_dict)
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid KnowledgeGapRecord dictionary: {err}",
        )

    try:
        existing = repo.list_rag_candidates(limit=500)
        staged = stage_rag_candidate(
            kg_rec,
            title=req.title,
            content=req.content,
            staged_by=req.staged_by,
            existing_records=existing,
        )
        repo.insert_rag_candidate(staged)
        return staged.to_dict()
    except GovernanceSecurityError as gse:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(gse))
    except CandidateProvenanceError as cpe:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(cpe))
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.post("/stage-dataset", status_code=status.HTTP_201_CREATED)
async def stage_dataset_candidate_endpoint(
    req: StageDatasetCandidateRequest,
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Stage a Phase 20 APPROVED Knowledge Gap record as a Dataset Candidate."""
    repo = get_curation_repository(settings)
    try:
        kg_rec = KnowledgeGapRecord(**req.record_dict)
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid KnowledgeGapRecord dictionary: {err}",
        )

    try:
        existing = repo.list_dataset_candidates(limit=500)
        staged = stage_dataset_candidate(
            kg_rec,
            input_context=req.input_context,
            proposed_output=req.proposed_output,
            language=req.language,
            domain_topic=req.domain_topic,
            staged_by=req.staged_by,
            existing_records=existing,
        )
        repo.insert_dataset_candidate(staged)
        return staged.to_dict()
    except GovernanceSecurityError as gse:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(gse))
    except CandidateProvenanceError as cpe:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(cpe))
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.post("/staged/{candidate_id}/approve")
async def approve_staged_candidate_endpoint(
    candidate_id: str,
    req: CandidateApproveActionRequest,
    candidate_type: str = Query(default="rag"),
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Approve a staged candidate (advancing to READY_FOR_INGESTION or READY_FOR_EXPORT)."""
    repo = get_curation_repository(settings)
    service = CandidateCurationService()

    if candidate_type == "dataset":
        rec = repo.get_dataset_candidate_by_id(candidate_id)
        if not rec:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Dataset candidate '{candidate_id}' not found.")
        try:
            approved = service.approve_staging(rec, approver_id=req.approver_id, approval_notes=req.approval_notes)
            repo.update_dataset_candidate_state(approved)
            return approved.to_dict()
        except InvalidStagingTransitionError as ite:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(ite))
    else:
        rec = repo.get_rag_candidate_by_id(candidate_id)
        if not rec:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"RAG candidate '{candidate_id}' not found.")
        try:
            approved = service.approve_staging(rec, approver_id=req.approver_id, approval_notes=req.approval_notes)
            repo.update_rag_candidate_state(approved)
            return approved.to_dict()
        except InvalidStagingTransitionError as ite:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(ite))


@router.post("/staged/{candidate_id}/reject")
async def reject_staged_candidate_endpoint(
    candidate_id: str,
    req: CandidateReviewActionRequest,
    candidate_type: str = Query(default="rag"),
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Reject a staged candidate."""
    repo = get_curation_repository(settings)
    service = CandidateCurationService()

    if candidate_type == "dataset":
        rec = repo.get_dataset_candidate_by_id(candidate_id)
        if not rec:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Dataset candidate '{candidate_id}' not found.")
        try:
            rejected = service.reject_staging(rec, reviewer_id=req.reviewer_id, rejection_reason=req.notes)
            repo.update_dataset_candidate_state(rejected)
            return rejected.to_dict()
        except InvalidStagingTransitionError as ite:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(ite))
    else:
        rec = repo.get_rag_candidate_by_id(candidate_id)
        if not rec:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"RAG candidate '{candidate_id}' not found.")
        try:
            rejected = service.reject_staging(rec, reviewer_id=req.reviewer_id, rejection_reason=req.notes)
            repo.update_rag_candidate_state(rejected)
            return rejected.to_dict()
        except InvalidStagingTransitionError as ite:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(ite))


@router.post("/staged/{candidate_id}/defer")
async def defer_staged_candidate_endpoint(
    candidate_id: str,
    req: CandidateReviewActionRequest,
    candidate_type: str = Query(default="rag"),
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Defer a staged candidate."""
    repo = get_curation_repository(settings)
    service = CandidateCurationService()

    if candidate_type == "dataset":
        rec = repo.get_dataset_candidate_by_id(candidate_id)
        if not rec:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Dataset candidate '{candidate_id}' not found.")
        try:
            deferred = service.defer_staging(rec, reviewer_id=req.reviewer_id, deferral_reason=req.notes)
            repo.update_dataset_candidate_state(deferred)
            return deferred.to_dict()
        except InvalidStagingTransitionError as ite:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(ite))
    else:
        rec = repo.get_rag_candidate_by_id(candidate_id)
        if not rec:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"RAG candidate '{candidate_id}' not found.")
        try:
            deferred = service.defer_staging(rec, reviewer_id=req.reviewer_id, deferral_reason=req.notes)
            repo.update_rag_candidate_state(deferred)
            return deferred.to_dict()
        except InvalidStagingTransitionError as ite:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(ite))
