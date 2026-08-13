"""MB-29: Local Model Auto-Setup & Provider Configuration Center --
admin-only APIs. Independent prefix (`/admin/mini-brain/local-setup`),
disjoint from every prior Mini Brain route prefix. No public routes
exist in this phase.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.models.local_setup import (
    HardwareSummaryResponse,
    LocalSetupDiagnosticsResponse,
    ProviderCatalogResponse,
    RecommendationsResponse,
    SaveLocalModelRequest,
    SaveProviderRequest,
    ScanModelsResponse,
    SetupGuideResponse,
)
from backend.models.mini_brain_provider_settings import ProviderSettingResponse
from backend.services.local_setup_service import LocalSetupService

router = APIRouter(
    prefix="/admin/mini-brain/local-setup",
    tags=["admin-mini-brain-local-setup"],
    dependencies=[Depends(require_admin)],
)


def service(settings) -> LocalSetupService:
    return LocalSetupService(settings)


@router.get("/hardware", response_model=HardwareSummaryResponse)
async def hardware(settings: SettingsDependency):
    return service(settings).hardware_summary()


@router.get("/scan-models", response_model=ScanModelsResponse)
async def scan_models(settings: SettingsDependency):
    return service(settings).scan_local_models()


@router.get("/recommendations", response_model=RecommendationsResponse)
async def recommendations(settings: SettingsDependency):
    return service(settings).recommend_models()


@router.post("/save-local-model", response_model=ProviderSettingResponse)
async def save_local_model(payload: SaveLocalModelRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).save_local_model_configuration(
        model_path=payload.model_path, context_length=payload.context_length, max_tokens=payload.max_tokens,
        temperature=payload.temperature, threads=payload.threads, additional_model_dirs=payload.additional_model_dirs,
        admin_id=admin.admin.public_id,
    )


@router.post("/save-provider", response_model=ProviderSettingResponse)
async def save_provider(payload: SaveProviderRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).save_external_provider_configuration(
        provider_key=payload.provider_key, api_key=payload.api_key, model=payload.model,
        enabled=payload.enabled, admin_id=admin.admin.public_id,
    )


@router.get("/providers/catalog", response_model=ProviderCatalogResponse)
async def providers_catalog(settings: SettingsDependency):
    return service(settings).provider_catalog()


@router.get("/setup-guide", response_model=SetupGuideResponse)
async def setup_guide(settings: SettingsDependency):
    return service(settings).build_setup_guide()


@router.get("/diagnostics", response_model=LocalSetupDiagnosticsResponse)
async def diagnostics(settings: SettingsDependency):
    return service(settings).diagnostics()


__all__ = ["router"]
