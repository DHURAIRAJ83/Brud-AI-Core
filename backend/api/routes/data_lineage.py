"""Phase 7 (Data Studio) source-to-model Data Lineage API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.models.governed_builds import CreateLineageEdgeRequest
from backend.services.lineage_graph_service import LineageGraphService

router = APIRouter(
    prefix="/admin/data-lineage",
    tags=["admin-data-lineage"],
    dependencies=[Depends(require_admin)],
)


def lineage_service(settings) -> LineageGraphService:
    return LineageGraphService(settings)


@router.post("/edges")
async def create_edge(
    payload: CreateLineageEdgeRequest, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return lineage_service(settings).create_edge(
        upstream_entity_type=payload.upstream_entity_type,
        upstream_entity_id=payload.upstream_entity_id,
        downstream_entity_type=payload.downstream_entity_type,
        downstream_entity_id=payload.downstream_entity_id,
        relationship_type=payload.relationship_type,
        metadata=payload.metadata,
        admin_id=admin.admin.public_id,
    )


@router.get("/entity/{entity_type}/{entity_id}")
async def trace_entity(
    entity_type: str, entity_id: str, settings: SettingsDependency
) -> dict[str, Any]:
    return lineage_service(settings).trace(entity_type, entity_id)


@router.get("/entity/{entity_type}/{entity_id}/upstream")
async def entity_upstream(
    entity_type: str, entity_id: str, settings: SettingsDependency
) -> dict[str, Any]:
    return lineage_service(settings).upstream_of(entity_type, entity_id)


@router.get("/entity/{entity_type}/{entity_id}/downstream")
async def entity_downstream(
    entity_type: str, entity_id: str, settings: SettingsDependency
) -> dict[str, Any]:
    return lineage_service(settings).downstream_of(entity_type, entity_id)


@router.get("/source/{source_public_id}")
async def source_lineage(source_public_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return lineage_service(settings).for_source(source_public_id)


@router.get("/model-release/{release_public_id}")
async def model_release_lineage(
    release_public_id: str, settings: SettingsDependency
) -> dict[str, Any]:
    return lineage_service(settings).for_model_release(release_public_id)
