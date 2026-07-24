"""Phase 14 model registry, release-candidate, and rollback APIs."""

from fastapi import APIRouter, Depends

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.database.repositories.model_release import ModelReleaseRepository
from backend.models.model_release import (
    ApprovalCreate,
    BundleCreate,
    ModelCardOverrides,
    ModelReleaseCandidateCreate,
    ModelReleaseCandidatePatch,
    ModelReleaseComparisonCreate,
    ModelReleaseCreate,
    ModelReleaseFamilyCreate,
    ModelReleaseFamilyPatch,
    RollbackApprovalCreate,
    RollbackPlanCreate,
)
from backend.services.model_release_service import ModelReleaseService

router = APIRouter(
    prefix="/admin/model-releases",
    tags=["admin-model-releases"],
    dependencies=[Depends(require_admin)],
)


def service(settings) -> ModelReleaseService:
    return ModelReleaseService(
        ModelReleaseRepository(settings.resolved_database_path), settings
    )


# --- families -----------------------------------------------------


@router.get("/families")
async def families(settings: SettingsDependency):
    return service(settings).list_families()


@router.post("/families")
async def create_family(
    payload: ModelReleaseFamilyCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).create_family(payload, admin.admin.public_id)


@router.get("/families/{public_id}")
async def family(public_id: str, settings: SettingsDependency):
    return service(settings).get_family(public_id)


@router.patch("/families/{public_id}")
async def patch_family(
    public_id: str,
    payload: ModelReleaseFamilyPatch,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return service(settings).patch_family(public_id, payload, admin.admin.public_id)


# --- candidates -----------------------------------------------------


@router.get("/candidates")
async def candidates(settings: SettingsDependency):
    return service(settings).list_candidates()


@router.post("/candidates")
async def create_candidate(
    payload: ModelReleaseCandidateCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).create_candidate(payload, admin.admin.public_id)


@router.get("/candidates/{public_id}")
async def candidate(public_id: str, settings: SettingsDependency):
    return service(settings).get_candidate(public_id)


@router.patch("/candidates/{public_id}")
async def patch_candidate(
    public_id: str,
    payload: ModelReleaseCandidatePatch,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return service(settings).patch_candidate(public_id, payload, admin.admin.public_id)


@router.post("/candidates/{public_id}/collect-artifacts")
async def collect_artifacts(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).collect_artifacts(public_id, admin.admin.public_id)


@router.post("/candidates/{public_id}/verify-artifacts")
async def verify_artifacts(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).verify_artifacts(public_id, admin.admin.public_id)


# --- eligibility -----------------------------------------------------


@router.post("/candidates/{public_id}/eligibility/assess")
async def assess_eligibility(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).assess_eligibility(public_id, admin.admin.public_id)


@router.get("/candidates/{public_id}/eligibility")
async def eligibility(public_id: str, settings: SettingsDependency):
    return service(settings).get_eligibility(public_id)


@router.get("/candidates/{public_id}/issues")
async def issues(public_id: str, settings: SettingsDependency):
    return service(settings).issues_for_candidate(public_id)


# --- model cards -----------------------------------------------------


@router.post("/candidates/{public_id}/model-card")
async def create_model_card(
    public_id: str,
    settings: SettingsDependency,
    admin: CsrfDependency,
    payload: ModelCardOverrides | None = None,
):
    return service(settings).generate_model_card(
        public_id, payload or ModelCardOverrides(), admin.admin.public_id
    )


@router.get("/candidates/{public_id}/model-card")
async def model_card(public_id: str, settings: SettingsDependency):
    return service(settings).get_model_card(public_id)


@router.post("/candidates/{public_id}/model-card/validate")
async def validate_model_card(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).validate_model_card(public_id, admin.admin.public_id)


# --- manifests -----------------------------------------------------


@router.post("/candidates/{public_id}/manifest")
async def create_manifest(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).generate_manifest(public_id, admin.admin.public_id)


@router.get("/candidates/{public_id}/manifest")
async def manifest(public_id: str, settings: SettingsDependency):
    return service(settings).get_manifest(public_id)


@router.post("/candidates/{public_id}/manifest/verify")
async def verify_manifest(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).verify_manifest(public_id)


# --- approvals -----------------------------------------------------


@router.post("/candidates/{public_id}/approvals")
async def create_approval(
    public_id: str, payload: ApprovalCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).submit_approval(public_id, payload, admin.admin.public_id)


@router.get("/candidates/{public_id}/approvals")
async def approvals(public_id: str, settings: SettingsDependency):
    return service(settings).approvals_for_candidate(public_id)


# --- releases -----------------------------------------------------


@router.get("/releases")
async def releases(settings: SettingsDependency):
    return service(settings).list_releases()


@router.post("/releases")
async def create_release(
    payload: ModelReleaseCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).create_release(payload, admin.admin.public_id)


@router.get("/releases/{public_id}")
async def release(public_id: str, settings: SettingsDependency):
    return service(settings).get_release(public_id)


@router.post("/releases/{public_id}/deprecate")
async def deprecate_release(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).deprecate_release(public_id, admin.admin.public_id)


@router.post("/releases/{public_id}/retire")
async def retire_release(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).retire_release(public_id, admin.admin.public_id)


# --- comparisons -----------------------------------------------------


@router.post("/releases/compare")
async def compare_releases(
    payload: ModelReleaseComparisonCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).compare_releases(payload, admin.admin.public_id)


@router.get("/comparisons/{public_id}")
async def comparison(public_id: str, settings: SettingsDependency):
    return service(settings).get_comparison(public_id)


# --- bundles -----------------------------------------------------


@router.post("/releases/{public_id}/bundle")
async def create_bundle(
    public_id: str,
    settings: SettingsDependency,
    admin: CsrfDependency,
    payload: BundleCreate | None = None,
):
    body = payload or BundleCreate()
    return service(settings).build_bundle(public_id, body.bundle_format, admin.admin.public_id)


@router.get("/releases/{public_id}/bundles")
async def bundles(public_id: str, settings: SettingsDependency):
    return service(settings).bundles_for_release(public_id)


@router.post("/bundles/{bundle_public_id}/verify")
async def verify_bundle(bundle_public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).verify_bundle(bundle_public_id)


# --- rollback -----------------------------------------------------


@router.post("/releases/{public_id}/rollback-plans")
async def create_rollback_plan(
    public_id: str,
    payload: RollbackPlanCreate,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return service(settings).create_rollback_plan(public_id, payload, admin.admin.public_id)


@router.get("/rollback-plans/{public_id}")
async def rollback_plan(public_id: str, settings: SettingsDependency):
    return service(settings).get_rollback_plan(public_id)


@router.post("/rollback-plans/{public_id}/validate")
async def validate_rollback_plan(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).validate_rollback_plan(public_id, admin.admin.public_id)


@router.post("/rollback-plans/{public_id}/approve")
async def approve_rollback_plan(
    public_id: str,
    settings: SettingsDependency,
    admin: CsrfDependency,
    payload: RollbackApprovalCreate | None = None,
):
    return service(settings).approve_rollback_plan(
        public_id, payload or RollbackApprovalCreate(), admin.admin.public_id
    )


@router.post("/rollback-plans/{public_id}/execute")
async def execute_rollback_plan(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).execute_rollback_plan(public_id, admin.admin.public_id)
