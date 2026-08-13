"""MB-40: External AI Gateway -> Dataset Studio bridge -- admin-only API.

Deliberately a separate route file/prefix from `mini_brain_external_ai
_gateway.py`, whose own docstring states no route there ever writes
into Dataset Studio -- that claim stays true; this bridge's one route
lives here instead, and only ever accepts a session that already has a
real, human-made `admin_accepted` decision recorded through the
gateway's own, unmodified `admin_review()` flow.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.models.external_gateway_dataset_bridge import (
    ExportAcceptedSessionRequest,
    ExportAcceptedSessionResponse,
)
from backend.services.external_gateway_dataset_bridge_service import ExternalGatewayDatasetBridgeService

router = APIRouter(
    prefix="/admin/mini-brain/external-ai-gateway-dataset-bridge",
    tags=["admin-mini-brain-external-ai-gateway-dataset-bridge"],
    dependencies=[Depends(require_admin)],
)


def service(settings) -> ExternalGatewayDatasetBridgeService:
    return ExternalGatewayDatasetBridgeService(settings)


@router.post("/sessions/{session_id}/export-to-dataset", response_model=ExportAcceptedSessionResponse)
async def export_accepted_session(
    session_id: str, payload: ExportAcceptedSessionRequest, settings: SettingsDependency, admin: CsrfDependency,
):
    return service(settings).export_accepted_session(
        session_id,
        admin_id=admin.admin.public_id,
        target_source_public_id=payload.target_source_public_id,
        ingest_to_rag=payload.ingest_to_rag,
        rag_knowledge_space_public_id=payload.rag_knowledge_space_public_id,
        build_rag_index=payload.build_rag_index,
        retrieval_profile_name=payload.retrieval_profile_name,
    )


__all__ = ["router"]
