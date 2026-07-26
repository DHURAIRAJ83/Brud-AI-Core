"""Governed Admin Assistant API: dashboard understanding, proposals, Admin Review.

Every mutating action is a two-step, two-actor flow:
  1. `POST /proposals` drafts a proposal (no mutation happens here).
  2. `POST /proposals/{id}/review` lets an authenticated admin approve or
     reject it (Admin Review). Only an approved proposal may be executed.
  3. `POST /proposals/{id}/execute` runs the approved proposal through an
     allowlisted existing service call.

All three steps, plus failures, are written to the audit log by the
service layer.
"""

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import Field

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.core.validation import DomainModel
from backend.models.domain import AdminApprovalPublic
from backend.services.admin_assistant_service import ACTION_EXECUTORS, AdminAssistantService

router = APIRouter(
    prefix="/admin/assistant", tags=["admin-assistant"], dependencies=[Depends(require_admin)]
)


def service(settings) -> AdminAssistantService:
    return AdminAssistantService(settings)


class ProposalCreateRequest(DomainModel):
    action_type: str
    target_type: str
    target_public_id: str
    request_payload: dict[str, Any] = Field(default_factory=dict)
    summary: str = Field(default="", max_length=2000)


class ProposalReviewRequest(DomainModel):
    decision: str
    comment: str | None = Field(default=None, max_length=4000)


@router.get("/overview")
async def overview(settings: SettingsDependency) -> dict[str, Any]:
    """Read-only summary of every governed area of the Admin Dashboard."""
    return service(settings).dashboard_overview()


@router.get("/actions")
async def available_actions() -> dict[str, list[str]]:
    """Allowlisted action types the assistant may propose. Nothing else is possible."""
    return {"action_types": sorted(ACTION_EXECUTORS)}


@router.post("/proposals", response_model=AdminApprovalPublic)
async def create_proposal(
    payload: ProposalCreateRequest, settings: SettingsDependency, admin: CsrfDependency
) -> AdminApprovalPublic:
    return service(settings).propose(
        action_type=payload.action_type,
        target_type=payload.target_type,
        target_public_id=payload.target_public_id,
        request_payload=payload.request_payload,
        requested_by=admin.admin.public_id,
        summary=payload.summary,
    )


@router.get("/proposals")
async def list_proposals(
    settings: SettingsDependency,
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
) -> list[AdminApprovalPublic]:
    offset = (page - 1) * page_size
    return service(settings).list_proposals(status=status, limit=page_size, offset=offset)


@router.get("/proposals/{public_id}")
async def get_proposal(public_id: str, settings: SettingsDependency) -> AdminApprovalPublic:
    return service(settings).get_proposal(public_id)


@router.post("/proposals/{public_id}/review", response_model=AdminApprovalPublic)
async def review_proposal(
    public_id: str,
    payload: ProposalReviewRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> AdminApprovalPublic:
    return service(settings).review(
        public_id,
        decision=payload.decision,
        reviewed_by=admin.admin.public_id,
        comment=payload.comment,
    )


@router.post("/proposals/{public_id}/execute", response_model=AdminApprovalPublic)
async def execute_proposal(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> AdminApprovalPublic:
    return service(settings).execute(public_id, executor_public_id=admin.admin.public_id)
