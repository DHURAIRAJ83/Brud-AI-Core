"""Phase 6 (Data Studio) unified Quality, Duplicate, Conflict & Approval
governance API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.models.governance import (
    AddReviewNoteRequest,
    AssignReviewRequest,
    OpenReviewItemRequest,
    OverrideApprovalRequest,
    ResolveGroupRequest,
    SetReviewStatusRequest,
)
from backend.services.governance_service import (
    GovernanceApprovalService,
    GovernanceConflictService,
    GovernanceDuplicateService,
    GovernanceExportReadinessService,
    GovernanceQualityService,
    GovernanceReviewService,
)

router = APIRouter(
    prefix="/admin/data-governance",
    tags=["admin-data-governance"],
    dependencies=[Depends(require_admin)],
)


def review_service(settings) -> GovernanceReviewService:
    return GovernanceReviewService(settings)


def quality_service(settings) -> GovernanceQualityService:
    return GovernanceQualityService(settings)


def duplicate_service(settings) -> GovernanceDuplicateService:
    return GovernanceDuplicateService(settings)


def conflict_service(settings) -> GovernanceConflictService:
    return GovernanceConflictService(settings)


def approval_service(settings) -> GovernanceApprovalService:
    return GovernanceApprovalService(settings)


def readiness_service(settings) -> GovernanceExportReadinessService:
    return GovernanceExportReadinessService(settings)


# --- review queue --------------------------------------------------------


@router.get("/queue")
async def queue(
    settings: SettingsDependency,
    status: str | None = None,
    priority: str | None = None,
    entity_type: str | None = None,
    assigned_admin_public_id: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
) -> dict[str, Any]:
    return review_service(settings).queue(
        status=status,
        priority=priority,
        entity_type=entity_type,
        assigned_admin_public_id=assigned_admin_public_id,
        page=page,
        page_size=page_size,
    )


@router.post("/review/open")
async def open_review_item(
    payload: OpenReviewItemRequest, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return review_service(settings).open_or_reuse(
        entity_type=payload.entity_type,
        entity_public_id=payload.entity_public_id,
        reason=payload.reason,
        admin_id=admin.admin.public_id,
        priority=payload.priority,
        entity_revision_public_id=payload.entity_revision_public_id,
        source_public_id=payload.source_public_id,
        document_public_id=payload.document_public_id,
        page_public_id=payload.page_public_id,
    )


@router.get("/review/{review_public_id}")
async def get_review_item(review_public_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return review_service(settings).get(review_public_id)


@router.get("/review/{review_public_id}/history")
async def review_item_history(
    review_public_id: str, settings: SettingsDependency
) -> dict[str, Any]:
    return review_service(settings).history(review_public_id)


@router.post("/review/{review_public_id}/assign")
async def assign_review_item(
    review_public_id: str,
    payload: AssignReviewRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return review_service(settings).assign(
        review_public_id, payload.assignee_admin_public_id, admin_id=admin.admin.public_id
    )


@router.post("/review/{review_public_id}/status")
async def set_review_item_status(
    review_public_id: str,
    payload: SetReviewStatusRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return review_service(settings).set_status(
        review_public_id, payload.status, admin_id=admin.admin.public_id, notes=payload.notes
    )


@router.post("/review/{review_public_id}/note")
async def add_review_item_note(
    review_public_id: str,
    payload: AddReviewNoteRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return review_service(settings).add_note(
        review_public_id, payload.note, admin_id=admin.admin.public_id
    )


# --- quality --------------------------------------------------------------


@router.post("/quality/{entity_type}/{entity_public_id}/assess")
async def assess_quality(
    entity_type: str,
    entity_public_id: str,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return quality_service(settings).assess(
        entity_type, entity_public_id, admin_id=admin.admin.public_id
    )


# --- duplicates -------------------------------------------------------------


@router.get("/duplicates")
async def list_duplicate_groups(
    settings: SettingsDependency, status: str | None = None
) -> dict[str, Any]:
    return duplicate_service(settings).list_groups(status=status)


@router.post("/duplicates/manual-data/{record_public_id}/sync")
async def sync_manual_data_duplicate(
    record_public_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return duplicate_service(settings).sync_manual_data_duplicate(
        record_public_id, admin_id=admin.admin.public_id
    )


@router.post("/duplicates/chunk/{chunk_public_id}/sync")
async def sync_chunk_duplicate(
    chunk_public_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return duplicate_service(settings).sync_chunk_duplicate(
        chunk_public_id, admin_id=admin.admin.public_id
    )


@router.post("/duplicates/{group_public_id}/resolve")
async def resolve_duplicate_group(
    group_public_id: str,
    payload: ResolveGroupRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return duplicate_service(settings).resolve(
        group_public_id,
        resolution_action=payload.resolution_action,
        resolution_reason=payload.resolution_reason,
        admin_id=admin.admin.public_id,
        selected_entities=[entity.model_dump() for entity in payload.selected_entities],
    )


# --- conflicts --------------------------------------------------------------


@router.get("/conflicts")
async def list_conflict_groups(
    settings: SettingsDependency, status: str | None = None
) -> dict[str, Any]:
    return conflict_service(settings).list_groups(status=status)


@router.post("/conflicts/structured-record/{candidate_public_id}/sync")
async def sync_structured_record_conflict(
    candidate_public_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return conflict_service(settings).sync_structured_record_conflict(
        candidate_public_id, admin_id=admin.admin.public_id
    )


@router.post("/conflicts/{group_public_id}/resolve")
async def resolve_conflict_group(
    group_public_id: str,
    payload: ResolveGroupRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return conflict_service(settings).resolve(
        group_public_id,
        resolution_action=payload.resolution_action,
        resolution_reason=payload.resolution_reason,
        admin_id=admin.admin.public_id,
        selected_entities=[entity.model_dump() for entity in payload.selected_entities],
    )


# --- approvals --------------------------------------------------------------


@router.get("/approvals/{entity_type}/{entity_public_id}")
async def approval_status(
    entity_type: str, entity_public_id: str, settings: SettingsDependency
) -> dict[str, Any]:
    return approval_service(settings).status(entity_type, entity_public_id)


@router.post("/approvals/{entity_type}/{entity_public_id}/{target_use}/evaluate")
async def evaluate_approval(
    entity_type: str,
    entity_public_id: str,
    target_use: str,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return approval_service(settings).evaluate(
        entity_type, entity_public_id, target_use, admin_id=admin.admin.public_id
    )


@router.post("/approvals/{entity_type}/{entity_public_id}/{target_use}/override")
async def override_approval(
    entity_type: str,
    entity_public_id: str,
    target_use: str,
    payload: OverrideApprovalRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return approval_service(settings).override(
        entity_type,
        entity_public_id,
        target_use,
        payload.decision,
        reason=payload.reason,
        admin_id=admin.admin.public_id,
    )


# --- export/handoff readiness -----------------------------------------------


@router.get("/export-readiness/{entity_type}/{entity_public_id}/{target_use}")
async def export_readiness(
    entity_type: str, entity_public_id: str, target_use: str, settings: SettingsDependency
) -> dict[str, Any]:
    return readiness_service(settings).check(entity_type, entity_public_id, target_use)
