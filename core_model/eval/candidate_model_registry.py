"""Phase 61 - P5: Candidate Model Registry & State Machine.

Provides tracking and governance state transitions for trained candidate models.

CRITICAL INVARIANTS:
- Candidate models remain TRAINED_CANDIDATE or UNDER_EVALUATION until certified.
- Production state remains separate from candidate state.
- Traffic share remains 0.0 and public chat remains FALSE by default.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class CandidateModelRecord:
    """Metadata record for trained candidate models."""
    candidate_model_id: str
    base_model_id: str
    dataset_version: str
    dataset_hash: str
    tokenizer_hash: str
    training_config_hash: str
    base_model_hash: str
    candidate_model_hash: str
    training_run_id: str
    creation_timestamp: str
    evaluation_status: str  # TRAINED_CANDIDATE | UNDER_EVALUATION | RED_TEAM_REQUIRED | EVALUATION_PASSED | REJECTED | QUARANTINED
    promotion_status: str   # PROMOTION_BLOCKED | PROMOTION_PENDING | PROMOTION_APPROVED | REJECTED
    is_production: bool = False  # ALWAYS FALSE UNLESS AUTHORIZED PROMOTION COMPLETED
    public_chat_eligible: bool = False  # ALWAYS FALSE IN P5
    candidate_traffic_share: float = 0.0  # ALWAYS 0.0 IN P5
    notes: str | None = None


class CandidateModelRegistry:
    """Registry managing candidate model records and state transitions."""

    def __init__(self) -> None:
        self._records: dict[str, CandidateModelRecord] = {}

    def register_candidate_model(
        self,
        candidate_model_id: str,
        base_model_id: str,
        dataset_version: str,
        dataset_hash: str,
        tokenizer_hash: str,
        training_config_hash: str,
        base_model_hash: str,
        candidate_model_hash: str,
        training_run_id: str,
    ) -> CandidateModelRecord:
        """Register a newly trained candidate model."""
        record = CandidateModelRecord(
            candidate_model_id=candidate_model_id,
            base_model_id=base_model_id,
            dataset_version=dataset_version,
            dataset_hash=dataset_hash,
            tokenizer_hash=tokenizer_hash,
            training_config_hash=training_config_hash,
            base_model_hash=base_model_hash,
            candidate_model_hash=candidate_model_hash,
            training_run_id=training_run_id,
            creation_timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            evaluation_status="TRAINED_CANDIDATE",
            promotion_status="PROMOTION_BLOCKED",
            is_production=False,
            public_chat_eligible=False,
            candidate_traffic_share=0.0
        )
        self._records[candidate_model_id] = record
        return record

    def update_evaluation_status(
        self,
        candidate_model_id: str,
        status: str,
        notes: str | None = None,
    ) -> CandidateModelRecord:
        """Update candidate model evaluation status."""
        if candidate_model_id not in self._records:
            raise KeyError(f"Candidate model {candidate_model_id} not registered.")

        rec = self._records[candidate_model_id]
        rec.evaluation_status = status
        if notes:
            rec.notes = notes
        return rec

    def update_promotion_status(
        self,
        candidate_model_id: str,
        status: str,
        notes: str | None = None,
    ) -> CandidateModelRecord:
        """Update candidate model promotion status."""
        if candidate_model_id not in self._records:
            raise KeyError(f"Candidate model {candidate_model_id} not registered.")

        rec = self._records[candidate_model_id]
        rec.promotion_status = status
        if notes:
            rec.notes = notes
        return rec

    def get_candidate(self, candidate_model_id: str) -> CandidateModelRecord | None:
        """Retrieve candidate model record by ID."""
        return self._records.get(candidate_model_id)
