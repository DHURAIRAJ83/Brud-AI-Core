"""Phase 23 — Admin Quality Evaluation API Router.

Prefix: `/admin/phase23`
Tags: `["evaluation-admin"]`
Dependencies: `[Depends(require_admin)]`

Provides human-governed admin API endpoints for pre-evaluation verification, quality metric evaluation,
version comparison, regression detection, and human review decision processing (APPROVED, REJECTED, DEFERRED).

CRITICAL INVARIANTS:
- Admin ONLY. Super Admin & Admin permitted; Auditor read-only; Public User denied.
- Server-side RBAC and identity verification.
- Evaluation PASS != Automatic Promotion. Higher evaluation scores NEVER automatically modify production data.
- Zero autonomous learning, zero training, zero background workers, zero subprocesses.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.api.auth import require_admin
from backend.api.dependencies import SettingsDependency
from backend.services.dataset_evaluation_service import DatasetEvaluationService
from backend.services.rag_evaluation_service import RagEvaluationService
from backend.services.version_comparison_service import VersionComparisonService
from core_model.capabilities.evaluation_service import (
    EVALUATION_STAGE_APPROVED,
    EVALUATION_STAGE_DEFERRED,
    EVALUATION_STAGE_REJECTED,
    EvaluationApprovalRequiredError,
    EvaluationPreflightError,
    InvalidEvaluationTransitionError,
    QualityEvaluationError,
)

router = APIRouter(
    prefix="/admin/phase23",
    tags=["evaluation-admin"],
    dependencies=[Depends(require_admin)],
)


def get_db_connection(settings: SettingsDependency) -> sqlite3.Connection:
    """Helper to instantiate SQLite connection to resolved DB path."""
    return sqlite3.connect(settings.resolved_database_path)


# ---------------------------------------------------------------------------
# Request Schemas
# ---------------------------------------------------------------------------

class EvaluateRAGRequest(BaseModel):
    """Payload for initiating a RAG evaluation."""
    title: str = Field(default="RAG Source Document", description="Document title")
    content: str = Field(default="RAG source text content", description="Document content text")


class ReviewDecisionRequest(BaseModel):
    """Payload for recording a human review decision."""
    reviewer_id: str = Field(..., description="Reviewer admin identity")
    notes: str | None = Field(default=None, description="Reviewer decision notes")


# ---------------------------------------------------------------------------
# RAG Evaluation Endpoints
# ---------------------------------------------------------------------------

@router.get("/rag/{artifact_id}/preflight")
async def rag_preflight_endpoint(
    artifact_id: str,
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Run pre-evaluation verification on a Phase 22 RAG artifact."""
    conn = get_db_connection(settings)
    service = RagEvaluationService(conn)
    try:
        return service.run_preflight(artifact_id)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.post("/rag/{artifact_id}/evaluate", status_code=status.HTTP_201_CREATED)
async def evaluate_rag_endpoint(
    artifact_id: str,
    req: EvaluateRAGRequest,
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Run quality evaluation on a Phase 22 RAG artifact."""
    conn = get_db_connection(settings)
    service = RagEvaluationService(conn)
    try:
        record = service.evaluate_rag_artifact(artifact_id, title=req.title, content=req.content)
        return record.to_dict()
    except EvaluationPreflightError as epe:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(epe))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.get("/rag/{artifact_id}/metrics")
async def get_rag_metrics_endpoint(
    artifact_id: str,
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Fetch evaluation metrics for a RAG artifact."""
    conn = get_db_connection(settings)
    service = RagEvaluationService(conn)
    evals = service.eval_repo.list_evaluations(artifact_id=artifact_id, artifact_type="RAG_SOURCE_VERSION")
    if not evals:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No evaluation records found for artifact '{artifact_id}'.")
    return evals[0].to_dict()


@router.get("/rag/compare/{version_a}/{version_b}")
async def compare_rag_versions_endpoint(
    version_a: str,
    version_b: str,
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Compare Version A vs Version B for RAG evaluation records."""
    conn = get_db_connection(settings)
    service = VersionComparisonService(conn)
    evals_a = service.eval_repo.list_evaluations(artifact_type="RAG_SOURCE_VERSION")
    eval_a = next((e for e in evals_a if e.artifact_version == version_a), None)
    eval_b = next((e for e in evals_a if e.artifact_version == version_b), None)

    if not eval_a or not eval_b:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Evaluation records for versions '{version_a}' or '{version_b}' not found.")

    comp = service.compare_evaluations(eval_a.evaluation_id, eval_b.evaluation_id)
    return comp.to_dict()


@router.post("/rag/{evaluation_id}/review")
async def review_rag_evaluation_endpoint(
    evaluation_id: str,
    decision: str = Query(..., description="Review decision: APPROVED, REJECTED, or DEFERRED"),
    req: ReviewDecisionRequest = None,
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Apply human admin review decision to a RAG evaluation record."""
    conn = get_db_connection(settings)
    service = RagEvaluationService(conn)
    try:
        updated_eval, review = service.review_evaluation(
            evaluation_id, decision, reviewer_id=req.reviewer_id, reviewer_notes=req.notes
        )
        return {"evaluation": updated_eval.to_dict(), "review": review.to_dict()}
    except InvalidEvaluationTransitionError as ite:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(ite))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.post("/rag/{evaluation_id}/approve")
async def approve_rag_evaluation_endpoint(
    evaluation_id: str,
    req: ReviewDecisionRequest,
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Explicitly approve a RAG evaluation record."""
    conn = get_db_connection(settings)
    service = RagEvaluationService(conn)
    try:
        updated_eval, review = service.review_evaluation(
            evaluation_id, EVALUATION_STAGE_APPROVED, reviewer_id=req.reviewer_id, reviewer_notes=req.notes
        )
        return {"evaluation": updated_eval.to_dict(), "review": review.to_dict()}
    except InvalidEvaluationTransitionError as ite:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(ite))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.post("/rag/{evaluation_id}/reject")
async def reject_rag_evaluation_endpoint(
    evaluation_id: str,
    req: ReviewDecisionRequest,
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Explicitly reject a RAG evaluation record."""
    conn = get_db_connection(settings)
    service = RagEvaluationService(conn)
    try:
        updated_eval, review = service.review_evaluation(
            evaluation_id, EVALUATION_STAGE_REJECTED, reviewer_id=req.reviewer_id, reviewer_notes=req.notes
        )
        return {"evaluation": updated_eval.to_dict(), "review": review.to_dict()}
    except InvalidEvaluationTransitionError as ite:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(ite))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.post("/rag/{evaluation_id}/defer")
async def defer_rag_evaluation_endpoint(
    evaluation_id: str,
    req: ReviewDecisionRequest,
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Explicitly defer a RAG evaluation record."""
    conn = get_db_connection(settings)
    service = RagEvaluationService(conn)
    try:
        updated_eval, review = service.review_evaluation(
            evaluation_id, EVALUATION_STAGE_DEFERRED, reviewer_id=req.reviewer_id, reviewer_notes=req.notes
        )
        return {"evaluation": updated_eval.to_dict(), "review": review.to_dict()}
    except InvalidEvaluationTransitionError as ite:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(ite))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


# ---------------------------------------------------------------------------
# Dataset Evaluation Endpoints
# ---------------------------------------------------------------------------

@router.get("/datasets/{artifact_id}/preflight")
async def dataset_preflight_endpoint(
    artifact_id: str,
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Run pre-evaluation verification on a Phase 22 Dataset export artifact."""
    conn = get_db_connection(settings)
    service = DatasetEvaluationService(conn)
    try:
        return service.run_preflight(artifact_id)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.post("/datasets/{artifact_id}/evaluate", status_code=status.HTTP_201_CREATED)
async def evaluate_dataset_endpoint(
    artifact_id: str,
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Run quality evaluation on a Phase 22 Dataset export artifact."""
    conn = get_db_connection(settings)
    service = DatasetEvaluationService(conn)
    try:
        record = service.evaluate_dataset_artifact(artifact_id)
        return record.to_dict()
    except EvaluationPreflightError as epe:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(epe))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.get("/datasets/{artifact_id}/metrics")
async def get_dataset_metrics_endpoint(
    artifact_id: str,
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Fetch evaluation metrics for a Dataset artifact."""
    conn = get_db_connection(settings)
    service = DatasetEvaluationService(conn)
    evals = service.eval_repo.list_evaluations(artifact_id=artifact_id, artifact_type="DATASET_EXPORT_ARTIFACT")
    if not evals:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No evaluation records found for artifact '{artifact_id}'.")
    return evals[0].to_dict()


@router.get("/datasets/compare/{version_a}/{version_b}")
async def compare_dataset_versions_endpoint(
    version_a: str,
    version_b: str,
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Compare Version A vs Version B for Dataset evaluation records."""
    conn = get_db_connection(settings)
    service = VersionComparisonService(conn)
    evals_a = service.eval_repo.list_evaluations(artifact_type="DATASET_EXPORT_ARTIFACT")
    eval_a = next((e for e in evals_a if e.artifact_version == version_a), None)
    eval_b = next((e for e in evals_a if e.artifact_version == version_b), None)

    if not eval_a or not eval_b:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Evaluation records for versions '{version_a}' or '{version_b}' not found.")

    comp = service.compare_evaluations(eval_a.evaluation_id, eval_b.evaluation_id)
    return comp.to_dict()


@router.post("/datasets/{evaluation_id}/approve")
async def approve_dataset_evaluation_endpoint(
    evaluation_id: str,
    req: ReviewDecisionRequest,
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Explicitly approve a Dataset evaluation record."""
    conn = get_db_connection(settings)
    service = DatasetEvaluationService(conn)
    try:
        updated_eval, review = service.review_evaluation(
            evaluation_id, EVALUATION_STAGE_APPROVED, reviewer_id=req.reviewer_id, reviewer_notes=req.notes
        )
        return {"evaluation": updated_eval.to_dict(), "review": review.to_dict()}
    except InvalidEvaluationTransitionError as ite:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(ite))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.post("/datasets/{evaluation_id}/reject")
async def reject_dataset_evaluation_endpoint(
    evaluation_id: str,
    req: ReviewDecisionRequest,
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Explicitly reject a Dataset evaluation record."""
    conn = get_db_connection(settings)
    service = DatasetEvaluationService(conn)
    try:
        updated_eval, review = service.review_evaluation(
            evaluation_id, EVALUATION_STAGE_REJECTED, reviewer_id=req.reviewer_id, reviewer_notes=req.notes
        )
        return {"evaluation": updated_eval.to_dict(), "review": review.to_dict()}
    except InvalidEvaluationTransitionError as ite:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(ite))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.post("/datasets/{evaluation_id}/defer")
async def defer_dataset_evaluation_endpoint(
    evaluation_id: str,
    req: ReviewDecisionRequest,
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Explicitly defer a Dataset evaluation record."""
    conn = get_db_connection(settings)
    service = DatasetEvaluationService(conn)
    try:
        updated_eval, review = service.review_evaluation(
            evaluation_id, EVALUATION_STAGE_DEFERRED, reviewer_id=req.reviewer_id, reviewer_notes=req.notes
        )
        return {"evaluation": updated_eval.to_dict(), "review": review.to_dict()}
    except InvalidEvaluationTransitionError as ite:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(ite))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


# ---------------------------------------------------------------------------
# Metrics & Individual Evaluation Query Endpoints
# ---------------------------------------------------------------------------

@router.get("/metrics")
async def get_aggregate_evaluation_metrics_endpoint(
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Fetch aggregate evaluation metrics."""
    conn = get_db_connection(settings)
    service = RagEvaluationService(conn)
    return service.eval_repo.aggregate_metrics()


@router.get("/evaluations/{evaluation_id}")
async def get_evaluation_by_id_endpoint(
    evaluation_id: str,
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Fetch an evaluation record by evaluation ID."""
    conn = get_db_connection(settings)
    service = RagEvaluationService(conn)
    rec = service.eval_repo.get_evaluation_by_id(evaluation_id)
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Evaluation record '{evaluation_id}' not found.")
    return rec.to_dict()
