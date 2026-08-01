"""Phase 20 Step 29 -- Admin-only API for the deterministic tool
gateway, under `/api/admin/deterministic-tools`. Read-only registry/
execution-event visibility plus one bounded, audited, CSRF-protected
test action -- never accepts an arbitrary tool name outside the closed
registry, never enables external MCP.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Query
from pydantic import Field

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.core.validation import DomainModel
from backend.database.repositories.knowledge_gap import KnowledgeGapRepository
from backend.database.repositories.trusted_web_tool_gateway import TrustedWebToolGatewayRepository
from backend.services.deterministic_tool_execution_service import DeterministicToolExecutionService
from backend.services.deterministic_tool_registry import list_tool_descriptors
from core_model.tool_gateway.mcp_contract import ToolInvocationRequest, ToolPermissionContext

router = APIRouter(
    prefix="/admin/deterministic-tools",
    tags=["deterministic-tools"],
    dependencies=[Depends(require_admin)],
)


class ToolTestRequest(DomainModel):
    tool_name: str = Field(min_length=1, max_length=64)
    input_payload: dict[str, Any] = Field(default_factory=dict)


def _repository(settings: SettingsDependency) -> TrustedWebToolGatewayRepository:
    return TrustedWebToolGatewayRepository(settings.resolved_database_path)


@router.get("/overview")
async def get_overview(settings: SettingsDependency) -> dict[str, Any]:
    repo = _repository(settings)
    overview = repo.tool_gateway_overview()
    overview["tool_demand"] = KnowledgeGapRepository(
        settings.resolved_database_path
    ).tool_demand_summary()
    overview["external_mcp_enabled"] = settings.external_mcp_enabled
    return overview


@router.get("/registry")
async def get_registry() -> dict[str, Any]:
    return {"tools": [asdict(descriptor) for descriptor in list_tool_descriptors()]}


@router.get("/execution-events")
async def list_execution_events(
    settings: SettingsDependency,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    tool_name: str | None = None,
) -> dict[str, Any]:
    repo = _repository(settings)
    return {
        "items": repo.list_tool_executions(limit=limit, offset=offset, tool_name=tool_name)
    }


@router.post("/test")
async def test_tool(
    payload: ToolTestRequest, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    """Admin-triggered execution test through the exact same closed
    registry + validation pipeline a public request uses
    (`is_public_request=False`, `is_admin_request=True` -- an
    `admin_enabled=False` tool is still refused here) -- an unknown
    `tool_name` is rejected the same way it would be for any caller,
    never dynamically resolved."""

    service = DeterministicToolExecutionService(settings)
    result = service.execute(
        ToolInvocationRequest(
            tool_name=payload.tool_name, input_payload=payload.input_payload,
            request_id=f"admin-test:{admin.admin.public_id}:{uuid4()}", is_public_request=False,
        ),
        ToolPermissionContext(
            is_public_request=False, is_admin_request=True,
            external_mcp_enabled=settings.external_mcp_enabled,
        ),
    )
    return {
        "tool_name": result.tool_name,
        "tool_version": result.tool_version,
        "status": result.status,
        "output_payload": result.output_payload,
        "error_code": result.error_code,
        "latency_ms": result.latency_ms,
    }


__all__ = ["router"]
