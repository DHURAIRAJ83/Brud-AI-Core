"""Phase 25 — Non-Destructive Deployment Rollback Backend Service.

Executes non-destructive deployment rollback from active deployed release version to target historical version.

CRITICAL INVARIANTS:
- Explicit human admin approval is strictly mandatory.
- Rollback is non-destructive: version pointer updated back without deleting history or files.
- Rollback operation log and audit reference recorded atomically.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from backend.database.repositories.deployment_repository import DeploymentRepository
from backend.database.repositories.release_repository import ReleaseRepository
from core_model.capabilities.deployment_readiness_service import (
    DEPLOYMENT_STAGE_ROLLED_BACK,
    DEPLOYMENT_STAGE_VERIFIED,
    DeploymentReadinessReport,
    DeploymentReadinessService as DomainDeploymentReadinessService,
    DeploymentRollback,
)


class DeploymentRollbackBackendService:
    """Backend service for executing non-destructive deployment rollbacks."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.release_repo = ReleaseRepository(conn)
        self.deployment_repo = DeploymentRepository(conn)
        self.domain_service = DomainDeploymentReadinessService()

    def rollback_deployment(
        self,
        readiness_id: str,
        target_historical_version: str,
        *,
        approved_by: str,
        reason: str = "Administrative deployment rollback",
    ) -> tuple[DeploymentReadinessReport, DeploymentRollback]:
        """Execute non-destructive deployment rollback to target historical version."""
        report = self.deployment_repo.get_readiness_report_by_id(readiness_id)
        if not report:
            raise ValueError(f"Deployment readiness report '{readiness_id}' not found.")

        rolled_back_report, rb_op = self.domain_service.rollback_deployment(
            report, target_historical_version, approved_by=approved_by, reason=reason
        )

        with self.conn:
            self.deployment_repo.update_readiness_status(rolled_back_report)
            self.deployment_repo.insert_deployment_rollback(rb_op)

        return rolled_back_report, rb_op
