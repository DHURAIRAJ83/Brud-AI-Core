"""Phase 26 Runtime Health Backend Service."""

from __future__ import annotations

import sqlite3
from typing import Sequence

from backend.database.repositories.observability_repository import ObservabilityRepository
from core_model.capabilities.production_observability_service import (
    HealthCheckItem,
    HealthTrendComparison,
    ObservabilityProvenance,
    ProductionObservabilityService,
    RuntimeHealthReport,
)


class RuntimeHealthService:
    """Backend service managing runtime health reports and comparisons."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.repo = ObservabilityRepository(conn)
        self.domain_service = ProductionObservabilityService()

    def generate_and_store_report(
        self,
        deployment_id: str,
        release_id: str,
        active_version: str,
        checks: Sequence[HealthCheckItem],
        *,
        created_by: str,
        provenance: ObservabilityProvenance | None = None,
    ) -> RuntimeHealthReport:
        """Generate a runtime health report and persist it in the repository."""
        report = self.domain_service.generate_health_report(
            deployment_id=deployment_id,
            release_id=release_id,
            active_version=active_version,
            checks=checks,
            created_by=created_by,
            provenance=provenance,
        )
        self.repo.insert_health_report(report)
        return report

    def compare_reports(
        self,
        report_id_a: str,
        report_id_b: str,
    ) -> HealthTrendComparison:
        """Compare two stored health reports."""
        report_a = self.repo.get_health_report(report_id_a)
        if not report_a:
            raise ValueError(f"Health report '{report_id_a}' not found.")

        report_b = self.repo.get_health_report(report_id_b)
        if not report_b:
            raise ValueError(f"Health report '{report_id_b}' not found.")

        return self.domain_service.compare_health_reports(report_a, report_b)
