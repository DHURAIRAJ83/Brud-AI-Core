"""Phase 25 — Admin Deployment Readiness & Gate API Router.

Prefix: `/admin/phase25`
Tags: `["deployment-admin"]`
Dependencies: `[Depends(require_admin)]`

Provides human-governed admin API endpoints for pre-deployment readiness preflight,
deployment review decisions (APPROVED, REJECTED, DEFERRED), atomic deployment execution, and non-destructive deployment rollback.

CRITICAL INVARIANTS:
- Admin ONLY. Super Admin & Admin permitted; Auditor read-only; Public User denied.
- Server-side RBAC and identity verification.
- Readiness PASS != Deployment Approval != Deployment Execution. Explicit human admin action mandatory for deployment and rollback.
- Zero autonomous learning, zero training, zero background workers, zero subprocesses.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.api.auth import require_admin
from backend.api.dependencies import SettingsDependency
from backend.services.deployment_gate_service import DeploymentGateService
from backend.services.deployment_readiness_service import DeploymentReadinessBackendService
from backend.services.deployment_rollback_service import DeploymentRollbackBackendService
from core_model.capabilities.deployment_readiness_service import (
    DEPLOYMENT_STAGE_APPROVED,
    DEPLOYMENT_STAGE_DEFERRED,
    DEPLOYMENT_STAGE_REJECTED,
    DeploymentApprovalRequiredError,
    DeploymentGovernanceError,
    DeploymentLockError,
    DeploymentPreflightError,
    InvalidDeploymentTransitionError,
)

router = APIRouter(
    prefix="/admin/phase25",
    tags=["deployment-admin"],
    dependencies=[Depends(require_admin)],
)


def get_db_connection(settings: SettingsDependency) -> sqlite3.Connection:
    """Helper to instantiate SQLite connection to resolved DB path."""
    return sqlite3.connect(settings.resolved_database_path)


# ---------------------------------------------------------------------------
# Request Schemas
# ---------------------------------------------------------------------------

class DeploymentPreflightRequest(BaseModel):
    """Payload for initiating a deployment readiness preflight check."""
    created_by: str = Field(..., description="Creator admin identity")
    target_environment: str = Field(default="production", description="Target deployment environment")
    content_text: str = Field(default="Validated production release content", description="Content text for preflight")


class DeploymentReviewRequest(BaseModel):
    """Payload for recording a human deployment approval decision."""
    reviewer_id: str = Field(..., description="Reviewer admin identity")
    notes: str | None = Field(default=None, description="Reviewer decision notes")


class ExecuteDeploymentRequest(BaseModel):
    """Payload for executing a DEPLOYMENT_APPROVED deployment."""
    approved_by: str = Field(..., description="Authorizing admin identity")


class RollbackDeploymentRequest(BaseModel):
    """Payload for performing non-destructive deployment rollback."""
    approved_by: str = Field(..., description="Authorizing admin identity")
    target_historical_version: str = Field(..., description="Target historical release version")
    reason: str = Field(default="Administrative deployment rollback", description="Reason for rollback")


# ---------------------------------------------------------------------------
# Deployment Endpoints
# ---------------------------------------------------------------------------

@router.get("/releases/{release_id}/preflight")
async def get_release_preflight_endpoint(
    release_id: str,
    created_by: str = Query(default="admin-1"),
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Run pre-deployment readiness verification on a Phase 24 ACTIVE release candidate."""
    conn = get_db_connection(settings)
    service = DeploymentReadinessBackendService(conn)
    try:
        report = service.run_preflight(release_id, created_by=created_by)
        return report.to_dict()
    except DeploymentPreflightError as dpe:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(dpe))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.post("/releases/{release_id}/review")
async def review_deployment_endpoint(
    release_id: str,
    readiness_id: str = Query(..., description="Readiness report ID"),
    decision: str = Query(..., description="Decision: APPROVED, REJECTED, or DEFERRED"),
    req: DeploymentReviewRequest = None,
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Apply human admin deployment approval decision."""
    conn = get_db_connection(settings)
    service = DeploymentGateService(conn)
    try:
        updated_report, approval = service.review_deployment(
            readiness_id, decision, reviewer_id=req.reviewer_id, reviewer_notes=req.notes
        )
        return {"report": updated_report.to_dict(), "approval": approval.to_dict()}
    except InvalidDeploymentTransitionError as ite:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(ite))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.post("/releases/{release_id}/approve")
async def approve_deployment_endpoint(
    release_id: str,
    readiness_id: str = Query(..., description="Readiness report ID"),
    req: DeploymentReviewRequest = None,
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Explicitly approve a deployment readiness report."""
    conn = get_db_connection(settings)
    service = DeploymentGateService(conn)
    try:
        updated_report, approval = service.review_deployment(
            readiness_id, DEPLOYMENT_STAGE_APPROVED, reviewer_id=req.reviewer_id, reviewer_notes=req.notes
        )
        return {"report": updated_report.to_dict(), "approval": approval.to_dict()}
    except InvalidDeploymentTransitionError as ite:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(ite))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.post("/releases/{release_id}/reject")
async def reject_deployment_endpoint(
    release_id: str,
    readiness_id: str = Query(..., description="Readiness report ID"),
    req: DeploymentReviewRequest = None,
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Explicitly reject a deployment readiness report."""
    conn = get_db_connection(settings)
    service = DeploymentGateService(conn)
    try:
        updated_report, approval = service.review_deployment(
            readiness_id, DEPLOYMENT_STAGE_REJECTED, reviewer_id=req.reviewer_id, reviewer_notes=req.notes
        )
        return {"report": updated_report.to_dict(), "approval": approval.to_dict()}
    except InvalidDeploymentTransitionError as ite:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(ite))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.post("/releases/{release_id}/defer")
async def defer_deployment_endpoint(
    release_id: str,
    readiness_id: str = Query(..., description="Readiness report ID"),
    req: DeploymentReviewRequest = None,
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Explicitly defer a deployment readiness report."""
    conn = get_db_connection(settings)
    service = DeploymentGateService(conn)
    try:
        updated_report, approval = service.review_deployment(
            readiness_id, DEPLOYMENT_STAGE_DEFERRED, reviewer_id=req.reviewer_id, reviewer_notes=req.notes
        )
        return {"report": updated_report.to_dict(), "approval": approval.to_dict()}
    except InvalidDeploymentTransitionError as ite:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(ite))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.post("/releases/{release_id}/deploy")
async def deploy_release_endpoint(
    release_id: str,
    readiness_id: str = Query(..., description="Readiness report ID"),
    req: ExecuteDeploymentRequest = None,
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Atomically execute deployment of a DEPLOYMENT_APPROVED release."""
    conn = get_db_connection(settings)
    service = DeploymentGateService(conn)
    try:
        verified_report, dep_op = service.execute_deployment(
            readiness_id, approved_by=req.approved_by
        )
        return {"report": verified_report.to_dict(), "deployment": dep_op.to_dict()}
    except DeploymentLockError as dle:
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=str(dle))
    except InvalidDeploymentTransitionError as ite:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(ite))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.post("/releases/{release_id}/rollback")
async def rollback_deployment_endpoint(
    release_id: str,
    readiness_id: str = Query(..., description="Readiness report ID"),
    req: RollbackDeploymentRequest = None,
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Execute non-destructive deployment rollback from active deployed release version to historical version."""
    conn = get_db_connection(settings)
    service = DeploymentRollbackBackendService(conn)
    try:
        rb_report, rb_op = service.rollback_deployment(
            readiness_id,
            target_historical_version=req.target_historical_version,
            approved_by=req.approved_by,
            reason=req.reason,
        )
        return {"report": rb_report.to_dict(), "rollback": rb_op.to_dict()}
    except InvalidDeploymentTransitionError as ite:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(ite))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.get("/releases")
async def list_deployment_reports_endpoint(
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """List deployment readiness reports."""
    conn = get_db_connection(settings)
    service = DeploymentReadinessBackendService(conn)
    metrics = service.deployment_repo.aggregate_metrics()
    return {"metrics": metrics}


@router.get("/metrics")
async def get_deployment_metrics_endpoint(
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Fetch aggregate deployment metrics."""
    conn = get_db_connection(settings)
    service = DeploymentReadinessBackendService(conn)
    return service.deployment_repo.aggregate_metrics()
