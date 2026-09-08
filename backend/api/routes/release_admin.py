"""Phase 24 — Admin Release Management API Router.

Prefix: `/admin/phase24`
Tags: `["release-admin"]`
Dependencies: `[Depends(require_admin)]`

Provides human-governed admin API endpoints for pre-release verification, release candidate creation,
release review decision processing (APPROVED, REJECTED, DEFERRED), atomic promotion, and non-destructive rollback.

CRITICAL INVARIANTS:
- Admin ONLY. Super Admin & Admin permitted; Auditor read-only; Public User denied.
- Server-side RBAC and identity verification.
- Evaluation APPROVED != Production Promotion. Explicit human admin action mandatory for promotion and rollback.
- Zero autonomous learning, zero training, zero background workers, zero subprocesses.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.api.auth import require_admin
from backend.api.dependencies import SettingsDependency
from backend.services.dataset_release_service import DatasetReleaseService
from backend.services.promotion_rollback_service import PromotionRollbackService
from backend.services.rag_release_service import RagReleaseService
from core_model.capabilities.release_management_service import (
    RELEASE_STAGE_APPROVED,
    RELEASE_STAGE_DEFERRED,
    RELEASE_STAGE_REJECTED,
    InvalidReleaseTransitionError,
    ReleaseApprovalRequiredError,
    ReleaseGovernanceError,
    ReleasePreflightError,
)

router = APIRouter(
    prefix="/admin/phase24",
    tags=["release-admin"],
    dependencies=[Depends(require_admin)],
)


def get_db_connection(settings: SettingsDependency) -> sqlite3.Connection:
    """Helper to instantiate SQLite connection to resolved DB path."""
    return sqlite3.connect(settings.resolved_database_path)


# ---------------------------------------------------------------------------
# Request Schemas
# ---------------------------------------------------------------------------

class CreateReleaseRequest(BaseModel):
    """Payload for creating a release candidate from an evaluation record."""
    evaluation_id: str = Field(..., description="Phase 23 APPROVED evaluation ID")
    created_by: str = Field(..., description="Creator admin identity")
    content_text: str = Field(default="Validated release content text", description="Release content text")


class ReleaseReviewRequest(BaseModel):
    """Payload for recording a human release approval decision."""
    reviewer_id: str = Field(..., description="Reviewer admin identity")
    notes: str | None = Field(default=None, description="Reviewer decision notes")


class PromoteReleaseRequest(BaseModel):
    """Payload for promoting a release candidate to active production status."""
    approved_by: str = Field(..., description="Authorizing admin identity")
    space_or_target_id: str = Field(default="default", description="Target space or component ID")


class RollbackReleaseRequest(BaseModel):
    """Payload for performing non-destructive release rollback."""
    approved_by: str = Field(..., description="Authorizing admin identity")
    target_historical_version: str = Field(..., description="Target historical release version")
    reason: str = Field(default="Administrative rollback", description="Reason for rollback")
    space_or_target_id: str = Field(default="default", description="Target space or component ID")


# ---------------------------------------------------------------------------
# Release Endpoints
# ---------------------------------------------------------------------------

@router.get("/releases/{release_id}/preflight")
async def release_preflight_endpoint(
    release_id: str,
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Run pre-release verification on a release candidate."""
    conn = get_db_connection(settings)
    service = RagReleaseService(conn)
    try:
        return service.run_preflight(release_id)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.post("/releases/create", status_code=status.HTTP_201_CREATED)
async def create_release_endpoint(
    req: CreateReleaseRequest,
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Create a formal ReleaseCandidate from an APPROVED evaluation record."""
    conn = get_db_connection(settings)
    service = RagReleaseService(conn)
    try:
        candidate = service.create_release_candidate(
            evaluation_id=req.evaluation_id, created_by=req.created_by, content_text=req.content_text
        )
        return candidate.to_dict()
    except ReleasePreflightError as rpe:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(rpe))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.post("/releases/{release_id}/review")
async def review_release_endpoint(
    release_id: str,
    decision: str = Query(..., description="Decision: APPROVED, REJECTED, or DEFERRED"),
    req: ReleaseReviewRequest = None,
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Apply human admin approval decision to a release candidate."""
    conn = get_db_connection(settings)
    service = RagReleaseService(conn)
    try:
        updated_candidate, approval = service.review_release(
            release_id, decision, reviewer_id=req.reviewer_id, reviewer_notes=req.notes
        )
        return {"release": updated_candidate.to_dict(), "approval": approval.to_dict()}
    except InvalidReleaseTransitionError as ite:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(ite))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.post("/releases/{release_id}/approve")
async def approve_release_endpoint(
    release_id: str,
    req: ReleaseReviewRequest,
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Explicitly approve a release candidate."""
    conn = get_db_connection(settings)
    service = RagReleaseService(conn)
    try:
        updated_candidate, approval = service.review_release(
            release_id, RELEASE_STAGE_APPROVED, reviewer_id=req.reviewer_id, reviewer_notes=req.notes
        )
        return {"release": updated_candidate.to_dict(), "approval": approval.to_dict()}
    except InvalidReleaseTransitionError as ite:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(ite))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.post("/releases/{release_id}/reject")
async def reject_release_endpoint(
    release_id: str,
    req: ReleaseReviewRequest,
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Explicitly reject a release candidate."""
    conn = get_db_connection(settings)
    service = RagReleaseService(conn)
    try:
        updated_candidate, approval = service.review_release(
            release_id, RELEASE_STAGE_REJECTED, reviewer_id=req.reviewer_id, reviewer_notes=req.notes
        )
        return {"release": updated_candidate.to_dict(), "approval": approval.to_dict()}
    except InvalidReleaseTransitionError as ite:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(ite))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.post("/releases/{release_id}/promote")
async def promote_release_endpoint(
    release_id: str,
    req: PromoteReleaseRequest,
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Atomically promote a RELEASE_APPROVED release candidate to ACTIVE production version."""
    conn = get_db_connection(settings)
    service = PromotionRollbackService(conn)
    try:
        active_candidate, promotion_op = service.promote_release(
            release_id, approved_by=req.approved_by, space_or_target_id=req.space_or_target_id
        )
        return {"release": active_candidate.to_dict(), "promotion": promotion_op.to_dict()}
    except InvalidReleaseTransitionError as ite:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(ite))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.post("/releases/{release_id}/rollback")
async def rollback_release_endpoint(
    release_id: str,
    req: RollbackReleaseRequest,
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Execute non-destructive rollback from active version to historical target release version."""
    conn = get_db_connection(settings)
    service = PromotionRollbackService(conn)
    try:
        rb_candidate, rollback_op = service.rollback_release(
            release_id,
            target_historical_version=req.target_historical_version,
            approved_by=req.approved_by,
            reason=req.reason,
            space_or_target_id=req.space_or_target_id,
        )
        return {"release": rb_candidate.to_dict(), "rollback": rollback_op.to_dict()}
    except InvalidReleaseTransitionError as ite:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(ite))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.get("/releases")
async def list_releases_endpoint(
    artifact_id: str | None = Query(default=None),
    artifact_type: str | None = Query(default=None),
    release_status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """List release candidates with optional filtering."""
    conn = get_db_connection(settings)
    service = RagReleaseService(conn)
    releases = service.release_repo.list_releases(
        artifact_id=artifact_id, artifact_type=artifact_type, release_status=release_status, limit=limit, offset=offset
    )
    return {"releases": [r.to_dict() for r in releases]}


@router.get("/active")
async def get_active_release_pointer_endpoint(
    artifact_type: str = Query(default="RAG_SOURCE_VERSION"),
    space_or_target_id: str = Query(default="default"),
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Fetch current active version pointer for target space."""
    conn = get_db_connection(settings)
    service = RagReleaseService(conn)
    pointer = service.release_repo.get_active_version_pointer(artifact_type, space_or_target_id)
    if not pointer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active version pointer found.")
    return pointer


@router.get("/metrics")
async def get_aggregate_release_metrics_endpoint(
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Fetch aggregate release metrics."""
    conn = get_db_connection(settings)
    service = RagReleaseService(conn)
    return service.release_repo.aggregate_metrics()
