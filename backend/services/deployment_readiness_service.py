"""Phase 25 — Deployment Readiness Backend Service.

Coordinates pre-deployment readiness verification, report generation, secret scans,
SECURITY_ADMIN_BOUNDARY hard blocking, and check aggregation for Phase 24 ACTIVE releases.

CRITICAL INVARIANTS:
- Phase 24 ACTIVE release is required.
- Readiness PASS alone MUST NOT execute deployment.
- Human admin review and approval is strictly required.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from backend.database.repositories.deployment_repository import DeploymentRepository
from backend.database.repositories.release_repository import ReleaseRepository
from core_model.capabilities.deployment_readiness_service import (
    DEPLOYMENT_STAGE_VALIDATED,
    DeploymentPreflightError,
    DeploymentReadinessReport,
    DeploymentReadinessService as DomainDeploymentReadinessService,
)


class DeploymentReadinessBackendService:
    """Backend service for executing deployment readiness preflights and report persistence."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.release_repo = ReleaseRepository(conn)
        self.deployment_repo = DeploymentRepository(conn)
        self.domain_service = DomainDeploymentReadinessService()

    def run_preflight(
        self,
        release_id: str,
        *,
        created_by: str,
        target_environment: str = "production",
        content_text: str = "Validated production deployment release content",
    ) -> DeploymentReadinessReport:
        """Run pre-deployment readiness checks and persist report."""
        rel_cand = self.release_repo.get_release_by_id(release_id)
        if not rel_cand:
            raise ValueError(f"Release candidate '{release_id}' not found.")

        report = self.domain_service.generate_readiness_report(
            release_candidate=rel_cand,
            content_text=content_text,
            created_by=created_by,
            target_environment=target_environment,
        )

        self.deployment_repo.insert_readiness_report(report)
        return report

    def get_readiness_report(self, readiness_id: str) -> DeploymentReadinessReport:
        """Fetch a persisted readiness report by readiness ID."""
        report = self.deployment_repo.get_readiness_report_by_id(readiness_id)
        if not report:
            raise ValueError(f"Deployment readiness report '{readiness_id}' not found.")
        return report
