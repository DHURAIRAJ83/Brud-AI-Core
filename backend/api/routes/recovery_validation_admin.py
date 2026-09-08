"""Phase 30 — Production Reliability, Recovery Validation & Operational Governance Admin API Router.

Prefix: /admin/phase30
All endpoints protected by server-side RBAC dependency [Depends(require_admin)].
Zero autonomous execution, zero background failover bots, zero automatic restore.
"""

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.api.auth import require_admin
from backend.api.dependencies import SettingsDependency
from backend.services.recovery_validation_service import RecoveryValidationService
from core_model.capabilities.recovery_validation_service import RecoveryDrillError

router = APIRouter(prefix="/admin/phase30", tags=["recovery-validation-admin"])


def get_db_connection(settings: SettingsDependency) -> sqlite3.Connection:
    """Helper to instantiate SQLite connection to resolved DB path."""
    return sqlite3.connect(settings.resolved_database_path)


@router.get("/health", response_model=dict[str, Any], dependencies=[Depends(require_admin)])
def get_subsystem_health_endpoint(settings: SettingsDependency = None) -> dict[str, Any]:
    """Get health status of Phase 30 recovery validation subsystem."""
    return {
        "phase": 30,
        "subsystem": "Recovery Validation & Operational Governance",
        "status": "HEALTHY",
        "autonomous_execution": "DISABLED",
    }


@router.get("/readiness", response_model=dict[str, Any], dependencies=[Depends(require_admin)])
def get_operational_readiness_endpoint(settings: SettingsDependency = None) -> dict[str, Any]:
    """Evaluate and return deterministic system operational readiness report."""
    with get_db_connection(settings) as db:
        service = RecoveryValidationService(db)
        report = service.evaluate_operational_readiness()
        return report.to_dict()


@router.get("/rpo", response_model=dict[str, Any], dependencies=[Depends(require_admin)])
def get_rpo_status_endpoint(settings: SettingsDependency = None) -> dict[str, Any]:
    """Get Recovery Point Objective (RPO) compliance status and backup freshness."""
    with get_db_connection(settings) as db:
        service = RecoveryValidationService(db)
        return service.get_rpo_compliance_status()


@router.get("/rto", response_model=dict[str, Any], dependencies=[Depends(require_admin)])
def get_rto_status_endpoint(settings: SettingsDependency = None) -> dict[str, Any]:
    """Get Recovery Time Objective (RTO) compliance status based on recovery drills."""
    with get_db_connection(settings) as db:
        service = RecoveryValidationService(db)
        return service.get_rto_compliance_status()


@router.get("/drills", response_model=dict[str, Any], dependencies=[Depends(require_admin)])
def list_recovery_drills_endpoint(
    limit: int = Query(50, ge=1, le=200),
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """List recovery drill execution records ordered by started_at descending."""
    with get_db_connection(settings) as db:
        service = RecoveryValidationService(db)
        drills = service.repository.list_recovery_drills(limit=limit)
        return {
            "total_count": len(drills),
            "drills": [d.to_dict() for d in drills],
        }


@router.get("/drills/{drill_id}", response_model=dict[str, Any], dependencies=[Depends(require_admin)])
def get_recovery_drill_details_endpoint(
    drill_id: str,
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Get specific recovery drill record details."""
    with get_db_connection(settings) as db:
        service = RecoveryValidationService(db)
        drill = service.repository.get_recovery_drill_by_id(drill_id)
        if not drill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Recovery drill '{drill_id}' not found.",
            )
        return drill.to_dict()


@router.post("/drills/{backup_id}", response_model=dict[str, Any], dependencies=[Depends(require_admin)])
def execute_recovery_drill_endpoint(
    backup_id: str,
    admin_id: str = Query("admin-1"),
    drill_type: str = Query("SCHEDULED_DRILL"),
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Execute a safe, isolated database recovery drill from snapshot backup.

    Drill executes strictly against temporary isolated SQLite environment.
    Production database is NEVER mutated or used as a write target.
    """
    with get_db_connection(settings) as db:
        service = RecoveryValidationService(db)
        try:
            record = service.execute_recovery_drill(
                backup_id,
                executed_by=admin_id,
                drill_type=drill_type,
            )
            return record.to_dict()
        except RecoveryDrillError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/metrics", response_model=dict[str, Any], dependencies=[Depends(require_admin)])
def get_recovery_validation_metrics(settings: SettingsDependency = None) -> dict[str, Any]:
    """Get operational recovery validation metrics summary."""
    with get_db_connection(settings) as db:
        service = RecoveryValidationService(db)
        drills = service.repository.list_recovery_drills(limit=100)
        passed_drills = sum(1 for d in drills if d.result == "PASS")
        report = service.evaluate_operational_readiness()
        return {
            "phase": 30,
            "name": "Production Reliability, Recovery Validation & Operational Governance",
            "readiness_status": report.readiness_status,
            "total_drills_count": len(drills),
            "passed_drills_count": passed_drills,
            "rpo_status": report.rpo_status,
            "rto_status": report.rto_status,
            "governance_mode": "ISOLATED_TEMPORARY_DRILL_NO_AUTONOMOUS_RESTORE",
        }
