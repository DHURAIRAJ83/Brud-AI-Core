"""MB-01: Brud Mini Brain -- authenticated admin-only APIs.

A completely independent router from `admin_assistant.py`: separate
prefix, separate service, separate tables. Every route requires an
authenticated admin (`require_admin`, router-level dependency,
identical to every other admin router in this codebase); mutating
routes additionally require CSRF (`CsrfDependency`), also identical
to every other admin router. There is no public-chat route here and
none should ever be added -- MB-01's own rule is that Mini Brain must
never answer Public Chat.
"""

from fastapi import APIRouter, Depends, Query

from backend.api.auth import AdminDependency, CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.database.repositories.mini_brain import MiniBrainRepository
from backend.models.mini_brain import MiniBrainSettingsPatch
from backend.services.mini_brain_service import MiniBrainService

router = APIRouter(
    prefix="/admin/mini-brain",
    tags=["admin-mini-brain"],
    dependencies=[Depends(require_admin)],
)


def service(settings) -> MiniBrainService:
    return MiniBrainService(MiniBrainRepository(settings.resolved_database_path), settings)


@router.get("/status")
async def status(settings: SettingsDependency):
    return service(settings).get_status()


@router.get("/settings")
async def get_settings(settings: SettingsDependency):
    return service(settings).get_settings()


@router.patch("/settings")
async def update_settings(
    payload: MiniBrainSettingsPatch, settings: SettingsDependency, admin: CsrfDependency,
):
    return service(settings).update_settings(payload.model_dump(), admin.admin.public_id)


@router.post("/enable")
async def enable(settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).enable(admin.admin.public_id)


@router.post("/disable")
async def disable(settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).disable(admin.admin.public_id)


@router.get("/health")
async def health(settings: SettingsDependency):
    return service(settings).health()


@router.get("/diagnostics")
async def diagnostics(settings: SettingsDependency):
    return service(settings).diagnostics()


@router.get("/version")
async def version(settings: SettingsDependency):
    return service(settings).version()


@router.get("/logs")
async def logs(
    settings: SettingsDependency,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return service(settings).list_logs(limit=limit, offset=offset)


# -- placeholder interfaces (MB-01: framework only, no model) -----------


@router.post("/inference")
async def placeholder_inference(settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).placeholder_inference(admin.admin.public_id)


@router.get("/knowledge")
async def placeholder_knowledge(settings: SettingsDependency, admin: AdminDependency):
    return service(settings).placeholder_knowledge(admin.admin.public_id)


@router.get("/memory")
async def placeholder_memory(settings: SettingsDependency, admin: AdminDependency):
    return service(settings).placeholder_memory(admin.admin.public_id)


@router.post("/suggestions")
async def placeholder_suggestions(settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).placeholder_suggestion(admin.admin.public_id)


@router.get("/context")
async def system_context(
    settings: SettingsDependency,
    admin: AdminDependency,
    force_refresh: bool = Query(default=False),
):
    """Real, unified Dashboard Context endpoint for Mini Brain Admin Assistant.
    Aggregates real-time, non-secret state across System, Providers, Models, Datasets,
    Training, Evaluation, RAG, Memory, and Governance. Uses bounded context cache."""
    from backend.services.mini_brain_dashboard_context_service import (
        MiniBrainDashboardContextService,
    )

    return MiniBrainDashboardContextService(settings).get_system_context(
        admin.admin.public_id, force_refresh=force_refresh,
    )


@router.get("/context/metrics")
async def system_context_metrics(settings: SettingsDependency, admin: AdminDependency):
    """Observability endpoint for Context Cache performance metrics."""
    from backend.services.mini_brain_dashboard_context_service import (
        MiniBrainDashboardContextService,
    )

    return MiniBrainDashboardContextService.get_cache_metrics()

