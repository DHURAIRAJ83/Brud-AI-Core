"""Phase 26 Incident Detection Backend Service."""

from __future__ import annotations

import sqlite3
from typing import Sequence

from backend.database.repositories.observability_repository import ObservabilityRepository
from core_model.capabilities.production_observability_service import (
    IncidentRecord,
    ProductionObservabilityService,
    RecoveryRecommendation,
    RuntimeHealthReport,
)


class IncidentDetectionService:
    """Backend service for detecting incidents and generating recovery recommendations."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.repo = ObservabilityRepository(conn)
        self.domain_service = ProductionObservabilityService()

    def process_health_report_for_incidents(
        self,
        report: RuntimeHealthReport,
    ) -> tuple[IncidentRecord, ...]:
        """Detect failing checks in report and store incident records."""
        incidents = self.domain_service.detect_incidents(report)
        for inc in incidents:
            self.repo.insert_incident(inc)
            # Generate and store recovery recommendation (NON-AUTONOMOUS)
            rec = self.domain_service.generate_recovery_recommendations(inc)
            self.repo.insert_recovery_recommendation(rec)
        return incidents

    def get_incident(self, incident_id: str) -> IncidentRecord | None:
        """Fetch incident by ID."""
        return self.repo.get_incident(incident_id)
