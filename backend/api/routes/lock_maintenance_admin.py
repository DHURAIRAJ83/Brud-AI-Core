"""Phase 28 — Operations Hardening & Stale-Lock Governance Admin API Router.

Prefix: /admin/phase28
All endpoints protected by server-side RBAC dependency [Depends(require_admin)].
Zero autonomous execution, zero automatic deployment, zero automatic lock deletion.
"""

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.api.auth import require_admin
from backend.api.dependencies import SettingsDependency
from backend.services.lock_maintenance_service import LockMaintenanceService
from core_model.capabilities.lock_maintenance_service import (
    InvalidLockError,
    LockReleaseError,
)

router = APIRouter(prefix="/admin/phase28", tags=["lock-maintenance-admin"])


def get_db_connection(settings: SettingsDependency) -> sqlite3.Connection:
    """Helper to instantiate SQLite connection to resolved DB path."""
    return sqlite3.connect(settings.resolved_database_path)


class LockReleasePayload(BaseModel):
    """Payload for human admin stale lock release request."""

    reason: str = Field(..., min_length=1, description="Explicit human admin audit reason for releasing stale lock.")


@router.get("/locks", response_model=dict[str, Any], dependencies=[Depends(require_admin)])
def list_and_inspect_locks(
    stale_threshold_seconds: float = Query(3600.0, ge=1.0),
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """List and inspect all active locks across Phase 24, 25, and 26 tables.

    Inspection ONLY observes and reports. Zero lock mutation or deletion is performed.
    """
    with get_db_connection(settings) as db:
        service = LockMaintenanceService(db)
        report = service.inspect_locks(stale_threshold_seconds=stale_threshold_seconds)
        return report.to_dict()


@router.get("/locks/{lock_table}/{lock_key:path}", response_model=dict[str, Any], dependencies=[Depends(require_admin)])
def get_lock_details(
    lock_table: str,
    lock_key: str,
    stale_threshold_seconds: float = Query(3600.0, ge=1.0),
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Inspect details of a specific lock record in Phase 24, 25, or 26 lock tables."""
    with get_db_connection(settings) as db:
        service = LockMaintenanceService(db)
        detail = service.get_lock_detail(lock_table, lock_key, stale_threshold_seconds=stale_threshold_seconds)
        if not detail:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Lock '{lock_key}' in table '{lock_table}' not found.",
            )
        return detail.to_dict()


@router.post("/locks/{lock_table}/{lock_key:path}/release", response_model=dict[str, Any], dependencies=[Depends(require_admin)])
def release_stale_lock_endpoint(
    lock_table: str,
    lock_key: str,
    payload: LockReleasePayload,
    stale_threshold_seconds: float = Query(3600.0, ge=1.0),
    admin_id: str = Query("super-admin-1"),
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Explicit human-authorized release of a verified stale lock record (Admin Only)."""
    with get_db_connection(settings) as db:
        service = LockMaintenanceService(db)
        try:
            op = service.release_stale_lock(
                lock_table,
                lock_key,
                released_by=admin_id,
                reason=payload.reason,
                stale_threshold_seconds=stale_threshold_seconds,
            )
            return op.to_dict()
        except LockReleaseError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except InvalidLockError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/metrics", response_model=dict[str, Any], dependencies=[Depends(require_admin)])
def get_lock_maintenance_metrics(settings: SettingsDependency = None) -> dict[str, Any]:
    """Get summary lock maintenance governance metrics."""
    with get_db_connection(settings) as db:
        service = LockMaintenanceService(db)
        report = service.inspect_locks(stale_threshold_seconds=3600.0)
        return {
            "phase": 28,
            "name": "Operations Hardening & Stale-Lock Governance",
            "total_active_locks": report.total_locks_count,
            "stale_locks_count": report.stale_locks_count,
            "fresh_locks_count": report.fresh_locks_count,
            "governance_mode": "HUMAN_APPROVED_LOCK_RELEASE",
        }
