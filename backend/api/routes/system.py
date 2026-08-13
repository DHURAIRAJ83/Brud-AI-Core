"""Temporary read-only admin control-plane endpoints for Phase 2."""

from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Query

from backend.api.auth import require_admin
from backend.api.dependencies import SettingsDependency
from backend.database.connection import database_connection
from backend.database.migrations import migration_status
from backend.database.repositories import AuditLogRepository
from backend.models.domain import AuditEventCreate
from backend.services.pilot_metrics import pilot_metric_counts

router = APIRouter(prefix="/admin", tags=["admin-system"], dependencies=[Depends(require_admin)])


def _record_read(settings, action: str) -> None:
    if not settings.audit_enabled:
        return
    try:
        AuditLogRepository(settings.resolved_database_path).append(
            AuditEventCreate(
                event_type="admin_system_read",
                actor_type="anonymous_admin",
                action=action,
                resource_type="system",
                metadata={},
            )
        )
    except Exception:
        # Observability failures must not make temporary read endpoints unavailable.
        return


def _latest_backup(backup_dir: Path) -> dict[str, str] | None:
    candidates = sorted(
        backup_dir.glob("brud_ai_before_v*_*.db"), key=lambda item: item.stat().st_mtime
    )
    if not candidates:
        return None
    latest = candidates[-1]
    return {
        "filename": latest.name,
        "created_at": datetime.fromtimestamp(latest.stat().st_mtime, UTC).isoformat(),
    }


@router.get("/system/database")
async def database_system(settings: SettingsDependency) -> dict[str, object]:
    _record_read(settings, "read_database_status")
    with database_connection(
        settings.resolved_database_path,
        busy_timeout_ms=settings.database_busy_timeout_ms,
        wal_enabled=settings.database_wal,
    ) as connection:
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        foreign_keys = bool(connection.execute("PRAGMA foreign_keys").fetchone()[0])
        busy_timeout = connection.execute("PRAGMA busy_timeout").fetchone()[0]
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    return {
        "status": "healthy" if integrity == "ok" else "degraded",
        "schema_version": migration_status(settings.resolved_database_path)["current_version"],
        "journal_mode": journal_mode,
        "foreign_keys": foreign_keys,
        "busy_timeout_ms": busy_timeout,
        "database_size_bytes": settings.resolved_database_path.stat().st_size,
        "backup_enabled": settings.database_auto_backup,
        "latest_backup": _latest_backup(settings.resolved_backup_dir),
    }


@router.get("/system/configuration")
async def safe_configuration(settings: SettingsDependency) -> dict[str, object]:
    _record_read(settings, "read_safe_configuration")
    return {
        "environment": settings.env,
        "debug": settings.debug,
        "log_level": settings.log_level,
        "audit_enabled": settings.audit_enabled,
        "database_wal": settings.database_wal,
        "configured_origins": settings.cors_origins,
    }


@router.get("/system/schema")
async def schema_status(settings: SettingsDependency) -> dict[str, object]:
    _record_read(settings, "read_schema_status")
    status = migration_status(settings.resolved_database_path)
    with database_connection(settings.resolved_database_path) as connection:
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
                "ORDER BY name"
            )
        ]
    return {**status, "tables": tables}


@router.get("/audit/recent")
async def recent_audit(
    settings: SettingsDependency,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    _record_read(settings, "read_recent_audit")
    events = AuditLogRepository(settings.resolved_database_path).recent(limit=limit, offset=offset)
    return {
        "items": [event.model_dump(mode="json") for event in events],
        "limit": limit,
        "offset": offset,
    }


@router.get("/system/pilot-metrics")
async def pilot_metrics(settings: SettingsDependency) -> dict[str, int]:
    _record_read(settings, "read_pilot_metrics")
    return pilot_metric_counts(settings)
