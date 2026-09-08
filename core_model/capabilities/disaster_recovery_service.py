"""Phase 29 — Disaster Recovery, Backup Integrity & Business Continuity Pure Domain Module.

Provides pure domain logic, dataclasses, SHA-256 checksum computation, RPO freshness calculation,
restore preflight report generation, and idempotency key computation for disaster recovery.
Zero database, zero network, zero subprocess, zero autonomous execution.
"""

import hashlib
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


class DisasterRecoveryError(Exception):
    """Base domain exception for Phase 29 Disaster Recovery capabilities."""

    pass


class BackupIntegrityError(DisasterRecoveryError):
    """Raised when a backup snapshot SHA-256 checksum or file size fails validation."""

    pass


class RestoreError(DisasterRecoveryError):
    """Raised when restore preflight or restore execution fails or is unauthorized."""

    pass


@dataclass(frozen=True)
class DisasterRecoveryProvenance:
    """Extended 16-step provenance chain for Phase 29 disaster recovery operations."""

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
    backup_id: str | None = None
    restore_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "DisasterRecoveryProvenance":
        if not data:
            return cls()
        known_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_keys}
        return cls(**filtered)


@dataclass(frozen=True)
class BackupMetadataRecord:
    """Domain model representing a database snapshot backup record."""

    backup_id: str
    backup_type: str  # FULL_SNAPSHOT, DIFFERENTIAL, EMERGENCY_PRE_RESTORE
    source_db_sha256: str
    backup_sha256: str
    backup_size_bytes: int
    created_at: str  # ISO timestamp
    storage_path: str
    rpo_freshness_seconds: float
    is_verified: bool
    created_by: str
    provenance: DisasterRecoveryProvenance = field(default_factory=DisasterRecoveryProvenance)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["provenance"] = self.provenance.to_dict()
        return d


@dataclass(frozen=True)
class RestorePreflightReport:
    """Domain model representing the dry-run preflight inspection prior to restore execution."""

    preflight_id: str
    backup_id: str
    checksum_match: bool
    integrity_check_passed: bool
    can_restore: bool
    checked_at: str
    notes: str
    provenance: DisasterRecoveryProvenance = field(default_factory=DisasterRecoveryProvenance)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["provenance"] = self.provenance.to_dict()
        return d


@dataclass(frozen=True)
class RestoreOperationRecord:
    """Record of an explicit human-authorized database restore operation."""

    restore_id: str
    backup_id: str
    target_db_path: str
    executed_by: str
    executed_at: str
    reason: str
    idempotency_key: str
    audit_reference: str
    status: str  # RESTORE_APPROVED, RESTORE_VERIFIED, RESTORE_FAILED
    provenance: DisasterRecoveryProvenance = field(default_factory=DisasterRecoveryProvenance)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["provenance"] = self.provenance.to_dict()
        return d


def compute_file_sha256(filepath: str) -> tuple[str, int]:
    """Compute SHA-256 checksum and file size in bytes for a file."""
    if not os.path.exists(filepath):
        raise BackupIntegrityError(f"File '{filepath}' does not exist.")

    hasher = hashlib.sha256()
    size = 0
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
            size += len(chunk)
    return hasher.hexdigest(), size


def calculate_rpo_freshness(
    backup_timestamp_iso: str,
    current_time_iso: str | None = None,
    rpo_target_seconds: float = 3600.0,
) -> tuple[float, bool]:
    """Calculate backup age in seconds and verify if it satisfies the Recovery Point Objective (RPO).

    RPO Target Default: 3,600 seconds (1 hour).
    Returns (freshness_seconds, is_within_rpo_target).
    """
    try:
        b_dt = datetime.fromisoformat(backup_timestamp_iso.replace("Z", "+00:00"))
        if b_dt.tzinfo is None:
            b_dt = b_dt.replace(tzinfo=timezone.utc)

        if current_time_iso:
            c_dt = datetime.fromisoformat(current_time_iso.replace("Z", "+00:00"))
            if c_dt.tzinfo is None:
                c_dt = c_dt.replace(tzinfo=timezone.utc)
        else:
            c_dt = datetime.now(timezone.utc)

        freshness = max(0.0, (c_dt - b_dt).total_seconds())
        within_rpo = freshness <= rpo_target_seconds
        return freshness, within_rpo
    except Exception as e:
        raise BackupIntegrityError(f"Invalid backup timestamp format '{backup_timestamp_iso}': {e}")


def compute_disaster_recovery_idempotency_key(
    backup_id: str,
    executed_by: str,
    target_db_path: str,
) -> str:
    """Compute deterministic SHA-256 idempotency key for database restore operation."""
    raw = f"phase29_restore:{backup_id}:{executed_by}:{target_db_path}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
