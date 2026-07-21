"""Service health and release metadata endpoints."""

from fastapi import APIRouter

from backend import __version__
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


@router.get("/version")
async def version() -> dict[str, str | int]:
    return {"project": "Brud AI", "version": __version__, "phase": 1}
