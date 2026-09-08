"""Phase 61 - P6: Production Release Registry.

Provides an immutable production release registry for tracking approved production models.

CRITICAL INVARIANTS:
- Distinct registry from CandidateModelRegistry.
- Never overwrites historical production release metadata.
- Production release success alone does NOT grant public chat eligibility (public_chat_eligible = FALSE by default).
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ProductionReleaseRecord:
    """Metadata record for approved production model releases."""
    release_id: str
    candidate_model_id: str
    candidate_model_hash: str
    base_model_hash: str
    dataset_version: str
    dataset_hash: str
    tokenizer_hash: str
    training_config_hash: str
    evaluation_manifest_hash: str
    promotion_authorization_hash: str
    approving_admin_identity: str
    approval_timestamp: str
    release_timestamp: str
    previous_production_release_id: str | None
    release_status: str  # ATOMIC_RELEASE_PREPARED | ATOMIC_PROMOTION | POST_PROMOTION_VERIFICATION | PRODUCTION_ACTIVE | ROLLED_BACK | QUARANTINED
    rollback_status: str  # ROLLBACK_READY | ROLLBACK_EXECUTED | NONE
    public_chat_status: str = "BLOCKED"  # BLOCKED | ADMITTED
    notes: str | None = None


class ProductionReleaseRegistry:
    """Immutable production release registry."""

    def __init__(self) -> None:
        self._releases: dict[str, ProductionReleaseRecord] = {}
        self._active_release_id: str | None = None

    def register_release(
        self,
        release_id: str,
        candidate_model_id: str,
        candidate_model_hash: str,
        base_model_hash: str,
        dataset_version: str,
        dataset_hash: str,
        tokenizer_hash: str,
        training_config_hash: str,
        evaluation_manifest_hash: str,
        promotion_authorization_hash: str,
        approving_admin_identity: str,
        previous_production_release_id: str | None = None,
    ) -> ProductionReleaseRecord:
        """Register a new production release candidate record."""
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        record = ProductionReleaseRecord(
            release_id=release_id,
            candidate_model_id=candidate_model_id,
            candidate_model_hash=candidate_model_hash,
            base_model_hash=base_model_hash,
            dataset_version=dataset_version,
            dataset_hash=dataset_hash,
            tokenizer_hash=tokenizer_hash,
            training_config_hash=training_config_hash,
            evaluation_manifest_hash=evaluation_manifest_hash,
            promotion_authorization_hash=promotion_authorization_hash,
            approving_admin_identity=approving_admin_identity,
            approval_timestamp=now,
            release_timestamp=now,
            previous_production_release_id=previous_production_release_id,
            release_status="ATOMIC_RELEASE_PREPARED",
            rollback_status="NONE",
            public_chat_status="BLOCKED"
        )
        self._releases[release_id] = record
        return record

    def set_active_release(self, release_id: str) -> None:
        """Set active production release."""
        if release_id not in self._releases:
            raise KeyError(f"Release {release_id} not registered.")

        # Update state of active release
        self._active_release_id = release_id
        self._releases[release_id].release_status = "PRODUCTION_ACTIVE"

    def mark_rollback(self, release_id: str, previous_release_id: str | None) -> None:
        """Mark release as rolled back and restore previous active release."""
        if release_id in self._releases:
            self._releases[release_id].release_status = "ROLLED_BACK"
            self._releases[release_id].rollback_status = "ROLLBACK_EXECUTED"

        if previous_release_id and previous_release_id in self._releases:
            self._active_release_id = previous_release_id
            self._releases[previous_release_id].release_status = "PRODUCTION_ACTIVE"
        else:
            self._active_release_id = None

    def get_active_release(self) -> ProductionReleaseRecord | None:
        """Retrieve currently active production release."""
        if self._active_release_id:
            return self._releases.get(self._active_release_id)
        return None

    def get_release(self, release_id: str) -> ProductionReleaseRecord | None:
        """Retrieve release record by ID."""
        return self._releases.get(release_id)
