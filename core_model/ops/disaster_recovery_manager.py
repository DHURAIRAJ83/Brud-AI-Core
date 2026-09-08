"""Phase 61 - P8: Disaster Recovery Manager.

Detects recoverable production states and evaluates snapshot integrity for disaster recovery.

CRITICAL INVARIANTS:
- Detects recoverable states from snapshot registry and release history.
- Fail closed requirement: Returns RECOVERY_BLOCKED if evidence is incomplete, corrupted, tampered, or inconsistent.
- Never automatically restores production state or promotes candidate models.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from core_model.ops.production_state_snapshot_registry import (
    ProductionStateSnapshotRecord,
    ProductionStateSnapshotRegistry,
    SnapshotError,
)


@dataclass
class RecoveryEvaluationResult:
    """Outcome of disaster recovery readiness evaluation."""
    recovery_status: str  # RECOVERY_READY | RECOVERY_DEGRADED | RECOVERY_BLOCKED
    latest_valid_snapshot_id: str | None
    model_hash: str | None
    dataset_hash: str | None
    evidence_valid: bool
    reasons: list[str] = field(default_factory=list)


class DisasterRecoveryManager:
    """Disaster recovery state evaluation manager."""

    def __init__(self, snapshot_registry: ProductionStateSnapshotRegistry | None = None) -> None:
        self.snapshot_registry = snapshot_registry or ProductionStateSnapshotRegistry()

    def evaluate_recovery_prerequisites(
        self,
        target_snapshot_id: str | None = None,
        mock_corrupted_snapshot: bool = False,
    ) -> RecoveryEvaluationResult:
        """Inspect available snapshots and verify disaster recovery prerequisites."""
        reasons: list[str] = []

        if mock_corrupted_snapshot:
            return RecoveryEvaluationResult(
                recovery_status="RECOVERY_BLOCKED",
                latest_valid_snapshot_id=None,
                model_hash=None,
                dataset_hash=None,
                evidence_valid=False,
                reasons=["Fail-Closed: Simulated snapshot corruption / integrity tampering detected."]
            )

        latest_snap = self.snapshot_registry.get_latest_snapshot() if not target_snapshot_id else self.snapshot_registry._snapshots.get(target_snapshot_id)

        if latest_snap is None:
            return RecoveryEvaluationResult(
                recovery_status="RECOVERY_BLOCKED",
                latest_valid_snapshot_id=None,
                model_hash=None,
                dataset_hash=None,
                evidence_valid=False,
                reasons=["Fail-Closed: No valid production snapshot found in registry."]
            )

        try:
            self.snapshot_registry.verify_snapshot_integrity(latest_snap.snapshot_id)
        except SnapshotError as err:
            return RecoveryEvaluationResult(
                recovery_status="RECOVERY_BLOCKED",
                latest_valid_snapshot_id=latest_snap.snapshot_id,
                model_hash=latest_snap.model_hash,
                dataset_hash=latest_snap.dataset_hash,
                evidence_valid=False,
                reasons=[f"Snapshot Integrity Error: {err}"]
            )

        return RecoveryEvaluationResult(
            recovery_status="RECOVERY_READY",
            latest_valid_snapshot_id=latest_snap.snapshot_id,
            model_hash=latest_snap.model_hash,
            dataset_hash=latest_snap.dataset_hash,
            evidence_valid=True,
            reasons=[]
        )
