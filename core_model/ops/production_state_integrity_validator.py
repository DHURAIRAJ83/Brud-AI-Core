"""Phase 61 - P8: Production State Integrity Validator.

Cross-validates consistency across release registry, observability, audit chain, and snapshots.

CRITICAL INVARIANTS:
- Outcomes: STATE_INTEGRITY_VALID | STATE_INTEGRITY_FAILURE | UNKNOWN.
- Unknown or unverifiable evidence strictly fails closed to STATE_INTEGRITY_FAILURE.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core_model.eval.production_release_registry import ProductionReleaseRecord, ProductionReleaseRegistry
from core_model.ops.production_audit_chain import ProductionAuditChain
from core_model.ops.production_state_snapshot_registry import ProductionStateSnapshotRecord, ProductionStateSnapshotRegistry


@dataclass
class StateIntegrityValidationResult:
    """Outcome of production state cross-validation."""
    integrity_status: str  # STATE_INTEGRITY_VALID | STATE_INTEGRITY_FAILURE | UNKNOWN
    active_release_id: str | None
    model_hash_match: bool
    dataset_hash_match: bool
    tokenizer_hash_match: bool
    audit_chain_valid: bool
    discrepancies: list[str] = field(default_factory=list)


class ProductionStateIntegrityValidator:
    """Cross-validates system integrity across canonical state registries."""

    def validate_system_integrity(
        self,
        release_registry: ProductionReleaseRegistry | None,
        snapshot_registry: ProductionStateSnapshotRegistry | None,
        audit_chain: ProductionAuditChain | None,
        mock_hash_mismatch: bool = False,
    ) -> StateIntegrityValidationResult:
        """Cross-validate component consistency across production registries."""
        discrepancies: list[str] = []

        if not release_registry or not snapshot_registry or not audit_chain:
            return StateIntegrityValidationResult(
                integrity_status="STATE_INTEGRITY_FAILURE",
                active_release_id=None,
                model_hash_match=False,
                dataset_hash_match=False,
                tokenizer_hash_match=False,
                audit_chain_valid=False,
                discrepancies=["Fail-Closed: Missing one or more required state registries."]
            )

        # 1. Audit Chain integrity check
        try:
            audit_valid = audit_chain.verify_chain_integrity()
        except Exception as err:
            audit_valid = False
            discrepancies.append(f"Audit Chain Error: {err}")

        if not audit_valid:
            discrepancies.append("Audit Chain integrity check failed.")

        # 2. Release & Snapshot hash binding check
        active_rel = release_registry.get_active_release()
        latest_snap = snapshot_registry.get_latest_snapshot()

        if active_rel is None or latest_snap is None or mock_hash_mismatch:
            if active_rel is None:
                discrepancies.append("Active release record missing.")
            if latest_snap is None:
                discrepancies.append("Latest snapshot record missing.")
            if mock_hash_mismatch:
                discrepancies.append("Simulated artifact hash mismatch between active release and snapshot.")

            return StateIntegrityValidationResult(
                integrity_status="STATE_INTEGRITY_FAILURE",
                active_release_id=active_rel.release_id if active_rel else None,
                model_hash_match=False,
                dataset_hash_match=False,
                tokenizer_hash_match=False,
                audit_chain_valid=audit_valid,
                discrepancies=discrepancies
            )

        model_match = active_rel.candidate_model_hash == latest_snap.model_hash
        dataset_match = active_rel.dataset_hash == latest_snap.dataset_hash
        tokenizer_match = active_rel.tokenizer_hash == latest_snap.tokenizer_hash

        if not model_match:
            discrepancies.append(f"Model hash mismatch: release '{active_rel.candidate_model_hash}' vs snap '{latest_snap.model_hash}'.")
        if not dataset_match:
            discrepancies.append(f"Dataset hash mismatch: release '{active_rel.dataset_hash}' vs snap '{latest_snap.dataset_hash}'.")
        if not tokenizer_match:
            discrepancies.append(f"Tokenizer hash mismatch: release '{active_rel.tokenizer_hash}' vs snap '{latest_snap.tokenizer_hash}'.")

        all_valid = audit_valid and model_match and dataset_match and tokenizer_match
        status = "STATE_INTEGRITY_VALID" if all_valid else "STATE_INTEGRITY_FAILURE"

        return StateIntegrityValidationResult(
            integrity_status=status,
            active_release_id=active_rel.release_id,
            model_hash_match=model_match,
            dataset_hash_match=dataset_match,
            tokenizer_hash_match=tokenizer_match,
            audit_chain_valid=audit_valid,
            discrepancies=discrepancies
        )
