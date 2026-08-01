"""Phase 5 (Data Studio) Structured Record Candidate API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.models.semantic_chunks import (
    CreateStructuredRecordRequest,
    ReviseStructuredRecordRequest,
    UsageCheckRequest,
)
from backend.services.structured_record_service import StructuredRecordCandidateService

router = APIRouter(
    prefix="/admin/structured-records",
    tags=["admin-structured-records"],
    dependencies=[Depends(require_admin)],
)


def candidate_service(settings) -> StructuredRecordCandidateService:
    return StructuredRecordCandidateService(settings)


@router.get("")
async def list_candidates(
    settings: SettingsDependency,
    status: str | None = None,
    record_type: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
) -> dict[str, Any]:
    return candidate_service(settings).list_candidates(
        status=status, record_type=record_type, page=page, page_size=page_size
    )


@router.post("/from-chunks")
async def create_from_chunks(
    payload: CreateStructuredRecordRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return candidate_service(settings).create_from_chunks(
        record_type=payload.record_type,
        chunk_public_ids=payload.chunk_public_ids,
        fields=payload.fields,
        requested_uses=payload.requested_uses,
        admin_id=admin.admin.public_id,
    )


@router.get("/{candidate_public_id}")
async def get_candidate(candidate_public_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return candidate_service(settings).candidate(candidate_public_id)


@router.get("/{candidate_public_id}/history")
async def history(candidate_public_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return candidate_service(settings).history(candidate_public_id)


@router.post("/{candidate_public_id}/revision")
async def revise(
    candidate_public_id: str,
    payload: ReviseStructuredRecordRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return candidate_service(settings).revise(
        candidate_public_id,
        fields=payload.fields,
        change_summary=payload.change_summary,
        admin_id=admin.admin.public_id,
    )


@router.post("/{candidate_public_id}/submit-review")
async def submit_review(
    candidate_public_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return candidate_service(settings).submit_review(candidate_public_id, admin.admin.public_id)


@router.post("/{candidate_public_id}/approve")
async def approve(
    candidate_public_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return candidate_service(settings).review(
        candidate_public_id, review_status="approved", comments="", admin_id=admin.admin.public_id
    )


@router.post("/{candidate_public_id}/reject")
async def reject(
    candidate_public_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return candidate_service(settings).review(
        candidate_public_id, review_status="rejected", comments="", admin_id=admin.admin.public_id
    )


@router.post("/{candidate_public_id}/archive")
async def archive(
    candidate_public_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return candidate_service(settings).archive(candidate_public_id, admin.admin.public_id)


@router.post("/{candidate_public_id}/usage-check")
async def usage_check(
    candidate_public_id: str,
    payload: UsageCheckRequest,
    settings: SettingsDependency,
) -> dict[str, Any]:
    return candidate_service(settings).usage_check(candidate_public_id, payload.target_use)


@router.post("/{candidate_public_id}/conflict-check")
async def conflict_check(candidate_public_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return candidate_service(settings).conflict_check(candidate_public_id)


@router.post("/{candidate_public_id}/export-dataset")
async def export_dataset(
    candidate_public_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return candidate_service(settings).export_to_dataset(candidate_public_id, admin.admin.public_id)


@router.post("/{candidate_public_id}/create-rag-candidate")
async def create_rag_candidate(
    candidate_public_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return candidate_service(settings).create_rag_candidate(
        candidate_public_id, admin.admin.public_id
    )
