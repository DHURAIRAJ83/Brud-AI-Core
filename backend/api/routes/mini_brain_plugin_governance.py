"""MB-24: Brud Mini Brain Plugin & Tool Runtime Governance Center --
admin-only APIs. Independent prefix
(`/admin/mini-brain/plugin-governance`). No route here executes a
plugin binary, runs a real sandbox, installs a plugin from the
internet, auto-enables a plugin, auto-grants a permission, modifies
any MB-16 through MB-23 table, starts a training job, or approves a
release -- every mutating route only ever writes to MB-24's own
tables. `enable_plugin` and `grant_permission` are the only routes
that can move a plugin/permission out of its safe default state, and
both require a real, CSRF-protected admin call.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.models.mini_brain_plugin_governance import (
    EvaluatePermissionRequest,
    GrantPermissionRequest,
    IssueTokenRequest,
    RegisterPluginRequest,
    RequestConsentRequest,
    RevokePermissionRequest,
    RuntimeEventRequest,
)
from backend.services.mini_brain_plugin_governance_service import MiniBrainPluginGovernanceService

router = APIRouter(
    prefix="/admin/mini-brain/plugin-governance",
    tags=["admin-mini-brain-plugin-governance"],
    dependencies=[Depends(require_admin)],
)


def service(settings) -> MiniBrainPluginGovernanceService:
    return MiniBrainPluginGovernanceService(settings)


@router.get("/diagnostics")
async def diagnostics(settings: SettingsDependency):
    return service(settings).diagnostics()


# -- plugins ------------------------------------------------------------------


@router.post("/plugins")
async def register_plugin(payload: RegisterPluginRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).register_plugin(
        manifest=payload.manifest.model_dump(), admin_id=admin.admin.public_id, source=payload.source,
    )


@router.get("/plugins")
async def list_plugins(
    settings: SettingsDependency,
    limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None),
):
    return service(settings).list_plugins(limit=limit, offset=offset, status=status)


@router.get("/plugins/{plugin_id}")
async def get_plugin(plugin_id: str, settings: SettingsDependency):
    return service(settings).plugin(plugin_id)


@router.get("/plugins/{plugin_id}/events")
async def list_events(
    plugin_id: str, settings: SettingsDependency,
    limit: int = Query(default=100, ge=1, le=100), offset: int = Query(default=0, ge=0),
):
    return service(settings).list_events(plugin_id, limit=limit, offset=offset)


@router.get("/plugins/{plugin_id}/consents")
async def list_consents(
    plugin_id: str, settings: SettingsDependency,
    limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0),
):
    return service(settings).list_consents(plugin_id, limit=limit, offset=offset)


@router.get("/plugins/{plugin_id}/permissions")
async def list_permissions(
    plugin_id: str, settings: SettingsDependency,
    limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0),
):
    return service(settings).list_permissions(plugin_id, limit=limit, offset=offset)


@router.get("/memory")
async def list_memory(
    settings: SettingsDependency,
    limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0),
):
    return service(settings).list_memory(limit=limit, offset=offset)


# -- workflow stages --------------------------------------------------------------


@router.post("/plugins/{plugin_id}/validate")
async def validate_manifest(plugin_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_validate_manifest_stage(plugin_id, admin_id=admin.admin.public_id)


@router.post("/plugins/{plugin_id}/classify")
async def classify_capabilities(plugin_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_classify_capabilities_stage(plugin_id, admin_id=admin.admin.public_id)


@router.post("/plugins/{plugin_id}/risk-score")
async def compute_risk_score(plugin_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_compute_risk_stage(plugin_id, admin_id=admin.admin.public_id)


@router.post("/plugins/{plugin_id}/sandbox-profile")
async def build_sandbox_profile(plugin_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_build_sandbox_stage(plugin_id, admin_id=admin.admin.public_id)


@router.post("/plugins/{plugin_id}/filesystem-policy")
async def build_filesystem_policy(plugin_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_build_filesystem_policy_stage(plugin_id, admin_id=admin.admin.public_id)


@router.post("/plugins/{plugin_id}/network-policy")
async def build_network_policy(plugin_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_build_network_policy_stage(plugin_id, admin_id=admin.admin.public_id)


@router.post("/plugins/{plugin_id}/enable")
async def enable_plugin(plugin_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).enable_plugin(plugin_id, admin_id=admin.admin.public_id)


@router.post("/plugins/{plugin_id}/evaluate-permission")
async def evaluate_permission(
    plugin_id: str, payload: EvaluatePermissionRequest, settings: SettingsDependency, admin: CsrfDependency,
):
    return service(settings).run_evaluate_permission_stage(
        plugin_id, scope_key=payload.scope_key, is_public_chat=payload.is_public_chat,
        user_id_hash=payload.user_id_hash, admin_id=admin.admin.public_id,
    )


@router.post("/plugins/{plugin_id}/request-consent")
async def request_consent(
    plugin_id: str, payload: RequestConsentRequest, settings: SettingsDependency, admin: CsrfDependency,
):
    return service(settings).request_consent(
        plugin_id, scope_key=payload.scope_key, raw_user_identity=payload.raw_user_identity,
        consent_given=payload.consent_given, ttl_seconds=payload.ttl_seconds, admin_id=admin.admin.public_id,
    )


@router.post("/plugins/{plugin_id}/grant-permission")
async def grant_permission(
    plugin_id: str, payload: GrantPermissionRequest, settings: SettingsDependency, admin: CsrfDependency,
):
    return service(settings).grant_permission(
        plugin_id, scope_key=payload.scope_key, user_id_hash=payload.user_id_hash, admin_id=admin.admin.public_id,
    )


@router.post("/plugins/{plugin_id}/revoke-permission")
async def revoke_permission(
    plugin_id: str, payload: RevokePermissionRequest, settings: SettingsDependency, admin: CsrfDependency,
):
    return service(settings).revoke_permission(plugin_id, scope_key=payload.scope_key, admin_id=admin.admin.public_id)


@router.post("/plugins/{plugin_id}/issue-token")
async def issue_token(
    plugin_id: str, payload: IssueTokenRequest, settings: SettingsDependency, admin: CsrfDependency,
):
    return service(settings).issue_execution_token(
        plugin_id, scope_keys=payload.scope_keys, raw_user_identity=payload.raw_user_identity,
        raw_session_identity=payload.raw_session_identity, admin_id=admin.admin.public_id,
        ttl_seconds=payload.ttl_seconds,
    )


@router.post("/plugins/{plugin_id}/runtime-event")
async def runtime_event(
    plugin_id: str, payload: RuntimeEventRequest, settings: SettingsDependency, admin: CsrfDependency,
):
    return service(settings).record_runtime_event(
        plugin_id, event_type=payload.event_type, message=payload.message, metadata=payload.metadata,
        admin_id=admin.admin.public_id,
    )


@router.post("/plugins/{plugin_id}/report")
async def generate_report(plugin_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).generate_report(plugin_id, admin_id=admin.admin.public_id)


@router.post("/plugins/{plugin_id}/disable")
async def disable_plugin(plugin_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).disable_plugin(plugin_id, admin_id=admin.admin.public_id)


@router.post("/plugins/{plugin_id}/archive")
async def archive_plugin(plugin_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).archive_plugin(plugin_id, admin_id=admin.admin.public_id)
