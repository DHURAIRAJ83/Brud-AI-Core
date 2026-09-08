"""Phase 61 - P7: Cryptographic Production Audit Chain.

Provides an append-only, tamper-evident cryptographic event log for all production governance actions.

CRITICAL INVARIANTS:
- Event Chaining: event_n.previous_hash = event_(n-1).hash.
- SHA-256 deterministic event hashing.
- Tamper-detection fail-closed requirement: Modified, deleted, inserted, or reordered events invalidate verification.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import asdict, dataclass, field
from typing import Any


class AuditChainError(ValueError):
    """Raised when audit chain verification or event logging fails."""


@dataclass
class AuditEventRecord:
    """Cryptographically linked audit event record."""
    event_id: str
    sequence_number: int
    event_type: str
    release_id: str
    model_hash: str
    actor_identity: str
    action: str
    decision: str
    evidence_hash: str
    timestamp: str
    previous_hash: str
    event_hash: str


def compute_event_hash(
    event_id: str,
    sequence_number: int,
    event_type: str,
    release_id: str,
    model_hash: str,
    actor_identity: str,
    action: str,
    decision: str,
    evidence_hash: str,
    timestamp: str,
    previous_hash: str,
) -> str:
    """Compute SHA-256 event hash for cryptographic chaining."""
    raw = f"{event_id}:{sequence_number}:{event_type}:{release_id}:{model_hash}:{actor_identity}:{action}:{decision}:{evidence_hash}:{timestamp}:{previous_hash}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class ProductionAuditChain:
    """Append-only cryptographic audit chain."""

    GENESIS_HASH = "0000000000000000000000000000000000000000000000000000000000000000"

    def __init__(self) -> None:
        self._chain: list[AuditEventRecord] = []

    def append_event(
        self,
        event_type: str,
        release_id: str,
        model_hash: str,
        actor_identity: str,
        action: str,
        decision: str,
        evidence_hash: str,
    ) -> AuditEventRecord:
        """Append a new cryptographically chained audit event."""
        seq_num = len(self._chain) + 1
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        event_id = f"evt-chain-{seq_num:06d}"

        prev_hash = self.GENESIS_HASH if seq_num == 1 else self._chain[-1].event_hash
        event_hash = compute_event_hash(
            event_id, seq_num, event_type, release_id, model_hash, actor_identity, action, decision, evidence_hash, now, prev_hash
        )

        rec = AuditEventRecord(
            event_id=event_id,
            sequence_number=seq_num,
            event_type=event_type,
            release_id=release_id,
            model_hash=model_hash,
            actor_identity=actor_identity,
            action=action,
            decision=decision,
            evidence_hash=evidence_hash,
            timestamp=now,
            previous_hash=prev_hash,
            event_hash=event_hash
        )
        self._chain.append(rec)
        return rec

    def verify_chain_integrity(self) -> bool:
        """Verify complete cryptographic audit chain integrity. Returns True or raises AuditChainError."""
        if not self._chain:
            return True

        for i, event in enumerate(self._chain):
            expected_seq = i + 1
            if event.sequence_number != expected_seq:
                raise AuditChainError(f"Chain sequence error at index {i}: expected {expected_seq}, got {event.sequence_number}")

            expected_prev_hash = self.GENESIS_HASH if i == 0 else self._chain[i - 1].event_hash
            if event.previous_hash != expected_prev_hash:
                raise AuditChainError(f"Chain link broken at event {event.event_id}: previous_hash mismatch.")

            computed_hash = compute_event_hash(
                event.event_id,
                event.sequence_number,
                event.event_type,
                event.release_id,
                event.model_hash,
                event.actor_identity,
                event.action,
                event.decision,
                event.evidence_hash,
                event.timestamp,
                event.previous_hash
            )
            if event.event_hash != computed_hash:
                raise AuditChainError(f"Event hash tampering detected at event {event.event_id}.")

        return True

    def get_chain(self) -> list[AuditEventRecord]:
        """Return list of chained audit events."""
        return list(self._chain)
