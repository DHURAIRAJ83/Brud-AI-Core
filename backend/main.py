"""FastAPI application entry point."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend import __version__
from backend.api.router import api_router
from backend.core.config import Settings, get_settings
from backend.core.exceptions import register_exception_handlers
from backend.core.logging import configure_logging
from backend.database.migrations import initialize_database
from backend.database.repositories import AuditLogRepository
from backend.models.domain import AuditEventCreate

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the API application without expensive import-time initialization."""

    active_settings = settings or get_settings()
    configure_logging(active_settings.log_level)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        logger.info("application_startup", extra={"environment": active_settings.env})
        initialize_database(
            active_settings.resolved_database_path,
            backup_dir=active_settings.resolved_backup_dir,
            auto_backup=active_settings.database_auto_backup,
            busy_timeout_ms=active_settings.database_busy_timeout_ms,
            wal_enabled=active_settings.database_wal,
        )
        if active_settings.audit_enabled:
            try:
                AuditLogRepository(active_settings.resolved_database_path).append(
                    AuditEventCreate(
                        event_type="application_startup",
                        actor_type="system",
                        action="application_startup",
                        resource_type="application",
                        metadata={},
                    )
                )
            except Exception:
                logger.exception("startup_audit_write_failed")
        yield
        logger.info("application_shutdown")

    application = FastAPI(
        title="Brud AI API",
        version=__version__,
        debug=active_settings.debug,
        lifespan=lifespan,
    )
    application.state.settings = active_settings

    async def provide_active_settings() -> Settings:
        return active_settings

    application.dependency_overrides[get_settings] = provide_active_settings
    application.add_middleware(
        CORSMiddleware,
        allow_origins=active_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["Content-Type", "Accept", active_settings.csrf_header_name],
    )
    application.include_router(api_router)
    register_exception_handlers(application)
    return application


app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run("backend.main:app", host=settings.host, port=settings.port, reload=settings.debug)
