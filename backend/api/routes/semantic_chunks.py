"""Phase 5 (Data Studio) Semantic Chunk Studio API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.models.semantic_chunks import (
    AssignParentRequest,
    ClassifyRequest,
    EditTextRequest,
    ManualChunkCreate,
    MergeRequest,
    MoveBoundaryRequest,
    ReorderRequest,
    ReviewActionRequest,
    SplitRequest,
)
from backend.services.semantic_chunk_service import (
    ChunkConflictService,
    SemanticChunkQualityService,
    SemanticChunkReviewService,
    SemanticChunkService,
)

router = APIRouter(
    prefix="/admin/semantic-chunks",
    tags=["admin-semantic-chunks"],
    dependencies=[Depends(require_admin)],
)


def chunk_service(settings) -> SemanticChunkService:
    return SemanticChunkService(settings)


def review_service(settings) -> SemanticChunkReviewService:
    return SemanticChunkReviewService(settings)


def quality_service(settings) -> SemanticChunkQualityService:
    return SemanticChunkQualityService(settings)


def conflict_service(settings) -> ChunkConflictService:
    return ChunkConflictService(settings)


# --- document-scoped ---------------------------------------------------


@router.post("/document/{document_public_id}/generate")
async def generate(
    document_public_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return chunk_service(settings).generate(document_public_id, admin.admin.public_id)


@router.get("/document/{document_public_id}")
async def list_chunks(
    document_public_id: str,
    settings: SettingsDependency,
    status: str | None = None,
    chunk_type: str | None = None,
    parent_chunk_public_id: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    return chunk_service(settings).list_chunks(
        document_public_id,
        status=status,
        chunk_type=chunk_type,
        parent_chunk_public_id=parent_chunk_public_id,
        page=page,
        page_size=page_size,
    )


@router.post("/document/{document_public_id}/reorder")
async def reorder(
    document_public_id: str,
    payload: ReorderRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return chunk_service(settings).reorder(
        document_public_id, payload.chunk_public_ids, admin.admin.public_id
    )


@router.get("/document/{document_public_id}/coverage")
async def coverage_report(document_public_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return conflict_service(settings).coverage_report(document_public_id)


@router.post("/document/{document_public_id}/manual")
async def create_manual_chunk(
    document_public_id: str,
    payload: ManualChunkCreate,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return chunk_service(settings).create_manual_chunk(
        document_public_id,
        text=payload.text,
        chunk_type=payload.chunk_type,
        page_number=payload.page_number,
        language=payload.language,
        admin_id=admin.admin.public_id,
    )


# --- chunk-scoped -------------------------------------------------------


@router.get("/{chunk_public_id}")
async def get_chunk(chunk_public_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return chunk_service(settings).chunk(chunk_public_id)


@router.get("/{chunk_public_id}/history")
async def history(chunk_public_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return chunk_service(settings).history(chunk_public_id)


@router.get("/{chunk_public_id}/classification-suggestions")
async def classification_suggestions(
    chunk_public_id: str, settings: SettingsDependency
) -> dict[str, Any]:
    return {"items": chunk_service(settings).classification_suggestions(chunk_public_id)}


@router.patch("/{chunk_public_id}")
async def edit_text(
    chunk_public_id: str,
    payload: EditTextRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return chunk_service(settings).edit_text(
        chunk_public_id, payload.text, admin.admin.public_id, change_summary=payload.change_summary
    )


@router.post("/{chunk_public_id}/split")
async def split(
    chunk_public_id: str,
    payload: SplitRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return chunk_service(settings).split(chunk_public_id, payload.split_at, admin.admin.public_id)


@router.post("/{chunk_public_id}/merge")
async def merge(
    chunk_public_id: str,
    payload: MergeRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return chunk_service(settings).merge(
        chunk_public_id, payload.other_chunk_public_id, admin.admin.public_id
    )


@router.post("/{chunk_public_id}/move-boundary")
async def move_boundary(
    chunk_public_id: str,
    payload: MoveBoundaryRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return chunk_service(settings).move_boundary(
        chunk_public_id,
        payload.neighbor_chunk_public_id,
        edge=payload.edge,
        new_offset=payload.new_offset,
        admin_id=admin.admin.public_id,
    )


@router.post("/{chunk_public_id}/classify")
async def classify(
    chunk_public_id: str,
    payload: ClassifyRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return chunk_service(settings).classify(
        chunk_public_id, admin.admin.public_id, chunk_type=payload.chunk_type, notes=payload.notes
    )


@router.post("/{chunk_public_id}/assign-parent")
async def assign_parent(
    chunk_public_id: str,
    payload: AssignParentRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return chunk_service(settings).assign_parent(
        chunk_public_id, payload.parent_chunk_public_id, admin.admin.public_id
    )


@router.post("/{chunk_public_id}/archive")
async def archive(
    chunk_public_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return chunk_service(settings).archive(chunk_public_id, admin.admin.public_id)


@router.post("/{chunk_public_id}/restore")
async def restore(
    chunk_public_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return chunk_service(settings).restore(chunk_public_id, admin.admin.public_id)


# --- review lifecycle ----------------------------------------------------


@router.post("/{chunk_public_id}/submit-review")
async def submit_review(
    chunk_public_id: str,
    payload: ReviewActionRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return review_service(settings).submit_review(
        chunk_public_id, admin.admin.public_id, payload.notes
    )


@router.post("/{chunk_public_id}/approve")
async def approve(
    chunk_public_id: str,
    payload: ReviewActionRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return review_service(settings).approve(chunk_public_id, admin.admin.public_id, payload.notes)


@router.post("/{chunk_public_id}/reject")
async def reject(
    chunk_public_id: str,
    payload: ReviewActionRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return review_service(settings).reject(chunk_public_id, admin.admin.public_id, payload.notes)


@router.post("/{chunk_public_id}/exclude")
async def exclude(
    chunk_public_id: str,
    payload: ReviewActionRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return review_service(settings).exclude(chunk_public_id, admin.admin.public_id, payload.notes)


@router.post("/{chunk_public_id}/reopen")
async def reopen(
    chunk_public_id: str,
    payload: ReviewActionRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return review_service(settings).reopen(chunk_public_id, admin.admin.public_id, payload.notes)


@router.post("/{chunk_public_id}/request-boundary-correction")
async def request_boundary_correction(
    chunk_public_id: str,
    payload: ReviewActionRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return review_service(settings).request_boundary_correction(
        chunk_public_id, admin.admin.public_id, payload.notes
    )


@router.post("/{chunk_public_id}/request-classification-correction")
async def request_classification_correction(
    chunk_public_id: str,
    payload: ReviewActionRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return review_service(settings).request_classification_correction(
        chunk_public_id, admin.admin.public_id, payload.notes
    )


@router.get("/{chunk_public_id}/review-history")
async def review_history(chunk_public_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return review_service(settings).review_history(chunk_public_id)


# --- quality / duplicates ------------------------------------------------


@router.post("/{chunk_public_id}/quality-check")
async def quality_check(chunk_public_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return quality_service(settings).assess(chunk_public_id)


@router.post("/{chunk_public_id}/duplicate-check")
async def duplicate_check(chunk_public_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return quality_service(settings).duplicate_check(chunk_public_id)
