"""Phase 2 (Data Studio) Source, Rights & Usage Registry API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.database.repositories.data_sources import DataSourceRepository
from backend.models.data_sources import (
    DataSourceCreate,
    DataSourcePatch,
    LinkCreate,
    SourceRightsUpsert,
    UsageCheckRequest,
    VerificationActionRequest,
)
from backend.services.data_source_service import (
    SourceRegistryService,
    SourceRightsService,
    SourceUsagePolicyService,
    SourceVerificationService,
)

router = APIRouter(
    prefix="/admin/data-sources", tags=["admin-data-sources"], dependencies=[Depends(require_admin)]
)


def _repository(settings) -> DataSourceRepository:
    return DataSourceRepository(settings.resolved_database_path)


def registry_service(settings) -> SourceRegistryService:
    return SourceRegistryService(_repository(settings), settings)


def rights_service(settings) -> SourceRightsService:
    return SourceRightsService(_repository(settings), settings)


def usage_service(settings) -> SourceUsagePolicyService:
    return SourceUsagePolicyService(_repository(settings), settings)


def verification_service(settings) -> SourceVerificationService:
    return SourceVerificationService(_repository(settings))


# --- data sources -------------------------------------------------------


@router.get("")
async def list_sources(
    settings: SettingsDependency,
    status: str | None = None,
    source_type: str | None = None,
    search: str | None = Query(default=None, max_length=200),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
) -> dict[str, Any]:
    return registry_service(settings).list(
        status=status, source_type=source_type, search=search, page=page, page_size=page_size
    )


@router.post("")
async def create_source(
    payload: DataSourceCreate, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return registry_service(settings).create(payload, admin_id=admin.admin.public_id)


@router.get("/{source_id}")
async def get_source(source_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return registry_service(settings).get(source_id)


@router.patch("/{source_id}")
async def update_source(
    source_id: str, payload: DataSourcePatch, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return registry_service(settings).update(source_id, payload, admin_id=admin.admin.public_id)


@router.post("/{source_id}/archive")
async def archive_source(
    source_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return registry_service(settings).archive(source_id, admin_id=admin.admin.public_id)


@router.post("/{source_id}/restore")
async def restore_source(
    source_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return registry_service(settings).restore(source_id, admin_id=admin.admin.public_id)


# --- rights ---------------------------------------------------------------


@router.get("/{source_id}/rights")
async def get_rights(source_id: str, settings: SettingsDependency) -> dict[str, Any] | None:
    return rights_service(settings).get(source_id)


@router.put("/{source_id}/rights")
async def upsert_rights(
    source_id: str,
    payload: SourceRightsUpsert,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return rights_service(settings).upsert(source_id, payload, admin_id=admin.admin.public_id)


@router.post("/{source_id}/submit-review")
async def submit_review(
    source_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return rights_service(settings).submit_review(source_id, admin_id=admin.admin.public_id)


@router.post("/{source_id}/verify")
async def verify_source(
    source_id: str,
    payload: VerificationActionRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return rights_service(settings).verify(source_id, payload, admin_id=admin.admin.public_id)


@router.post("/{source_id}/restrict")
async def restrict_source(
    source_id: str,
    payload: VerificationActionRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return rights_service(settings).restrict(source_id, payload, admin_id=admin.admin.public_id)


@router.post("/{source_id}/reject")
async def reject_source(
    source_id: str,
    payload: VerificationActionRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return rights_service(settings).reject(source_id, payload, admin_id=admin.admin.public_id)


# --- links ------------------------------------------------------------------


@router.get("/{source_id}/links")
async def list_links(source_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return registry_service(settings).list_links(source_id)


@router.post("/{source_id}/links")
async def create_link(
    source_id: str, payload: LinkCreate, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return registry_service(settings).create_link(
        source_id, payload, admin_id=admin.admin.public_id
    )


@router.delete("/{source_id}/links/{link_id}")
async def delete_link(
    source_id: str, link_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, str]:
    registry_service(settings).delete_link(source_id, link_id, admin_id=admin.admin.public_id)
    return {"status": "deleted"}


# --- usage & history --------------------------------------------------------


@router.post("/{source_id}/usage-check")
async def usage_check(
    source_id: str,
    payload: UsageCheckRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return usage_service(settings).evaluate(
        source_id, payload.target_use, admin_id=admin.admin.public_id
    )


@router.get("/{source_id}/usage-summary")
async def usage_summary(source_id: str, settings: SettingsDependency) -> dict[str, Any]:
    """Read-only: evaluates every target use without an authenticated admin
    identity attached to the resulting decision rows (unlike POST
    usage-check, which records who explicitly requested the check)."""

    return usage_service(settings).effective_permissions(source_id)


@router.get("/{source_id}/history")
async def source_history(source_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return registry_service(settings).history(source_id)


@router.get("/{source_id}/verification-events")
async def verification_events(source_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return verification_service(settings).list_events(source_id)
