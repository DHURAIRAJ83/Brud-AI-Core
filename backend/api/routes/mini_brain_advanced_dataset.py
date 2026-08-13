"""MB-05.1: Advanced Dataset Intelligence -- authenticated admin-only
APIs. Independent prefix (`/admin/mini-brain/dataset-advanced`),
separate from `/admin/datasets` and `/admin/mini-brain/dataset-
intelligence` (MB-05's own routes) -- every route here ends in a
read-only call, composing MB-05's service and Dataset Studio's own
`DatasetService`, neither of which is ever modified.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.database.repositories.dataset_admin import DatasetAdminRepository
from backend.models.mini_brain_advanced_dataset import AdvancedDatasetRequest
from backend.services.dataset_service import DatasetService
from backend.services.mini_brain_advanced_dataset_service import MiniBrainAdvancedDatasetService
from backend.services.mini_brain_dataset_intelligence_service import MiniBrainDatasetIntelligenceService

router = APIRouter(
    prefix="/admin/mini-brain/dataset-advanced",
    tags=["admin-mini-brain-dataset-advanced"],
    dependencies=[Depends(require_admin)],
)


def service(settings) -> MiniBrainAdvancedDatasetService:
    dataset_service = DatasetService(DatasetAdminRepository(settings.resolved_database_path))
    dataset_intelligence_service = MiniBrainDatasetIntelligenceService(dataset_service)
    return MiniBrainAdvancedDatasetService(dataset_service, dataset_intelligence_service)


@router.post("/conflicts")
async def conflicts(payload: AdvancedDatasetRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).conflicts(payload.source_public_id)


@router.post("/bias")
async def bias(payload: AdvancedDatasetRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).bias(payload.source_public_id)


@router.post("/coverage")
async def coverage(payload: AdvancedDatasetRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).coverage(payload.source_public_id)


@router.post("/difficulty")
async def difficulty(payload: AdvancedDatasetRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).difficulty(payload.source_public_id)


@router.post("/curriculum")
async def curriculum(payload: AdvancedDatasetRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).curriculum(payload.source_public_id)


@router.post("/knowledge-gap")
async def knowledge_gap(payload: AdvancedDatasetRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).knowledge_gap(payload.source_public_id)


@router.post("/risk")
async def risk(payload: AdvancedDatasetRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).risk(payload.source_public_id)


@router.post("/graph")
async def graph(payload: AdvancedDatasetRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).graph(payload.source_public_id)


@router.post("/priority")
async def priority(payload: AdvancedDatasetRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).priority(payload.source_public_id)


@router.post("/report")
async def report(payload: AdvancedDatasetRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).report(payload.source_public_id)


@router.get("/diagnostics")
async def diagnostics(settings: SettingsDependency):
    return service(settings).diagnostics()
