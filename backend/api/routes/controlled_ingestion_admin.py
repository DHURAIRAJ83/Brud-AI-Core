"""Phase 22 — Admin Controlled Ingestion & Dataset Export API Router.

Prefix: `/admin/phase22`
Tags: `["controlled-ingestion"]`
Dependencies: `[Depends(require_admin)]`

Provides human-governed admin API endpoints for pre-flight verification, dry-run plan generation,
explicit human admin approval, controlled atomic ingestion/export, status tracking, and rollback operations.

CRITICAL INVARIANTS:
- Admin ONLY. Super Admin & Admin permitted; Auditor read-only; Public User denied.
- Server-side RBAC and identity verification.
- Candidate readiness (READY_FOR_INGESTION / READY_FOR_EXPORT) alone NEVER triggers automatic execution.
- Zero autonomous execution, zero training, zero background workers, zero subprocesses.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.api.auth import require_admin
from backend.api.dependencies import SettingsDependency
from backend.services.controlled_dataset_export_service import ControlledDatasetExportService
from backend.services.controlled_rag_ingestion_service import ControlledRagIngestionService
from core_model.capabilities.controlled_ingestion_service import (
    ControlledIngestionError,
    IngestionApprovalRequiredError,
    InvalidOperationTransitionError,
    PreflightValidationError,
)

router = APIRouter(
    prefix="/admin/phase22",
    tags=["controlled-ingestion"],
    dependencies=[Depends(require_admin)],
)


def get_db_connection(settings: SettingsDependency) -> sqlite3.Connection:
    """Helper to instantiate SQLite connection to resolved DB path."""
    return sqlite3.connect(settings.resolved_database_path)


# ---------------------------------------------------------------------------
# Request Schemas
# ---------------------------------------------------------------------------

class ApproveOperationRequest(BaseModel):
    """Payload for approving an operation."""
    approver_id: str = Field(..., description="Approver admin identity")
    notes: str | None = Field(default=None, description="Optional approval notes")


class ExecuteOperationRequest(BaseModel):
    """Payload for executing an approved operation."""
    executor_id: str = Field(..., description="Executor admin identity")


class RollbackOperationRequest(BaseModel):
    """Payload for rolling back an operation."""
    admin_id: str = Field(..., description="Admin identity initiating rollback")
    reason: str | None = Field(default=None, description="Rollback reason")


# ---------------------------------------------------------------------------
# RAG Ingestion Endpoints
# ---------------------------------------------------------------------------

@router.get("/rag/{candidate_id}/preflight")
async def rag_preflight_endpoint(
    candidate_id: str,
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Run pre-flight verification on a staged RAG candidate."""
    conn = get_db_connection(settings)
    service = ControlledRagIngestionService(conn)
    try:
        res = service.run_preflight(candidate_id)
        return res.to_dict()
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.post("/rag/{candidate_id}/dry-run", status_code=status.HTTP_201_CREATED)
async def rag_dry_run_endpoint(
    candidate_id: str,
    target_space_id: str = Query(default="space-default"),
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Generate a dry-run ingestion plan without mutating production RAG data."""
    conn = get_db_connection(settings)
    service = ControlledRagIngestionService(conn)
    try:
        plan = service.execute_dry_run(candidate_id, target_space_id=target_space_id)
        return plan.to_dict()
    except PreflightValidationError as pve:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(pve))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.post("/rag/operations/{operation_id}/approve")
async def approve_rag_ingestion_endpoint(
    operation_id: str,
    req: ApproveOperationRequest,
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Explicitly approve a RAG ingestion dry-run operation."""
    conn = get_db_connection(settings)
    service = ControlledRagIngestionService(conn)
    try:
        approved = service.approve_ingestion(operation_id, approver_id=req.approver_id, approval_notes=req.notes)
        return approved.to_dict()
    except InvalidOperationTransitionError as ite:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(ite))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.post("/rag/operations/{operation_id}/ingest")
async def execute_rag_ingestion_endpoint(
    operation_id: str,
    req: ExecuteOperationRequest,
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Execute controlled RAG ingestion after explicit approval."""
    conn = get_db_connection(settings)
    service = ControlledRagIngestionService(conn)
    try:
        res = service.execute_ingestion(operation_id, executor_id=req.executor_id)
        return res
    except IngestionApprovalRequiredError as iae:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(iae))
    except InvalidOperationTransitionError as ite:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(ite))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.post("/rag/operations/{operation_id}/rollback")
async def rollback_rag_ingestion_endpoint(
    operation_id: str,
    req: RollbackOperationRequest,
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Perform a non-destructive rollback of a RAG ingestion operation."""
    conn = get_db_connection(settings)
    service = ControlledRagIngestionService(conn)
    try:
        rolled_back = service.rollback_ingestion(operation_id, admin_id=req.admin_id, rollback_reason=req.reason)
        return rolled_back.to_dict()
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except InvalidOperationTransitionError as ite:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(ite))


# ---------------------------------------------------------------------------
# Dataset Export Endpoints
# ---------------------------------------------------------------------------

@router.get("/datasets/{candidate_id}/preflight")
async def dataset_preflight_endpoint(
    candidate_id: str,
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Run pre-flight verification on a staged Dataset candidate."""
    conn = get_db_connection(settings)
    service = ControlledDatasetExportService(conn)
    try:
        res = service.run_preflight(candidate_id)
        return res.to_dict()
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.post("/datasets/{candidate_id}/dry-run", status_code=status.HTTP_201_CREATED)
async def dataset_dry_run_endpoint(
    candidate_id: str,
    target_dir: str | None = Query(default=None),
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Generate a dry-run export plan without creating production dataset files."""
    conn = get_db_connection(settings)
    service = ControlledDatasetExportService(conn)
    try:
        plan = service.execute_dry_run(candidate_id, target_dir=target_dir)
        return plan.to_dict()
    except PreflightValidationError as pve:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(pve))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.post("/datasets/operations/{operation_id}/approve")
async def approve_dataset_export_endpoint(
    operation_id: str,
    req: ApproveOperationRequest,
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Explicitly approve a Dataset export dry-run operation."""
    conn = get_db_connection(settings)
    service = ControlledDatasetExportService(conn)
    try:
        approved = service.approve_export(operation_id, approver_id=req.approver_id, approval_notes=req.notes)
        return approved.to_dict()
    except InvalidOperationTransitionError as ite:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(ite))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.post("/datasets/operations/{operation_id}/export")
async def execute_dataset_export_endpoint(
    operation_id: str,
    req: ExecuteOperationRequest,
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Execute controlled dataset export after explicit approval."""
    conn = get_db_connection(settings)
    service = ControlledDatasetExportService(conn, export_root_dir=settings.resolved_dataset_export_dir)
    try:
        res = service.execute_export(operation_id, executor_id=req.executor_id)
        return res
    except IngestionApprovalRequiredError as iae:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(iae))
    except InvalidOperationTransitionError as ite:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(ite))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.post("/datasets/operations/{operation_id}/rollback")
async def rollback_dataset_export_endpoint(
    operation_id: str,
    req: RollbackOperationRequest,
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Perform a non-destructive rollback of a Dataset export operation."""
    conn = get_db_connection(settings)
    service = ControlledDatasetExportService(conn)
    try:
        rolled_back = service.rollback_export(operation_id, admin_id=req.admin_id, rollback_reason=req.reason)
        return rolled_back.to_dict()
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except InvalidOperationTransitionError as ite:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(ite))
