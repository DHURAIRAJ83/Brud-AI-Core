"""Phase 26 Human-Governed Incident Recovery Backend Service."""

from __future__ import annotations

import sqlite3

from backend.database.repositories.observability_repository import ObservabilityRepository
from core_model.capabilities.production_observability_service import (
    IncidentRecord,
    IncidentReview,
    ProductionObservabilityService,
    RecoveryLockError,
    RecoveryOperation,
    compute_recovery_idempotency_key,
)


class HumanRecoveryService:
    """Backend service managing human review, concurrency locking, and recovery execution."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.repo = ObservabilityRepository(conn)
        self.domain_service = ProductionObservabilityService()

    def acknowledge_incident(
        self,
        incident_id: str,
        *,
        acknowledged_by: str,
        notes: str | None = None,
    ) -> tuple[IncidentRecord, IncidentReview]:
        """Acknowledge an incident (Human Admin Only)."""
        incident = self.repo.get_incident(incident_id)
        if not incident:
            raise ValueError(f"Incident '{incident_id}' not found.")

        updated_inc, review = self.domain_service.process_incident_acknowledgement(
            incident,
            acknowledged_by=acknowledged_by,
            notes=notes,
        )
        self.repo.update_incident_status(incident_id, updated_inc.status)
        self.repo.insert_incident_review(review)
        return updated_inc, review

    def review_recovery_decision(
        self,
        incident_id: str,
        decision: str,
        *,
        approved_by: str,
        notes: str | None = None,
    ) -> tuple[IncidentRecord, IncidentReview]:
        """Process explicit human admin recovery decision (APPROVED, REJECTED, DEFERRED)."""
        incident = self.repo.get_incident(incident_id)
        if not incident:
            raise ValueError(f"Incident '{incident_id}' not found.")

        updated_inc, review = self.domain_service.process_recovery_approval(
            incident,
            decision,
            approved_by=approved_by,
            notes=notes,
        )
        self.repo.update_incident_status(incident_id, updated_inc.status)
        self.repo.insert_incident_review(review)
        return updated_inc, review

    def execute_recovery(
        self,
        incident_id: str,
        action: str,
        *,
        approved_by: str,
        reason: str,
    ) -> tuple[IncidentRecord, RecoveryOperation]:
        """Execute human-approved recovery with concurrency locking and idempotency key protection."""
        incident = self.repo.get_incident(incident_id)
        if not incident:
            raise ValueError(f"Incident '{incident_id}' not found.")

        idemp_key = compute_recovery_idempotency_key(incident_id, action)
        existing_op = self.repo.get_recovery_operation_by_idempotency_key(idemp_key)
        if existing_op:
            return incident, existing_op

        lock_key = f"lock-rec-{incident.incident_id}"
        lock_acquired = self.repo.acquire_health_lock(lock_key, incident.incident_id, approved_by)
        if not lock_acquired:
            raise RecoveryLockError(f"Concurrent recovery operation already in progress for incident '{incident_id}'.")

        try:
            updated_inc, rec_op = self.domain_service.execute_recovery(
                incident,
                action,
                approved_by=approved_by,
                reason=reason,
            )
            self.repo.update_incident_status(incident_id, updated_inc.status)
            self.repo.insert_recovery_operation(rec_op)
            return updated_inc, rec_op
        finally:
            self.repo.release_health_lock(lock_key)
