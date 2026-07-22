"""Authenticated Core Model architecture APIs."""

from fastapi import APIRouter, Depends, Query

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.database.repositories.core_models import CoreModelRepository
from backend.models.core_models import (
    CoreAssignmentPatch,
    CoreConfigCreate,
    CoreConfigPatch,
    CoreFamilyCreate,
    CoreFamilyPatch,
    CoreVersionCreate,
    ForwardTestRequest,
)
from backend.services.core_model_service import CoreModelService

router = APIRouter(
    prefix="/admin/core-models",
    tags=["admin-core-models"],
    dependencies=[Depends(require_admin)],
)


def service(settings) -> CoreModelService:
    return CoreModelService(CoreModelRepository(settings.resolved_database_path), settings)


@router.get("/capabilities")
async def capabilities(settings: SettingsDependency):
    return service(settings).capabilities()


@router.get("/families")
async def families(
    settings: SettingsDependency,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
):
    return service(settings).list_families(page, page_size)


@router.post("/families")
async def create_family(
    payload: CoreFamilyCreate,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return service(settings).create_family(payload, admin.admin.public_id)


@router.get("/families/{public_id}")
async def family(public_id: str, settings: SettingsDependency):
    return service(settings).get_family(public_id)


@router.patch("/families/{public_id}")
async def patch_family(
    public_id: str,
    payload: CoreFamilyPatch,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return service(settings).patch_family(public_id, payload, admin.admin.public_id)


@router.get("/configs")
async def configs(
    settings: SettingsDependency,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
):
    return service(settings).list_configs(page, page_size)


@router.post("/configs")
async def create_config(
    payload: CoreConfigCreate,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return service(settings).create_config(payload, admin.admin.public_id)


@router.post("/configs/estimate")
async def estimate_config(payload: CoreConfigCreate, settings: SettingsDependency):
    return service(settings).estimate_config(payload)


@router.get("/versions")
async def versions(
    settings: SettingsDependency,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
):
    return service(settings).list_versions(page, page_size)


@router.post("/versions")
async def create_version(
    payload: CoreVersionCreate,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return service(settings).create_version(payload, admin.admin.public_id)


@router.get("/versions/{public_id}")
async def version(public_id: str, settings: SettingsDependency):
    return service(settings).get_version(public_id)


@router.post("/versions/{public_id}/initialize")
async def initialize(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).initialize(public_id, admin.admin.public_id)


@router.post("/versions/{public_id}/verify-architecture")
async def verify_architecture(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).verify_architecture(public_id, admin.admin.public_id)


@router.post("/versions/{public_id}/forward-test")
async def forward_test(
    public_id: str,
    payload: ForwardTestRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return service(settings).forward_test(
        public_id,
        payload.input_ids,
        payload.labels,
        admin.admin.public_id,
    )


@router.post("/versions/{public_id}/smoke-test")
async def smoke_test(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).smoke_test(public_id, admin.admin.public_id)


@router.post("/versions/{public_id}/stage")
async def stage(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).stage(public_id, admin.admin.public_id)


@router.post("/versions/{public_id}/activate")
async def activate(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).activate(public_id, admin.admin.public_id)


@router.post("/versions/{public_id}/retire")
async def retire(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).retire(public_id, admin.admin.public_id)


@router.get("/versions/{public_id}/checks")
async def checks(public_id: str, settings: SettingsDependency):
    return service(settings).checks(public_id)


@router.get("/versions/{public_id}/checkpoints")
async def checkpoints(public_id: str, settings: SettingsDependency):
    return service(settings).checkpoints(public_id)


@router.post("/checkpoints/{checkpoint_public_id}/verify")
async def verify_checkpoint(
    checkpoint_public_id: str,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return service(settings).verify_checkpoint(checkpoint_public_id, admin.admin.public_id)


@router.get("/assignments")
async def assignments(settings: SettingsDependency):
    return service(settings).assignments()


@router.patch("/assignments/{assignment_key}")
async def patch_assignment(
    assignment_key: str,
    payload: CoreAssignmentPatch,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return service(settings).patch_assignment(assignment_key, payload, admin.admin.public_id)


@router.get("/configs/{public_id}")
async def config(public_id: str, settings: SettingsDependency):
    return service(settings).get_config(public_id)


@router.patch("/configs/{public_id}")
async def patch_config(
    public_id: str,
    payload: CoreConfigPatch,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    _ = payload, admin
    return service(settings).get_config(public_id)


@router.post("/configs/{public_id}/validate")
async def validate_config(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).validate_config(public_id, admin.admin.public_id)
