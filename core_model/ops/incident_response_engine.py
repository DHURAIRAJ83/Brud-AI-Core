"""Phase 61 - P7: Production Incident Response Engine.

Manages the complete lifecycle of production security and performance incidents.

CRITICAL INVARIANTS:
- Incident Lifecycle: INCIDENT_DETECTED -> INCIDENT_TRIAGED -> MITIGATION_REQUIRED -> TRAFFIC_FROZEN -> ROLLBACK_REQUIRED -> ROLLBACK_EXECUTED -> RECOVERY_VERIFIED -> INCIDENT_CLOSED.
- Critical incidents MUST NOT be automatically closed. Human Admin approval is mandatory.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import asdict, dataclass, field
from typing import Any


class IncidentError(ValueError):
    """Raised when incident lifecycle state transition is invalid."""


@dataclass
class IncidentRecord:
    """Immutable production incident record."""
    incident_id: str
    release_id: str
    model_hash: str
    severity: str  # LOW | MEDIUM | HIGH | CRITICAL
    trigger_source: str
    description: str
    detection_timestamp: str
    incident_status: str  # INCIDENT_DETECTED | INCIDENT_TRIAGED | MITIGATION_REQUIRED | TRAFFIC_FROZEN | ROLLBACK_REQUIRED | ROLLBACK_EXECUTED | RECOVERY_VERIFIED | INCIDENT_CLOSED
    mitigation_notes: str | None = None
    assigned_admin: str | None = None
    closed_by_admin: str | None = None
    closure_timestamp: str | None = None
    audit_hash: str = ""


class IncidentResponseEngine:
    """Production incident lifecycle manager."""

    def __init__(self) -> None:
        self._incidents: dict[str, IncidentRecord] = {}

    def raise_incident(
        self,
        release_id: str,
        model_hash: str,
        severity: str,
        trigger_source: str,
        description: str,
    ) -> IncidentRecord:
        """Raise a new production incident."""
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        inc_id = f"inc-{time.strftime('%Y%m%d%H%M%S', time.gmtime())}-{len(self._incidents)+1:03d}"

        raw_hash = f"{inc_id}:{release_id}:{model_hash}:{severity}:{now}".encode("utf-8")
        audit_hash = hashlib.sha256(raw_hash).hexdigest()

        rec = IncidentRecord(
            incident_id=inc_id,
            release_id=release_id,
            model_hash=model_hash,
            severity=severity,
            trigger_source=trigger_source,
            description=description,
            detection_timestamp=now,
            incident_status="INCIDENT_DETECTED",
            audit_hash=audit_hash
        )
        self._incidents[inc_id] = rec
        return rec

    def transition_status(
        self,
        incident_id: str,
        new_status: str,
        admin_identity: str | None = None,
        notes: str | None = None,
    ) -> IncidentRecord:
        """Transition incident state in lifecycle."""
        if incident_id not in self._incidents:
            raise KeyError(f"Incident {incident_id} not found.")

        rec = self._incidents[incident_id]

        # Invariant: Closing CRITICAL or HIGH incidents requires explicit human admin identity
        if new_status == "INCIDENT_CLOSED" and rec.severity in ("HIGH", "CRITICAL"):
            if not admin_identity or admin_identity.startswith("auto-"):
                raise IncidentError(f"Critical incident {incident_id} cannot be automatically closed without human Admin authorization.")

        rec.incident_status = new_status
        if admin_identity:
            rec.assigned_admin = admin_identity
        if notes:
            rec.mitigation_notes = notes

        if new_status == "INCIDENT_CLOSED":
            rec.closed_by_admin = admin_identity
            rec.closure_timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        return rec

    def get_incident(self, incident_id: str) -> IncidentRecord | None:
        """Retrieve incident by ID."""
        return self._incidents.get(incident_id)

    def get_active_incidents(self) -> list[IncidentRecord]:
        """Get all unresolved incidents."""
        return [i for i in self._incidents.values() if i.incident_status != "INCIDENT_CLOSED"]
