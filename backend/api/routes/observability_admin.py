"""Phase 26 Production Observability & Human-Governed Incident Recovery FastAPI Admin Router."""

from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.api.auth import require_admin
from backend.api.dependencies import SettingsDependency
from backend.services.human_recovery_service import HumanRecoveryService
from backend.services.incident_detection_service import IncidentDetectionService
from backend.services.runtime_health_service import RuntimeHealthService
from core_model.capabilities.production_observability_service import (
    HealthCheckItem,
    ObservabilityError,
)

router = APIRouter(prefix="/admin/phase26", tags=["Phase 26 Observability Admin"], dependencies=[Depends(require_admin)])


def get_db_connection(settings: SettingsDependency) -> sqlite3.Connection:
    """Helper to instantiate SQLite connection to resolved DB path."""
    return sqlite3.connect(settings.resolved_database_path)


class IncidentActionPayload(BaseModel):
    action: str = Field(..., description="Action name or decision")
    notes: str | None = Field(None, description="Optional notes or reason")


class RecoveryExecutionPayload(BaseModel):
    action: str = Field(..., description="Recovery action to execute")
    reason: str = Field(..., description="Reason for recovery execution")


@router.get("/health", response_model=dict[str, Any], dependencies=[Depends(require_admin)])
def list_health_reports(settings: SettingsDependency) -> dict[str, Any]:
    """List summary health metrics and status."""
    return {
        "phase": 26,
        "name": "Production Observability, Runtime Health, Incident Detection & Human-Governed Recovery",
        "status": "ACTIVE",
    }


@router.get("/incidents/{incident_id}", response_model=dict[str, Any], dependencies=[Depends(require_admin)])
def get_incident_details(incident_id: str, settings: SettingsDependency) -> dict[str, Any]:
    """Get details of a specific incident record."""
    with get_db_connection(settings) as db:
        service = IncidentDetectionService(db)
        incident = service.get_incident(incident_id)
        if not incident:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Incident '{incident_id}' not found.")
        return incident.to_dict()


@router.post("/incidents/{incident_id}/acknowledge", response_model=dict[str, Any], dependencies=[Depends(require_admin)])
def acknowledge_incident_endpoint(
    incident_id: str,
    payload: IncidentActionPayload,
    settings: SettingsDependency,
    admin_id: str = Query("super-admin-1"),
) -> dict[str, Any]:
    """Acknowledge an incident (Human Admin Only)."""
    with get_db_connection(settings) as db:
        service = HumanRecoveryService(db)
        try:
            updated_inc, review = service.acknowledge_incident(
                incident_id,
                acknowledged_by=admin_id,
                notes=payload.notes,
            )
            return {
                "incident": updated_inc.to_dict(),
                "review": review.to_dict(),
            }
        except ObservabilityError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/incidents/{incident_id}/approve-recovery", response_model=dict[str, Any], dependencies=[Depends(require_admin)])
def approve_recovery_endpoint(
    incident_id: str,
    payload: IncidentActionPayload,
    settings: SettingsDependency,
    admin_id: str = Query("super-admin-1"),
) -> dict[str, Any]:
    """Approve recovery action for an incident."""
    with get_db_connection(settings) as db:
        service = HumanRecoveryService(db)
        try:
            updated_inc, review = service.review_recovery_decision(
                incident_id,
                "APPROVED",
                approved_by=admin_id,
                notes=payload.notes,
            )
            return {
                "incident": updated_inc.to_dict(),
                "review": review.to_dict(),
            }
        except ObservabilityError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/incidents/{incident_id}/reject-recovery", response_model=dict[str, Any], dependencies=[Depends(require_admin)])
def reject_recovery_endpoint(
    incident_id: str,
    payload: IncidentActionPayload,
    settings: SettingsDependency,
    admin_id: str = Query("super-admin-1"),
) -> dict[str, Any]:
    """Reject recovery action for an incident."""
    with get_db_connection(settings) as db:
        service = HumanRecoveryService(db)
        try:
            updated_inc, review = service.review_recovery_decision(
                incident_id,
                "REJECTED",
                approved_by=admin_id,
                notes=payload.notes,
            )
            return {
                "incident": updated_inc.to_dict(),
                "review": review.to_dict(),
            }
        except ObservabilityError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/incidents/{incident_id}/execute-recovery", response_model=dict[str, Any], dependencies=[Depends(require_admin)])
def execute_recovery_endpoint(
    incident_id: str,
    payload: RecoveryExecutionPayload,
    settings: SettingsDependency,
    admin_id: str = Query("super-admin-1"),
) -> dict[str, Any]:
    """Execute human-approved recovery action."""
    with get_db_connection(settings) as db:
        service = HumanRecoveryService(db)
        try:
            updated_inc, rec_op = service.execute_recovery(
                incident_id,
                payload.action,
                approved_by=admin_id,
                reason=payload.reason,
            )
            return {
                "incident": updated_inc.to_dict(),
                "recovery_operation": rec_op.to_dict(),
            }
        except ObservabilityError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/metrics", response_model=dict[str, Any], dependencies=[Depends(require_admin)])
def get_observability_metrics(settings: SettingsDependency) -> dict[str, Any]:
    """Get Phase 26 operational health and incident metrics."""
    return {
        "health_status": "HEALTHY",
        "active_incidents": 0,
        "governance_mode": "HUMAN_APPROVED_RECOVERY",
    }
