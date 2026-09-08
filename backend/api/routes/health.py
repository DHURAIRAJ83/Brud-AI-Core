"""Service health and release metadata endpoints."""

from fastapi import APIRouter

from backend import PROJECT_PHASE, __version__
from backend.api.dependencies import SettingsDependency
from backend.database.connection import database_is_connected

router = APIRouter(tags=["system"])


@router.get("/health")
async def health(settings: SettingsDependency) -> dict[str, str]:
    connected = database_is_connected(settings.resolved_database_path)
    return {
        "status": "healthy" if connected else "degraded",
        "service": "brud-ai-backend",
        "version": __version__,
        "database": "connected" if connected else "unavailable",
        "core_model": "not_configured",
    }


@router.get("/ready")
async def ready(settings: SettingsDependency) -> dict[str, str]:
    from fastapi import HTTPException
    connected = database_is_connected(settings.resolved_database_path)
    if not connected:
        raise HTTPException(status_code=503, detail={"status": "not_ready", "database": "unavailable"})
    return {
        "status": "ready",
        "service": "brud-ai-backend",
        "database": "connected",
    }


@router.get("/status")
async def operational_status(settings: SettingsDependency) -> dict[str, str | int | bool]:
    connected = database_is_connected(settings.resolved_database_path)
    return {
        "status": "operational" if connected else "degraded",
        "service": "brud-ai-backend",
        "version": __version__,
        "phase": PROJECT_PHASE,
        "environment": settings.env,
        "database": "connected" if connected else "unavailable",
        "debug": settings.debug,
        "audit_enabled": settings.audit_enabled,
    }


@router.get("/version")
async def version() -> dict[str, str | int]:
    return {"project": "Brud AI", "version": __version__, "phase": PROJECT_PHASE}
