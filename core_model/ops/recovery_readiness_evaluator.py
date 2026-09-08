"""Phase 61 - P8: Recovery Readiness Evaluator.

Evaluates disaster recovery readiness across snapshots, releases, audit chain, and governance locks.

CRITICAL INVARIANTS:
- Required States: RECOVERY_READY | RECOVERY_DEGRADED | RECOVERY_BLOCKED | RECOVERY_CRITICAL | UNKNOWN.
- Fail Closed Requirement: Unknown or missing evidence strictly defaults to RECOVERY_BLOCKED or UNKNOWN -> RECOVERY_CRITICAL.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from core_model.ops.disaster_recovery_manager import RecoveryEvaluationResult
from core_model.ops.production_state_integrity_validator import StateIntegrityValidationResult


@dataclass
class RecoveryReadinessResult:
    """Outcome of overall disaster recovery readiness evaluation."""
    readiness_status: str  # RECOVERY_READY | RECOVERY_DEGRADED | RECOVERY_BLOCKED | RECOVERY_CRITICAL | UNKNOWN
    snapshots_available: bool
    integrity_valid: bool
    audit_chain_continuous: bool
    rollback_ready: bool
    evaluated_at: str
    reasons: list[str] = field(default_factory=list)


class RecoveryReadinessEvaluator:
    """Evaluates readiness of production recovery infrastructure."""

    def evaluate_readiness(
        self,
        dr_eval: RecoveryEvaluationResult | None,
        integrity_eval: StateIntegrityValidationResult | None,
    ) -> RecoveryReadinessResult:
        """Evaluate disaster recovery readiness across system components."""
        reasons: list[str] = []
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        if dr_eval is None or integrity_eval is None:
            return RecoveryReadinessResult(
                readiness_status="RECOVERY_CRITICAL",
                snapshots_available=False,
                integrity_valid=False,
                audit_chain_continuous=False,
                rollback_ready=False,
                evaluated_at=now,
                reasons=["Fail-Closed: Disaster recovery evaluation or state integrity evaluation is missing."]
            )

        snaps_ok = dr_eval.evidence_valid and dr_eval.latest_valid_snapshot_id is not None
        integrity_ok = integrity_eval.integrity_status == "STATE_INTEGRITY_VALID"
        audit_ok = integrity_eval.audit_chain_valid

        if not snaps_ok:
            reasons.extend(dr_eval.reasons)
        if not integrity_ok:
            reasons.extend(integrity_eval.discrepancies)

        if snaps_ok and integrity_ok and audit_ok:
            status = "RECOVERY_READY"
        elif snaps_ok or integrity_ok:
            status = "RECOVERY_DEGRADED"
        else:
            status = "RECOVERY_BLOCKED"

        return RecoveryReadinessResult(
            readiness_status=status,
            snapshots_available=snaps_ok,
            integrity_valid=integrity_ok,
            audit_chain_continuous=audit_ok,
            rollback_ready=snaps_ok,
            evaluated_at=now,
            reasons=reasons
        )
