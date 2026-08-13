"""MB-30: Production Runtime Manager & One-Click Local Model Lifecycle
-- admin-only APIs. Independent prefix
(`/admin/mini-brain/runtime-manager`), disjoint from every prior Mini
Brain route prefix -- including MB-04's unrelated, pre-existing
`/admin/mini-brain/runtime`. No public routes exist in this phase.
`POST /download` is the only route in the entire codebase that
reaches a real outbound network call for this phase, and only ever on
an admin's explicit request.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.models.mini_brain_runtime_manager import (
    BenchmarkModelRequest,
    BenchmarkResponse,
    CatalogModelEntry,
    CatalogResponse,
    HardwareProbeResponse,
    InstallationResponse,
    InstalledListResponse,
    LoadModelRequest,
    ModelIdRequest,
    RuntimeEventListResponse,
    RuntimeManagerDiagnosticsResponse,
    RuntimeMemoryListResponse,
    RuntimeRowResponse,
    RuntimeStatusResponse,
    VerifyResponse,
)
from backend.services.runtime_manager_service import RuntimeManagerService

router = APIRouter(
    prefix="/admin/mini-brain/runtime-manager",
    tags=["admin-mini-brain-runtime-manager"],
    dependencies=[Depends(require_admin)],
)


def service(settings) -> RuntimeManagerService:
    return RuntimeManagerService(settings)


@router.get("/hardware", response_model=HardwareProbeResponse)
async def hardware(settings: SettingsDependency):
    return service(settings).detect_system()


@router.get("/diagnostics", response_model=RuntimeManagerDiagnosticsResponse)
async def diagnostics(settings: SettingsDependency):
    return service(settings).diagnostics()


@router.get("/catalog", response_model=CatalogResponse)
async def catalog(settings: SettingsDependency):
    return service(settings).catalog()


@router.get("/installed", response_model=InstalledListResponse)
async def installed(settings: SettingsDependency):
    return service(settings).list_installed_models()


@router.get("/status", response_model=RuntimeStatusResponse)
async def status(settings: SettingsDependency):
    return service(settings).runtime_status()


@router.get("/recommendation", response_model=CatalogModelEntry)
async def recommendation(settings: SettingsDependency):
    return service(settings).get_recommended_model()


@router.post("/download", response_model=InstallationResponse)
async def download(payload: ModelIdRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).download_model(payload.model_id, admin_id=admin.admin.public_id)


@router.post("/verify", response_model=VerifyResponse)
async def verify(payload: ModelIdRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).verify_model(payload.model_id, admin_id=admin.admin.public_id)


@router.post("/install", response_model=InstallationResponse)
async def install(payload: ModelIdRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).install_model(payload.model_id, admin_id=admin.admin.public_id)


@router.post("/load", response_model=RuntimeRowResponse)
async def load(payload: LoadModelRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).load_model(
        payload.model_id, context_length=payload.context_length, max_tokens=payload.max_tokens,
        temperature=payload.temperature, threads=payload.threads, admin_id=admin.admin.public_id,
    )


@router.post("/unload", response_model=RuntimeRowResponse)
async def unload(settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).unload_model(admin_id=admin.admin.public_id)


@router.post("/benchmark", response_model=BenchmarkResponse)
async def benchmark(payload: BenchmarkModelRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).benchmark_model(payload.model_id, prompt=payload.prompt, admin_id=admin.admin.public_id)


@router.post("/remove", response_model=InstallationResponse)
async def remove(payload: ModelIdRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).remove_model(payload.model_id, admin_id=admin.admin.public_id)


@router.get("/events", response_model=RuntimeEventListResponse)
async def events(
    settings: SettingsDependency, model_name: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=100), offset: int = Query(default=0, ge=0),
):
    return service(settings).list_events(model_name=model_name, limit=limit, offset=offset)


@router.get("/memory", response_model=RuntimeMemoryListResponse)
async def memory(
    settings: SettingsDependency, limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0),
):
    return service(settings).list_memory(limit=limit, offset=offset)


__all__ = ["router"]
