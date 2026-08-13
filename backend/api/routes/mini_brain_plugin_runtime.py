"""MB-25: Brud Mini Brain Secure Plugin Execution Runtime -- admin-only
APIs. Independent prefix (`/admin/mini-brain/plugin-runtime`). No
route here executes a plugin that MB-24 has not approved and enabled,
issues its own execution token (only MB-24's own governance routes may
do that), or bypasses MB-24's own permission/consent decisions --
`run_execution()` re-derives them fresh from MB-24's own repository
state on every single call.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.models.mini_brain_plugin_runtime import ExecuteRequest, RuntimeEventRequest
from backend.services.mini_brain_plugin_runtime_service import MiniBrainPluginRuntimeService

router = APIRouter(
    prefix="/admin/mini-brain/plugin-runtime",
    tags=["admin-mini-brain-plugin-runtime"],
    dependencies=[Depends(require_admin)],
)


def service(settings) -> MiniBrainPluginRuntimeService:
    return MiniBrainPluginRuntimeService(settings)


@router.get("/diagnostics")
async def diagnostics(settings: SettingsDependency):
    return service(settings).diagnostics()


@router.post("/execute")
async def execute(payload: ExecuteRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).execute_manual(
        plugin_public_id=payload.plugin_public_id, scope_key=payload.scope_key, arguments=payload.arguments,
        requester_admin_public_id=admin.admin.public_id, execution_token=payload.execution_token,
        timeout_seconds=payload.timeout_seconds,
    )


@router.get("/executions")
async def list_executions(
    settings: SettingsDependency,
    limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None), plugin_public_id: str | None = Query(default=None),
):
    return service(settings).list_executions(limit=limit, offset=offset, status=status, plugin_public_id=plugin_public_id)


@router.get("/executions/{execution_id}")
async def execution_status(execution_id: str, settings: SettingsDependency):
    return service(settings).execution(execution_id)


@router.get("/executions/{execution_id}/logs")
async def execution_logs(
    execution_id: str, settings: SettingsDependency,
    limit: int = Query(default=100, ge=1, le=100), offset: int = Query(default=0, ge=0),
):
    svc = service(settings)
    return {"events": svc.list_events(execution_id, limit=limit, offset=offset)["items"], "io": svc.list_io(execution_id, limit=limit, offset=offset)["items"]}


@router.post("/executions/{execution_id}/report")
async def execution_report(execution_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).generate_execution_report(execution_id)


@router.post("/executions/{execution_id}/cancel")
async def cancel_execution(execution_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).cancel_execution(execution_id, admin_id=admin.admin.public_id)


@router.post("/executions/{execution_id}/archive")
async def archive_execution(execution_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).archive_execution(execution_id, admin_id=admin.admin.public_id)


@router.post("/executions/{execution_id}/runtime-event")
async def runtime_event(execution_id: str, payload: RuntimeEventRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).record_external_event(
        execution_id, event_type=payload.event_type, message=payload.message, metadata=payload.metadata,
        admin_id=admin.admin.public_id,
    )


@router.get("/memory")
async def list_memory(
    settings: SettingsDependency,
    limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0),
):
    return service(settings).list_memory(limit=limit, offset=offset)


@router.get("/statistics")
async def statistics(settings: SettingsDependency):
    return service(settings).statistics()
