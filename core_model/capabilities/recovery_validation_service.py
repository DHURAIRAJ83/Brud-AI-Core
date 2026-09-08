"""Phase 30 — Production Reliability, Recovery Validation & Operational Governance Domain Module.

Provides pure domain dataclasses, RPO status calculation, RTO status calculation,
backup lifecycle evaluation, operational readiness evaluation, and idempotency key computation.
Zero database, zero network, zero subprocess, zero autonomous execution.
"""

import hashlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


class RecoveryValidationError(Exception):
    """Base domain exception for Phase 30 Recovery Validation capabilities."""

    pass


class RecoveryDrillError(RecoveryValidationError):
    """Raised when a recovery drill fails or is misconfigured."""

    pass


@dataclass(frozen=True)
class RecoveryValidationProvenance:
    """Extended 16-step provenance chain for Phase 30 recovery validation and drill operations."""

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
    drill_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "RecoveryValidationProvenance":
        if not data:
            return cls()
        known_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_keys}
        return cls(**filtered)


@dataclass(frozen=True)
class RecoveryDrillRecord:
    """Domain model representing an isolated database recovery drill execution record."""

    drill_id: str
    backup_id: str
    drill_type: str  # SCHEDULED_DRILL, MANUAL_DRILL, PRE_DEPLOYMENT_DRILL
    started_at: str
    completed_at: str
    duration_seconds: float
    target_rto_seconds: float
    rto_status: str  # WITHIN_TARGET, AT_RISK, BREACHED
    backup_sha256: str
    restored_db_sha256: str
    integrity_status: str  # PASSED, FAILED
    schema_status: str  # PASSED, FAILED
    result: str  # PASS, FAIL
    executed_by: str
    audit_reference: str
    idempotency_key: str
    provenance: RecoveryValidationProvenance = field(default_factory=RecoveryValidationProvenance)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["provenance"] = self.provenance.to_dict()
        return d


@dataclass(frozen=True)
class OperationalReadinessReport:
    """Domain model representing a deterministic operational readiness evaluation."""

    evaluation_id: str
    readiness_status: str  # READY, READY_WITH_WARNINGS, NOT_READY
    latest_backup_freshness_seconds: float
    rpo_status: str  # WITHIN_TARGET, AT_RISK, BREACHED, NO_VERIFIED_BACKUP
    rto_status: str  # WITHIN_TARGET, AT_RISK, BREACHED, UNKNOWN
    latest_drill_result: str  # PASS, FAIL, NO_DRILL_EXECUTED
    active_locks_count: int
    evaluated_at: str
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_rpo_status(
    latest_backup_freshness_seconds: float | None,
    rpo_target_seconds: float = 3600.0,
) -> str:
    """Classify Recovery Point Objective (RPO) status based on backup freshness.

    Target Default: 3,600 seconds (1 hour).
    Statuses:
    - NO_VERIFIED_BACKUP if freshness is None or negative.
    - WITHIN_TARGET if freshness <= rpo_target_seconds.
    - AT_RISK if rpo_target_seconds < freshness <= (rpo_target_seconds * 1.5).
    - BREACHED if freshness > (rpo_target_seconds * 1.5).
    """
    if latest_backup_freshness_seconds is None or latest_backup_freshness_seconds < 0:
        return "NO_VERIFIED_BACKUP"

    if latest_backup_freshness_seconds <= rpo_target_seconds:
        return "WITHIN_TARGET"
    elif latest_backup_freshness_seconds <= (rpo_target_seconds * 1.5):
        return "AT_RISK"
    else:
        return "BREACHED"


def evaluate_rto_status(
    drill_duration_seconds: float | None,
    rto_target_seconds: float = 900.0,
) -> str:
    """Classify Recovery Time Objective (RTO) status based on recovery drill duration.

    Target Default: 900 seconds (15 minutes).
    Statuses:
    - UNKNOWN if drill_duration_seconds is None or negative.
    - WITHIN_TARGET if drill_duration_seconds <= rto_target_seconds.
    - AT_RISK if rto_target_seconds < drill_duration_seconds <= (rto_target_seconds * 1.25).
    - BREACHED if drill_duration_seconds > (rto_target_seconds * 1.25).
    """
    if drill_duration_seconds is None or drill_duration_seconds < 0:
        return "UNKNOWN"

    if drill_duration_seconds <= rto_target_seconds:
        return "WITHIN_TARGET"
    elif drill_duration_seconds <= (rto_target_seconds * 1.25):
        return "AT_RISK"
    else:
        return "BREACHED"


def evaluate_backup_lifecycle_state(
    created_at_iso: str,
    is_verified: bool,
    current_time_iso: str | None = None,
    aging_threshold_seconds: float = 86400.0,
    retention_threshold_seconds: float = 604800.0,
) -> str:
    """Evaluate non-autonomous backup lifecycle state.

    Lifecycle States:
    - CREATED: Fresh backup, verification pending.
    - VERIFIED: Validated checksum & integrity, age <= 1 day.
    - AVAILABLE: Active available backup state.
    - AGING: Backup age > aging_threshold_seconds (1 day).
    - RETENTION_ELIGIBLE: Backup age > retention_threshold_seconds (7 days).
    Note: Lifecycle evaluation MUST NOT execute automatic deletion.
    """
    if not is_verified:
        return "CREATED"

    try:
        b_dt = datetime.fromisoformat(created_at_iso.replace("Z", "+00:00"))
        if b_dt.tzinfo is None:
            b_dt = b_dt.replace(tzinfo=timezone.utc)

        if current_time_iso:
            c_dt = datetime.fromisoformat(current_time_iso.replace("Z", "+00:00"))
            if c_dt.tzinfo is None:
                c_dt = c_dt.replace(tzinfo=timezone.utc)
        else:
            c_dt = datetime.now(timezone.utc)

        age_seconds = max(0.0, (c_dt - b_dt).total_seconds())

        if age_seconds > retention_threshold_seconds:
            return "RETENTION_ELIGIBLE"
        elif age_seconds > aging_threshold_seconds:
            return "AGING"
        elif age_seconds > 3600.0:
            return "AVAILABLE"
        else:
            return "VERIFIED"
    except Exception:
        return "CREATED"


def compute_recovery_drill_idempotency_key(
    backup_id: str,
    executed_by: str,
    drill_type: str = "SCHEDULED_DRILL",
) -> str:
    """Compute deterministic SHA-256 idempotency key for recovery drill execution."""
    raw = f"phase30_drill:{backup_id}:{executed_by}:{drill_type}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
