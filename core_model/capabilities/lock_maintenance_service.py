"""Phase 28 — Operations Hardening & Stale-Lock Governance Pure Domain Module.

Provides pure domain logic, dataclasses, stale-lock calculation, idempotency key computation,
and 16-step provenance chain tracking for Phase 24, 25, and 26 concurrency locks.
Zero database, zero network, zero shell execution, zero autonomous execution.
"""

import hashlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


class LockMaintenanceError(Exception):
    """Base domain exception for Phase 28 Lock Maintenance capabilities."""

    pass


class InvalidLockError(LockMaintenanceError):
    """Raised when a lock record or lock table is invalid or malformed."""

    pass


class LockReleaseError(LockMaintenanceError):
    """Raised when lock release fails or is unauthorized."""

    pass


@dataclass(frozen=True)
class LockMaintenanceProvenance:
    """Extended 16-step provenance chain for Phase 28 lock maintenance operations."""

    source_request_id: str | None = None
    source_gap_id: str | None = None
    source_record_id: str | None = None
    candidate_id: str | None = None
    operation_id: str | None = None
    artifact_id: str | None = None
    evaluation_id: str | None = None
    comparison_id: str | None = None
    review_id: str | None = None
    release_id: str | None = None
    promotion_operation_id: str | None = None
    deployment_id: str | None = None
    health_report_id: str | None = None
    health_check_id: str | None = None
    incident_id: str | None = None
    recovery_id: str | None = None
    lock_maintenance_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "LockMaintenanceProvenance":
        if not data:
            return cls()
        known_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_keys}
        return cls(**filtered)


@dataclass(frozen=True)
class StaleLockRecord:
    """Domain model representing a concurrency lock inspected for stale status."""

    lock_table: str  # phase24_release_locks, phase25_deployment_locks, phase26_health_locks
    lock_key: str
    resource_id: str
    acquired_by: str
    acquired_at: str  # ISO timestamp
    age_seconds: float
    lock_ttl_seconds: float
    is_stale: bool
    phase_origin: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LockInspectionReport:
    """Summary report of concurrency locks across Phase 24, 25, and 26."""

    inspection_id: str
    inspected_at: str
    total_locks_count: int
    stale_locks_count: int
    fresh_locks_count: int
    locks: list[StaleLockRecord] = field(default_factory=list)
    provenance: LockMaintenanceProvenance = field(default_factory=LockMaintenanceProvenance)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["locks"] = [l.to_dict() for l in self.locks]
        d["provenance"] = self.provenance.to_dict()
        return d


@dataclass(frozen=True)
class LockCleanupOperation:
    """Record of a human-authorized stale lock cleanup operation."""

    cleanup_id: str
    lock_table: str
    lock_key: str
    resource_id: str
    released_by: str
    released_at: str
    reason: str
    idempotency_key: str
    audit_reference: str
    provenance: LockMaintenanceProvenance = field(default_factory=LockMaintenanceProvenance)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["provenance"] = self.provenance.to_dict()
        return d


def compute_lock_age_seconds(acquired_at_iso: str, current_time_iso: str | None = None) -> float:
    """Calculate lock age in seconds given an ISO timestamp string."""
    try:
        acq_dt = datetime.fromisoformat(acquired_at_iso.replace("Z", "+00:00"))
        if acq_dt.tzinfo is None:
            acq_dt = acq_dt.replace(tzinfo=timezone.utc)

        if current_time_iso:
            cur_dt = datetime.fromisoformat(current_time_iso.replace("Z", "+00:00"))
            if cur_dt.tzinfo is None:
                cur_dt = cur_dt.replace(tzinfo=timezone.utc)
        else:
            cur_dt = datetime.now(timezone.utc)

        diff = (cur_dt - acq_dt).total_seconds()
        return max(0.0, diff)
    except Exception as e:
        raise InvalidLockError(f"Invalid timestamp format '{acquired_at_iso}': {e}")


def is_lock_stale(age_seconds: float, lock_ttl_seconds: float) -> bool:
    """Deterministic stale lock calculation: age_seconds > lock_ttl_seconds."""
    if age_seconds < 0.0 or lock_ttl_seconds <= 0.0:
        return False
    return age_seconds > lock_ttl_seconds


def compute_lock_cleanup_idempotency_key(
    lock_table: str,
    lock_key: str,
    released_by: str,
) -> str:
    """Compute deterministic SHA-256 idempotency key for lock release operation."""
    raw = f"phase28_lock_cleanup:{lock_table}:{lock_key}:{released_by}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
