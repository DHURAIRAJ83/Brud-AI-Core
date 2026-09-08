"""FastAPI application entry point."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend import __version__
from backend.api.dependencies import get_pool
from backend.api.router import api_router
from backend.core.config import Settings, get_settings
from backend.core.exceptions import register_exception_handlers
from backend.core.logging import configure_logging
from backend.core.rate_limit_middleware import GlobalRateLimitMiddleware
from backend.core.security_headers_middleware import SecurityHeadersMiddleware
from backend.database.connection_pool import ConnectionPool
from backend.database.migrations import initialize_database
from backend.database.repositories import AuditLogRepository
from backend.models.domain import AuditEventCreate

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the API application without expensive import-time initialization."""

    active_settings = settings or get_settings()
    configure_logging(active_settings.log_level)

    # Phase 7C-33: one shared ConnectionPool per app instance, constructed
    # during lifespan startup (not eagerly here, so a startup failure never
    # leaves a partially-used pool behind) and closed during shutdown. This
    # dict-cell (not a module-level variable) is scoped to this one
    # `create_app()` call/closure, so two independently-created app
    # instances can never see each other's pool. Deliberately NOT wired
    # into the production request path yet -- see `provide_active_pool`
    # and the two routes in `base_training.py` opted into it this phase;
    # every other repository construction site still resolves `get_pool()`
    # to `None` and keeps today's exact unpooled behavior.
    pool_cell: dict[str, ConnectionPool | None] = {"pool": None}

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
        pool = ConnectionPool(
            active_settings.resolved_database_path,
            busy_timeout_ms=active_settings.database_busy_timeout_ms,
            wal_enabled=active_settings.database_wal,
        )
        pool_cell["pool"] = pool
        application.state.pool = pool
        yield
        pool.close()
        pool_cell["pool"] = None
        application.state.pool = None
        logger.info("application_shutdown")

    application = FastAPI(
        title="Brud AI API",
        version=__version__,
        debug=active_settings.debug,
        lifespan=lifespan,
    )
    application.state.settings = active_settings
    application.state.pool = None

    async def provide_active_settings() -> Settings:
        return active_settings

    async def provide_active_pool() -> ConnectionPool | None:
        return pool_cell["pool"]

    application.dependency_overrides[get_settings] = provide_active_settings
    application.dependency_overrides[get_pool] = provide_active_pool
    application.add_middleware(GlobalRateLimitMiddleware, settings=active_settings)
    application.add_middleware(SecurityHeadersMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=active_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["Content-Type", "Accept", "X-Trace-Id", active_settings.csrf_header_name],
        expose_headers=["X-Trace-Id"],
    )
    application.include_router(api_router)

    @application.get("/health", include_in_schema=False)
    async def root_health() -> dict[str, str]:
        from backend.api.routes.health import health as health_handler
        return await health_handler(active_settings)

    @application.get("/ready", include_in_schema=False)
    async def root_ready() -> dict[str, str]:
        from backend.api.routes.health import ready as ready_handler
        return await ready_handler(active_settings)

    @application.get("/status", include_in_schema=False)
    async def root_status() -> dict[str, str | int | bool]:
        from backend.api.routes.health import operational_status as status_handler
        return await status_handler(active_settings)

    register_exception_handlers(application)
    return application


app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run("backend.main:app", host=settings.host, port=settings.port, reload=settings.debug)
