"""Phase 25 — Deployment Gate & Atomic Execution Backend Service.

Coordinates human deployment approval decisions (APPROVED, REJECTED, DEFERRED), deployment concurrency locks,
idempotent execution, and atomic deployment state updates.

CRITICAL INVARIANTS:
- Explicit human admin approval is strictly mandatory before deployment execution.
- Readiness PASS != Deployment Approval != Deployment Execution.
- Deployment operations are idempotent and concurrency lock protected.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from backend.database.repositories.deployment_repository import DeploymentRepository
from backend.database.repositories.release_repository import ReleaseRepository
from core_model.capabilities.deployment_readiness_service import (
    DEPLOYMENT_STAGE_APPROVED,
    DEPLOYMENT_STAGE_DEFERRED,
    DEPLOYMENT_STAGE_READY,
    DEPLOYMENT_STAGE_REJECTED,
    DEPLOYMENT_STAGE_VERIFIED,
    DeploymentApproval,
    DeploymentApprovalRequiredError,
    DeploymentLockError,
    DeploymentOperation,
    DeploymentReadinessReport,
    DeploymentReadinessService as DomainDeploymentReadinessService,
    compute_deployment_idempotency_key,
)


class DeploymentGateService:
    """Backend service for deployment human review decisions, concurrency locking, and execution."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.release_repo = ReleaseRepository(conn)
        self.deployment_repo = DeploymentRepository(conn)
        self.domain_service = DomainDeploymentReadinessService()

    def review_deployment(
        self,
        readiness_id: str,
        decision: str,
        *,
        reviewer_id: str,
        reviewer_notes: str | None = None,
    ) -> tuple[DeploymentReadinessReport, DeploymentApproval]:
        """Apply human admin deployment approval decision (APPROVED, REJECTED, DEFERRED)."""
        report = self.deployment_repo.get_readiness_report_by_id(readiness_id)
        if not report:
            raise ValueError(f"Deployment readiness report '{readiness_id}' not found.")

        updated_report, approval = self.domain_service.process_deployment_approval(
            report, decision, approved_by=reviewer_id, reviewer_notes=reviewer_notes
        )

        self.deployment_repo.update_readiness_status(updated_report)
        self.deployment_repo.insert_deployment_approval(approval)
        return updated_report, approval

    def execute_deployment(
        self,
        readiness_id: str,
        *,
        approved_by: str,
    ) -> tuple[DeploymentReadinessReport, DeploymentOperation]:
        """Atomically execute a DEPLOYMENT_APPROVED release deployment."""
        report = self.deployment_repo.get_readiness_report_by_id(readiness_id)
        if not report:
            raise ValueError(f"Deployment readiness report '{readiness_id}' not found.")

        # Idempotency Check
        idemp_key = compute_deployment_idempotency_key(report.release_id, report.active_version, report.target_environment)
        existing_op = self.deployment_repo.get_deployment_by_idempotency_key(idemp_key)
        if existing_op and report.readiness_status == DEPLOYMENT_STAGE_VERIFIED:
            return report, existing_op

        # Acquire Deployment Concurrency Lock
        dep_id_temp = f"dep-temp-{report.readiness_id}"
        lock_acquired = self.deployment_repo.acquire_deployment_lock(report.release_id, dep_id_temp, approved_by)
        if not lock_acquired:
            raise DeploymentLockError(f"Deployment lock active for release '{report.release_id}'. Concurrent deployment prohibited.")

        try:
            prev_pointer = self.release_repo.get_active_version_pointer(report.provenance.artifact_type, "default")
            prev_ver = prev_pointer["active_release_version"] if prev_pointer else None

            verified_report, dep_op = self.domain_service.execute_deployment(
                report, previous_version=prev_ver, approved_by=approved_by
            )

            with self.conn:
                self.deployment_repo.update_readiness_status(verified_report)
                self.deployment_repo.insert_deployment_operation(dep_op)
        finally:
            self.deployment_repo.release_deployment_lock(report.release_id, dep_id_temp)

        return verified_report, dep_op
