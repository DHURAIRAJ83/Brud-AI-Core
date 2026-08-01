"""Phase 15 controlled inference runtime, model assignment, canary, and
rollback APIs."""

from fastapi import APIRouter, Depends

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.database.repositories.inference_runtime import InferenceRuntimeRepository
from backend.database.repositories.model_release import ModelReleaseRepository
from backend.models.inference_runtime import (
    AssignmentActivateRequest,
    AssignmentApprovalCreate,
    AssignmentCreate,
    AssignmentPatch,
    CanaryExecuteRequest,
    CanaryStartRequest,
    CanaryStopRequest,
    ChatLabMessageCreate,
    ChatLabSessionCreate,
    CompatibilityAssessRequest,
    DiagnosticGenerateRequest,
    InstanceLoadRequest,
    RollbackExecuteRequest,
    RollbackPreviewRequest,
    RuntimeInstanceCreate,
    RuntimeProfileCreate,
    RuntimeProfilePatch,
    ScopeEnabledPatch,
)
from backend.services.inference_runtime_service import InferenceRuntimeService
from backend.services.model_assignment_service import ModelAssignmentService

router = APIRouter(
    prefix="/admin/inference-runtime",
    tags=["admin-inference-runtime"],
    dependencies=[Depends(require_admin)],
)


def runtime_service(settings) -> InferenceRuntimeService:
    return InferenceRuntimeService(
        InferenceRuntimeRepository(settings.resolved_database_path),
        ModelReleaseRepository(settings.resolved_database_path),
        settings,
    )


def assignment_service(settings) -> ModelAssignmentService:
    return ModelAssignmentService(
        InferenceRuntimeRepository(settings.resolved_database_path),
        ModelReleaseRepository(settings.resolved_database_path),
        runtime_service(settings),
        settings,
    )


# --- runtime profiles -----------------------------------------------------


@router.get("/profiles")
async def profiles(settings: SettingsDependency):
    return runtime_service(settings).list_profiles()


@router.post("/profiles")
async def create_profile(
    payload: RuntimeProfileCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return runtime_service(settings).create_profile(payload, admin.admin.public_id)


@router.get("/profiles/{public_id}")
async def profile(public_id: str, settings: SettingsDependency):
    return runtime_service(settings).get_profile(public_id)


@router.patch("/profiles/{public_id}")
async def patch_profile(
    public_id: str,
    payload: RuntimeProfilePatch,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return runtime_service(settings).patch_profile(public_id, payload, admin.admin.public_id)


# --- runtime instances -----------------------------------------------------


@router.get("/instances")
async def instances(settings: SettingsDependency):
    return runtime_service(settings).list_instances()


@router.post("/instances")
async def create_instance(
    payload: RuntimeInstanceCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return runtime_service(settings).create_instance(
        payload.runtime_profile_public_id, admin.admin.public_id
    )


@router.get("/instances/{public_id}")
async def instance(public_id: str, settings: SettingsDependency):
    return runtime_service(settings).get_instance(public_id)


@router.post("/instances/{public_id}/start")
async def start_instance(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return runtime_service(settings).start_instance(public_id, admin.admin.public_id)


@router.post("/instances/{public_id}/stop")
async def stop_instance(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return runtime_service(settings).stop_instance(public_id, admin.admin.public_id)


@router.post("/instances/{public_id}/load")
async def load_instance(
    public_id: str,
    payload: InstanceLoadRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return runtime_service(settings).load_instance(
        public_id, payload.release_public_id, admin.admin.public_id
    )


@router.post("/instances/{public_id}/unload")
async def unload_instance(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return runtime_service(settings).unload_instance(public_id, admin.admin.public_id)


@router.post("/instances/{public_id}/health-check")
async def health_check(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return runtime_service(settings).run_health_check(public_id, admin.admin.public_id)


# --- compatibility -----------------------------------------------------


@router.post("/releases/{release_public_id}/compatibility/assess")
async def assess_compatibility(
    release_public_id: str,
    payload: CompatibilityAssessRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return runtime_service(settings).assess_compatibility(
        release_public_id, payload.runtime_profile_public_id, admin.admin.public_id
    )


@router.get("/releases/{release_public_id}/compatibility")
async def compatibility(release_public_id: str, settings: SettingsDependency):
    return runtime_service(settings).get_compatibility(release_public_id)


# --- assignment scopes -----------------------------------------------------


@router.get("/assignment-scopes")
async def assignment_scopes(settings: SettingsDependency):
    return assignment_service(settings).list_scopes()


@router.patch("/assignment-scopes/{scope_key}")
async def patch_assignment_scope(
    scope_key: str, payload: ScopeEnabledPatch, settings: SettingsDependency, admin: CsrfDependency
):
    return assignment_service(settings).set_scope_enabled(
        scope_key, payload.enabled, admin.admin.public_id
    )


# --- assignments -----------------------------------------------------


@router.get("/assignments")
async def assignments(settings: SettingsDependency):
    return assignment_service(settings).list_assignments()


@router.post("/assignments")
async def create_assignment(
    payload: AssignmentCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return assignment_service(settings).create_assignment(payload, admin.admin.public_id)


@router.get("/assignments/{public_id}")
async def assignment(public_id: str, settings: SettingsDependency):
    return assignment_service(settings).get_assignment(public_id)


@router.patch("/assignments/{public_id}")
async def patch_assignment(
    public_id: str, payload: AssignmentPatch, settings: SettingsDependency, admin: CsrfDependency
):
    return assignment_service(settings).patch_assignment(public_id, payload, admin.admin.public_id)


@router.post("/assignments/{public_id}/validate")
async def validate_assignment(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return assignment_service(settings).validate_assignment(public_id, admin.admin.public_id)


@router.post("/assignments/{public_id}/approve")
async def approve_assignment(
    public_id: str,
    payload: AssignmentApprovalCreate,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return assignment_service(settings).approve_assignment(
        public_id, payload, admin.admin.public_id
    )


@router.post("/assignments/{public_id}/activate")
async def activate_assignment(
    public_id: str,
    payload: AssignmentActivateRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return assignment_service(settings).activate_assignment(
        public_id,
        admin.admin.public_id,
        explicit_activation_confirmed=payload.explicit_activation_confirmed,
    )


@router.post("/assignments/{public_id}/pause")
async def pause_assignment(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return assignment_service(settings).pause_assignment(public_id, admin.admin.public_id)


@router.post("/assignments/{public_id}/resume")
async def resume_assignment(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return assignment_service(settings).resume_assignment(public_id, admin.admin.public_id)


@router.get("/assignments/{public_id}/versions")
async def versions(public_id: str, settings: SettingsDependency):
    return assignment_service(settings).versions(public_id)


@router.get("/assignments/{public_id}/events")
async def events(public_id: str, settings: SettingsDependency):
    return assignment_service(settings).events(public_id)


# --- admin diagnostics -----------------------------------------------------


@router.post("/assignments/{public_id}/diagnostic-generate")
async def diagnostic_generate(
    public_id: str,
    payload: DiagnosticGenerateRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return assignment_service(settings).diagnostic_generate(
        public_id, payload, admin.admin.public_id
    )


# --- admin chat lab -----------------------------------------------------


@router.post("/assignments/{public_id}/sessions")
async def create_session(
    public_id: str,
    payload: ChatLabSessionCreate,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return assignment_service(settings).create_session(public_id, payload, admin.admin.public_id)


@router.get("/sessions/{public_id}")
async def session(public_id: str, settings: SettingsDependency):
    return assignment_service(settings).get_session(public_id)


@router.post("/sessions/{public_id}/messages")
async def post_message(
    public_id: str,
    payload: ChatLabMessageCreate,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return assignment_service(settings).post_message(
        public_id, payload.message, admin.admin.public_id
    )


@router.post("/sessions/{public_id}/close")
async def close_session(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return assignment_service(settings).close_session(public_id, admin.admin.public_id)


# --- canary -----------------------------------------------------


@router.post("/assignments/{public_id}/canary/start")
async def start_canary(
    public_id: str, payload: CanaryStartRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return assignment_service(settings).start_canary(public_id, payload, admin.admin.public_id)


@router.post("/assignments/{public_id}/canary/execute")
async def execute_canary(
    public_id: str,
    payload: CanaryExecuteRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return assignment_service(settings).execute_canary(
        public_id, payload.fixture_prompts, admin.admin.public_id
    )


@router.post("/assignments/{public_id}/canary/stop")
async def stop_canary(
    public_id: str,
    payload: CanaryStopRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return assignment_service(settings).stop_canary(
        public_id, payload.reason, admin.admin.public_id
    )


@router.get("/assignments/{public_id}/canary/results")
async def canary_results(public_id: str, settings: SettingsDependency):
    return assignment_service(settings).canary_results(public_id)


# --- rollback -----------------------------------------------------


@router.post("/assignments/{public_id}/rollback/preview")
async def rollback_preview(
    public_id: str,
    payload: RollbackPreviewRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return assignment_service(settings).rollback_preview(public_id, payload, admin.admin.public_id)


@router.post("/assignments/{public_id}/rollback/execute")
async def rollback_execute(
    public_id: str,
    payload: RollbackExecuteRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    preview_payload = RollbackPreviewRequest(
        target_version_public_id=payload.target_version_public_id, reason=payload.comment
    )
    return assignment_service(settings).rollback_execute(
        public_id, preview_payload, admin.admin.public_id
    )


# --- runtime manifest -----------------------------------------------------


@router.get("/assignments/{public_id}/manifest")
async def generate_manifest(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return assignment_service(settings).generate_manifest(public_id, admin.admin.public_id)


@router.post("/assignments/{public_id}/manifest/verify")
async def verify_manifest(public_id: str, settings: SettingsDependency):
    return assignment_service(settings).verify_manifest(public_id)
