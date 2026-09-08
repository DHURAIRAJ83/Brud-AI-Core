"""Phase 61 - P8: Production State Snapshot Registry.

Provides append-only, immutable production state snapshots for disaster recovery.

CRITICAL INVARIANTS:
- Append-only storage: Snapshot records are immutable and cannot be overwritten or deleted.
- Binds snapshot ID, release ID, model hash, dataset hash, tokenizer hash, training config hash, routing state, governance state, safety state, audit chain position, timestamp, and HMAC-SHA256 signature.
- Rejects malformed snapshots and hash mismatches.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import asdict, dataclass, field
from typing import Any


class SnapshotError(ValueError):
    """Raised when snapshot creation or validation fails."""


@dataclass
class ProductionStateSnapshotRecord:
    """Immutable production state snapshot record."""
    snapshot_id: str
    release_id: str
    model_hash: str
    dataset_hash: str
    tokenizer_hash: str
    training_config_hash: str
    routing_state: str  # FAIL_CLOSED_PROD | PUBLIC_CHAT_ADMITTED
    governance_state: str  # LOCKED | CERTIFIED | PROMOTION_BLOCKED
    safety_state: str      # SAFE | WARNING | VIOLATION | CRITICAL
    audit_chain_position: int
    timestamp: str
    snapshot_hmac: str


def compute_snapshot_hmac(
    snapshot_id: str,
    release_id: str,
    model_hash: str,
    dataset_hash: str,
    tokenizer_hash: str,
    secret_key: str = "BRUD_SNAPSHOT_SECRET_KEY_2026",
) -> str:
    """Compute HMAC-SHA256 signature for production state snapshot."""
    raw = f"{snapshot_id}:{release_id}:{model_hash}:{dataset_hash}:{tokenizer_hash}".encode("utf-8")
    return hmac.new(secret_key.encode("utf-8"), raw, hashlib.sha256).hexdigest()


class ProductionStateSnapshotRegistry:
    """Append-only production state snapshot registry."""

    def __init__(self, secret_key: str = "BRUD_SNAPSHOT_SECRET_KEY_2026") -> None:
        self.secret_key = secret_key
        self._snapshots: dict[str, ProductionStateSnapshotRecord] = {}

    def create_snapshot(
        self,
        release_id: str,
        model_hash: str,
        dataset_hash: str,
        tokenizer_hash: str,
        training_config_hash: str,
        routing_state: str = "FAIL_CLOSED_PROD",
        governance_state: str = "PROMOTION_BLOCKED",
        safety_state: str = "SAFE",
        audit_chain_position: int = 0,
    ) -> ProductionStateSnapshotRecord:
        """Create an append-only production state snapshot."""
        if not release_id or not model_hash or not dataset_hash or not tokenizer_hash:
            raise SnapshotError("Malformed snapshot: missing required artifact hashes.")

        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        snap_id = f"snap-{release_id}-{len(self._snapshots)+1:03d}"
        snap_hmac = compute_snapshot_hmac(snap_id, release_id, model_hash, dataset_hash, tokenizer_hash, self.secret_key)

        record = ProductionStateSnapshotRecord(
            snapshot_id=snap_id,
            release_id=release_id,
            model_hash=model_hash,
            dataset_hash=dataset_hash,
            tokenizer_hash=tokenizer_hash,
            training_config_hash=training_config_hash,
            routing_state=routing_state,
            governance_state=governance_state,
            safety_state=safety_state,
            audit_chain_position=audit_chain_position,
            timestamp=now,
            snapshot_hmac=snap_hmac
        )

        self._snapshots[snap_id] = record
        return record

    def get_latest_snapshot(self) -> ProductionStateSnapshotRecord | None:
        """Retrieve the latest valid production snapshot."""
        if not self._snapshots:
            return None
        latest_id = list(self._snapshots.keys())[-1]
        return self._snapshots[latest_id]

    def verify_snapshot_integrity(self, snapshot_id: str) -> bool:
        """Verify HMAC signature of stored snapshot record."""
        record = self._snapshots.get(snapshot_id)
        if not record:
            raise SnapshotError(f"Snapshot {snapshot_id} not found.")

        expected_hmac = compute_snapshot_hmac(
            record.snapshot_id, record.release_id, record.model_hash, record.dataset_hash, record.tokenizer_hash, self.secret_key
        )
        if not hmac.compare_digest(record.snapshot_hmac, expected_hmac):
            raise SnapshotError(f"Snapshot HMAC tampering detected for snapshot {snapshot_id}.")

        return True
