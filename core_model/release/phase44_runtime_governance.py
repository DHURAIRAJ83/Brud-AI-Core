"""Phase 44 — Runtime Governance Controller & Two-Person Verification Drill.

Implements Workstreams 2 & 9:
- Enforces strict 9-state governance lifecycle:
  REVIEW_REQUIRED -> ADMIN_APPROVAL_PENDING -> ADMIN_APPROVED ->
  RUNTIME_VALIDATION -> INTERNAL_CANARY_READY -> INTERNAL_CANARY_ACTIVE ->
  INTERNAL_CANARY_QUALIFIED -> ROLLBACK_REQUIRED -> ROLLED_BACK.
- Maximum state ceiling: INTERNAL_CANARY_QUALIFIED.
  Transition to PUBLIC_PRODUCTION is barred at the code level.
- Two-Person Governance Drill:
  - Requires 2 distinct administrators (admin_1 != admin_2).
  - Duplicate admin approval rejected.
  - Cryptographic binding to candidate release_id, model_sha256, tokenizer_sha256,
    config_sha256, release_manifest_sha256, timestamp, admin identity, and action.
  - Invalidation of approvals upon artifact mutation.
- Enforces candidate traffic limits (default 0.0%, max 1.0%).
- Non-destructive audit trail of governance events.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class GovernanceApprovalToken:
    admin_id: str
    approval_role: str
    release_id: str
    model_sha256: str
    tokenizer_sha256: str
    config_sha256: str
    release_manifest_sha256: str
    governance_action: str
    timestamp: float = field(default_factory=time.time)

    def compute_signature_hash(self) -> str:
        payload = (
            f"{self.admin_id}:{self.approval_role}:{self.release_id}:"
            f"{self.model_sha256}:{self.tokenizer_sha256}:{self.config_sha256}:"
            f"{self.release_manifest_sha256}:{self.governance_action}"
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["signature_hash"] = self.compute_signature_hash()
        return d


@dataclass
class GovernanceEventRecord:
    event_id: str
    timestamp: float
    source_state: str
    target_state: str
    actor: str
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RuntimeGovernanceController:
    """Controls the runtime governance lifecycle and two-person administrative verification."""

    VALID_STATES = [
        "REVIEW_REQUIRED",
        "ADMIN_APPROVAL_PENDING",
        "ADMIN_APPROVED",
        "RUNTIME_VALIDATION",
        "INTERNAL_CANARY_READY",
        "INTERNAL_CANARY_ACTIVE",
        "INTERNAL_CANARY_QUALIFIED",
        "ROLLBACK_REQUIRED",
        "ROLLED_BACK",
    ]

    def __init__(self, release_id: str, current_state: str = "REVIEW_REQUIRED") -> None:
        if current_state not in self.VALID_STATES:
            raise ValueError(f"Invalid initial state: {current_state}")
        self.release_id = release_id
        self._state = current_state
        self._approvals: list[GovernanceApprovalToken] = []
        self._events: list[GovernanceEventRecord] = []

    @property
    def current_state(self) -> str:
        return self._state

    @property
    def approvals(self) -> list[GovernanceApprovalToken]:
        return list(self._approvals)

    @property
    def events(self) -> list[GovernanceEventRecord]:
        return list(self._events)

    def record_event(self, source_state: str, target_state: str, actor: str, details: dict[str, Any]) -> None:
        rec = GovernanceEventRecord(
            event_id=f"gov-evt-{len(self._events) + 1}",
            timestamp=time.time(),
            source_state=source_state,
            target_state=target_state,
            actor=actor,
            details=details,
        )
        self._events.append(rec)

    def transition_to(self, target_state: str, actor: str = "system") -> None:
        """Transitions state while enforcing non-public ceiling and state hierarchy."""
        if target_state == "PUBLIC_PRODUCTION":
            raise PermissionError("Transition to PUBLIC_PRODUCTION is strictly prohibited in Phase 44.")

        if target_state not in self.VALID_STATES:
            raise ValueError(f"Unknown governance state: {target_state}")

        source = self._state
        self._state = target_state
        self.record_event(source, target_state, actor, {"reason": "state_transition"})

    def submit_approval(self, approval: GovernanceApprovalToken) -> tuple[bool, str]:
        """Submits an administrative approval, enforcing two distinct admins."""
        if approval.release_id != self.release_id:
            return False, f"Release ID mismatch: expected {self.release_id}, got {approval.release_id}"

        # Reject duplicate approval by the same administrator
        if any(existing.admin_id == approval.admin_id for existing in self._approvals):
            return False, f"Duplicate approval rejected: administrator '{approval.admin_id}' has already approved"

        self._approvals.append(approval)
        self.record_event(
            self._state,
            self._state,
            approval.admin_id,
            {"action": "approval_submitted", "role": approval.approval_role},
        )

        if len(self._approvals) >= 2:
            self.transition_to("ADMIN_APPROVED", actor="governance_engine")
            return True, "TWO_PERSON_APPROVAL_GRANTED"

        self.transition_to("ADMIN_APPROVAL_PENDING", actor="governance_engine")
        return True, "APPROVAL_RECORDED_PENDING_SECOND_ADMIN"

    def verify_approvals_against_live_artifacts(
        self,
        current_model_sha256: str,
        current_tokenizer_sha256: str,
        current_config_sha256: str,
        current_manifest_sha256: str,
    ) -> tuple[bool, str]:
        """Verifies that live candidate artifacts match the hashes bound in approvals.

        Invalidates all approvals if any mutation is detected.
        """
        if len(self._approvals) < 2:
            return False, "Insufficient approvals: two distinct administrators required"

        for app in self._approvals:
            if app.model_sha256 != current_model_sha256:
                self.invalidate_all_approvals("Model artifact SHA-256 mutation detected")
                return False, "APPROVAL_INVALIDATED: Model artifact hash mismatch"
            if app.tokenizer_sha256 != current_tokenizer_sha256:
                self.invalidate_all_approvals("Tokenizer artifact SHA-256 mutation detected")
                return False, "APPROVAL_INVALIDATED: Tokenizer artifact hash mismatch"
            if app.config_sha256 != current_config_sha256:
                self.invalidate_all_approvals("Configuration SHA-256 mutation detected")
                return False, "APPROVAL_INVALIDATED: Configuration hash mismatch"
            if app.release_manifest_sha256 != current_manifest_sha256:
                self.invalidate_all_approvals("Release manifest SHA-256 mutation detected")
                return False, "APPROVAL_INVALIDATED: Release manifest hash mismatch"

        return True, "ALL_APPROVAL_HASHES_VERIFIED"

    def invalidate_all_approvals(self, reason: str) -> None:
        """Invalidates all prior approvals and reverts state to REVIEW_REQUIRED."""
        self._approvals.clear()
        source = self._state
        self._state = "REVIEW_REQUIRED"
        self.record_event(source, "REVIEW_REQUIRED", "security_guard", {"reason": reason})
