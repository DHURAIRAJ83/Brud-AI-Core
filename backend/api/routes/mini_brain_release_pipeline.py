"""MB-07: Brud Mini Brain Release Pipeline & Model Deployment Manager --
authenticated admin-only APIs. Independent prefix
(`/admin/mini-brain/release-pipeline`), separate from every system this
phase composes (Core Models, the Training Engine's own
`/admin/pretraining` routes, Model Release governance, MB-04 Runtime).
No route here trains a model, edits a dataset, or modifies the source
checkpoint -- every mutating route is a thin pass-through to
`MiniBrainReleasePipelineService`, which itself only ever calls other
systems' already-existing public methods plus writes genuinely new
GGUF files under an approved artifact root.

Each of the 12 workflow stages gets its own independently-callable
route (more granular than the task spec's shorthand 13-endpoint list)
so every stage is independently testable, matching the spec's own
explicit testing requirement.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.models.mini_brain_release_pipeline import (
    ActivateRequest,
    AdminReviewRequest,
    CreateReleaseVersionRequest,
    EvaluateRollbackRequest,
    ExecuteRollbackRequest,
    ReleaseSessionCreateRequest,
)
from backend.services.mini_brain_release_pipeline_service import MiniBrainReleasePipelineService
from core_model.mini_brain.release_pipeline.quantization_manager import (
    available_levels as _available_levels,
)

router = APIRouter(
    prefix="/admin/mini-brain/release-pipeline",
    tags=["admin-mini-brain-release-pipeline"],
    dependencies=[Depends(require_admin)],
)


def service(settings) -> MiniBrainReleasePipelineService:
    return MiniBrainReleasePipelineService(settings)


@router.get("/diagnostics")
async def diagnostics():
    return {
        "quantization_levels_supported": _available_levels(),
        "ai_model_used": False,
        "writes_performed": True,
        "pipeline_stages": [
            "checkpoint_validation", "conversion", "quantization", "integrity_validation",
            "compatibility_validation", "performance_validation", "version_registration",
            "awaiting_admin_review", "production_activation",
        ],
    }


@router.post("/sessions")
async def create_session(
    payload: ReleaseSessionCreateRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).create_session(
        core_model_version_public_id=payload.core_model_version_public_id,
        pretraining_checkpoint_public_id=payload.pretraining_checkpoint_public_id,
        model_release_family_public_id=payload.model_release_family_public_id,
        target_quantizations=payload.target_quantizations,
        dataset_version_public_id=payload.dataset_version_public_id,
        model_evaluation_run_public_id=payload.model_evaluation_run_public_id,
        admin_id=admin.admin.public_id,
    )


@router.get("/sessions")
async def list_sessions(
    settings: SettingsDependency,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    return service(settings).list_sessions(limit=limit, offset=offset)


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, settings: SettingsDependency):
    return service(settings).session(session_id)


@router.get("/sessions/{session_id}/events")
async def list_events(
    session_id: str,
    settings: SettingsDependency,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    return service(settings).events(session_id, limit=limit, offset=offset)


@router.post("/sessions/{session_id}/validate")
async def validate_checkpoint(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).validate_checkpoint(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/convert")
async def convert_model(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).convert_model(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/quantize")
async def quantize_and_export(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).quantize_and_export(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/verify")
async def verify(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    svc = service(settings)
    result = svc.validate_integrity(session_id, admin_id=admin.admin.public_id)
    if result["stage"] == "compatibility_validation":
        result = svc.validate_compatibility(session_id, admin_id=admin.admin.public_id)
    return result


@router.post("/sessions/{session_id}/performance")
async def performance(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).measure_performance(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/version")
async def create_release_version(
    session_id: str, payload: CreateReleaseVersionRequest, settings: SettingsDependency, admin: CsrfDependency
):
    # Prepares the candidate (manifest generation etc.) only -- does not
    # create the release. GOV-26/GOV-33: real, distinct, non-creator admins
    # must separately submit approvals (POST /admin/model-releases/candidates/
    # {id}/approvals, unchanged) before /finalize-version below can succeed.
    svc = service(settings)
    svc.create_release_version(
        session_id, version=payload.version, prerelease_label=payload.prerelease_label,
        admin_id=admin.admin.public_id,
    )
    return svc.generate_report(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/finalize-version")
async def finalize_release_version(
    session_id: str, payload: CreateReleaseVersionRequest, settings: SettingsDependency, admin: CsrfDependency
):
    svc = service(settings)
    svc.finalize_release_version(
        session_id, version=payload.version, prerelease_label=payload.prerelease_label,
        admin_id=admin.admin.public_id,
    )
    return svc.generate_report(session_id, admin_id=admin.admin.public_id)


@router.get("/sessions/{session_id}/register")
async def registry_entry(session_id: str, settings: SettingsDependency):
    return service(settings).registry_entry(session_id)


@router.post("/sessions/{session_id}/admin-review")
async def admin_review(
    session_id: str, payload: AdminReviewRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).admin_review(
        session_id, decision=payload.decision, admin_id=admin.admin.public_id
    )


@router.post("/sessions/{session_id}/activate")
async def activate(
    session_id: str, payload: ActivateRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).activate(
        session_id, quantization_level=payload.quantization_level, admin_id=admin.admin.public_id
    )


@router.post("/sessions/{session_id}/rollback/evaluate")
async def evaluate_rollback(
    session_id: str, payload: EvaluateRollbackRequest, settings: SettingsDependency, admin: CsrfDependency
):
    del admin
    return service(settings).evaluate_rollback(session_id, target_version=payload.target_version)


@router.post("/sessions/{session_id}/rollback")
async def execute_rollback(
    session_id: str, payload: ExecuteRollbackRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).execute_rollback(
        session_id, target_release_public_id=payload.target_release_public_id,
        reason=payload.reason, admin_id=admin.admin.public_id,
    )


@router.get("/sessions/{session_id}/report")
async def report(session_id: str, settings: SettingsDependency):
    return service(settings).session(session_id)["release_report"]
