"""MB-27: Brud AI Secrets & Provider Settings UI -- admin-only APIs.
Independent prefix (`/admin/mini-brain/provider-settings`). No public
routes exist in this phase at all. `POST /providers/{id}/test` is the
only route in the entire codebase that reaches
`provider_settings_connection_adapters.adapter_for_provider()` -- the
one place real outbound HTTP to a third-party provider can happen in
this phase, and only ever on an admin's explicit request.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.models.mini_brain_provider_settings import (
    CreateProviderSettingRequest,
    ImportSettingsMetadataRequest,
    SetProviderSecretRequest,
    TestConnectionRequest,
    UpdateProviderSettingRequest,
)
from backend.services.mini_brain_provider_settings_service import MiniBrainProviderSettingsService

router = APIRouter(
    prefix="/admin/mini-brain/provider-settings",
    tags=["admin-mini-brain-provider-settings"],
    dependencies=[Depends(require_admin)],
)


def service(settings) -> MiniBrainProviderSettingsService:
    return MiniBrainProviderSettingsService(settings)


@router.get("/diagnostics")
async def diagnostics(settings: SettingsDependency):
    return service(settings).diagnostics()


@router.get("/providers")
async def list_providers(
    settings: SettingsDependency,
    provider_type: str | None = Query(default=None),
    enabled: bool | None = Query(default=None),
):
    return service(settings).list_settings(provider_type=provider_type, enabled=enabled)


@router.post("/providers")
async def create_provider(payload: CreateProviderSettingRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).create_provider_setting(
        provider_key=payload.provider_key, enabled=payload.enabled, config=payload.config,
        admin_id=admin.admin.public_id,
    )


@router.get("/providers/{setting_id}")
async def get_provider(setting_id: str, settings: SettingsDependency):
    return service(settings).get_setting(setting_id)


@router.patch("/providers/{setting_id}")
async def update_provider(
    setting_id: str, payload: UpdateProviderSettingRequest, settings: SettingsDependency, admin: CsrfDependency,
):
    return service(settings).update_provider_setting(setting_id, config=payload.config, admin_id=admin.admin.public_id)


@router.post("/providers/{setting_id}/enable")
async def enable_provider(setting_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).enable_provider(setting_id, admin_id=admin.admin.public_id)


@router.post("/providers/{setting_id}/disable")
async def disable_provider(setting_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).disable_provider(setting_id, admin_id=admin.admin.public_id)


@router.post("/providers/{setting_id}/secrets")
async def set_secret(
    setting_id: str, payload: SetProviderSecretRequest, settings: SettingsDependency, admin: CsrfDependency,
):
    return service(settings).set_secret(
        setting_id, secret_name=payload.secret_name, raw_value=payload.value, admin_id=admin.admin.public_id,
    )


@router.delete("/providers/{setting_id}/secrets/{secret_name}")
async def delete_secret(setting_id: str, secret_name: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).delete_secret(setting_id, secret_name=secret_name, admin_id=admin.admin.public_id)


@router.post("/providers/{setting_id}/test")
async def test_connection(
    setting_id: str, payload: TestConnectionRequest, settings: SettingsDependency, admin: CsrfDependency,
):
    return service(settings).test_connection(
        setting_id, secret_name=payload.secret_name, timeout_seconds=payload.timeout_seconds,
        admin_id=admin.admin.public_id,
    )


@router.get("/providers/{setting_id}/audit")
async def provider_audit(
    setting_id: str, settings: SettingsDependency,
    limit: int = Query(default=100, ge=1, le=100), offset: int = Query(default=0, ge=0),
):
    return service(settings).list_audit_events(setting_id, limit=limit, offset=offset)


@router.get("/export")
async def export_settings(settings: SettingsDependency):
    return service(settings).export_settings()


@router.post("/import-metadata")
async def import_metadata(payload: ImportSettingsMetadataRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).import_settings_metadata(payload.model_dump(), admin_id=admin.admin.public_id)


@router.post("/providers/{setting_id}/archive")
async def archive_provider(setting_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).archive_provider_setting(setting_id, admin_id=admin.admin.public_id)


@router.get("/memory")
async def list_memory(
    settings: SettingsDependency,
    limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0),
):
    return service(settings).list_memory(limit=limit, offset=offset)


__all__ = ["router"]
