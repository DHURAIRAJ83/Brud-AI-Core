"""MB-05: Dataset Intelligence -- authenticated admin-only APIs.
Independent prefix (`/admin/mini-brain/dataset-intelligence`),
separate from `/admin/datasets` (Dataset Studio's own routes) --
these routes never modify anything; every one of them ends in a
read-only call into the existing, unmodified `DatasetService`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.database.repositories.dataset_admin import DatasetAdminRepository
from backend.models.mini_brain_dataset_intelligence import DatasetIntelligenceRequest
from backend.services.dataset_service import DatasetService
from backend.services.mini_brain_dataset_intelligence_service import MiniBrainDatasetIntelligenceService

router = APIRouter(
    prefix="/admin/mini-brain/dataset-intelligence",
    tags=["admin-mini-brain-dataset-intelligence"],
    dependencies=[Depends(require_admin)],
)


def service(settings) -> MiniBrainDatasetIntelligenceService:
    dataset_service = DatasetService(DatasetAdminRepository(settings.resolved_database_path))
    return MiniBrainDatasetIntelligenceService(dataset_service)


@router.post("/analyze")
async def analyze(payload: DatasetIntelligenceRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).analyze(payload.source_public_id)


@router.post("/quality")
async def quality(payload: DatasetIntelligenceRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).quality(payload.source_public_id)


@router.post("/language")
async def language(payload: DatasetIntelligenceRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).language(payload.source_public_id)


@router.post("/domain")
async def domain(payload: DatasetIntelligenceRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).domain(payload.source_public_id)


@router.post("/training")
async def training(payload: DatasetIntelligenceRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).training(payload.source_public_id)


@router.post("/rag")
async def rag(payload: DatasetIntelligenceRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).rag(payload.source_public_id)


@router.post("/sft")
async def sft(payload: DatasetIntelligenceRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).sft(payload.source_public_id)


@router.post("/tokens")
async def tokens(payload: DatasetIntelligenceRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).tokens(payload.source_public_id)


@router.post("/report")
async def report(payload: DatasetIntelligenceRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).report(payload.source_public_id)


@router.get("/diagnostics")
async def diagnostics(settings: SettingsDependency):
    return service(settings).diagnostics()
