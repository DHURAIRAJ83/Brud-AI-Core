"""Phase 10 Step 7 (service-layer integration): decides whether a
newly discovered dataset should merge into an existing candidate in
the same search session, be flagged as a possible (non-merged)
duplicate for human review, or become an entirely new candidate.

The merge/flag decision logic itself is the pure, independently tested
`core_model.data_discovery.deduplication` module -- this service only
supplies the DB reads that module has no business knowing about. It is
deliberately conservative: when no strong signal is found, it creates
a new candidate rather than guessing a merge (Step 7's own
instruction), and every provider source is preserved regardless of the
outcome (a merge only ever adds a source row to the target candidate,
never discards one -- see
`ExternalDatasetNormalizationService.build_candidate_source_fields`).
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.database.repositories.external_dataset_discovery import (
    ExternalDatasetDiscoveryRepository,
)
from core_model.data_discovery.candidate_model import NormalizedDatasetMetadata
from core_model.data_discovery.deduplication import (
    cross_reference_signals,
    is_cross_referenced,
    is_possible_duplicate,
    is_strong_duplicate,
    strong_signals,
)

# Used only when re-deriving `strong_signals` for an *existing
# candidate's own aggregate row* (as opposed to one specific provider
# source) -- structurally distinct from any real provider code, so the
# provider_dataset_id branch of `is_strong_duplicate` can never
# accidentally collide with a real incoming id.
_AGGREGATE_SENTINEL_PROVIDER_CODE = "__candidate_aggregate__"


@dataclass(frozen=True)
class DeduplicationDecision:
    action: str  # "merge_exact_source" | "merge_strong_signal" | "possible_duplicate" | "new"
    target_candidate_public_id: str | None
    reason: str


def _candidate_as_metadata(candidate: dict) -> NormalizedDatasetMetadata:
    """Re-derives a comparable `NormalizedDatasetMetadata` from an
    already-persisted candidate row's own denormalized identity fields
    -- never from a specific provider source, since a merged candidate
    can carry sources from several providers with different ids."""

    return NormalizedDatasetMetadata(
        provider_dataset_id="",
        name=candidate["canonical_name"],
        organization=candidate["organization"],
        repository_url=candidate["repository_url"],
        homepage_url=candidate["homepage_url"],
        dataset_card_url=candidate["dataset_card_url"],
    )


class ExternalDatasetDeduplicationService:
    def __init__(self, discovery_repository: ExternalDatasetDiscoveryRepository) -> None:
        self._repository = discovery_repository

    def resolve(
        self,
        *,
        session_public_id: str,
        provider_public_id: str,
        provider_code: str,
        metadata: NormalizedDatasetMetadata,
    ) -> DeduplicationDecision:
        existing_candidates = self._repository.list_candidates(
            session_public_id, include_excluded=True
        )

        # Step A: the same provider already reported this exact
        # dataset id (e.g. a re-run of the same search) -- always
        # merges, never a guess.
        for candidate in existing_candidates:
            for source in self._repository.list_candidate_sources(candidate["public_id"]):
                if (
                    source["provider_public_id"] == provider_public_id
                    and source["provider_dataset_id"] == metadata.provider_dataset_id
                ):
                    return DeduplicationDecision(
                        action="merge_exact_source",
                        target_candidate_public_id=candidate["public_id"],
                        reason="same provider already reported this exact dataset id",
                    )

        new_signals = strong_signals(metadata, provider_code=provider_code)
        new_cross_refs = cross_reference_signals(metadata)

        # Step B: a strong signal (matching organization+name, or an
        # identical declared repository/homepage/dataset-card URL)
        # shared with a *different* provider's already-recorded
        # candidate.
        for candidate in existing_candidates:
            candidate_metadata = _candidate_as_metadata(candidate)
            candidate_signals = strong_signals(
                candidate_metadata, provider_code=_AGGREGATE_SENTINEL_PROVIDER_CODE
            )
            if is_strong_duplicate(new_signals, candidate_signals):
                return DeduplicationDecision(
                    action="merge_strong_signal",
                    target_candidate_public_id=candidate["public_id"],
                    reason="matching organization+name or an identical declared URL",
                )
            candidate_cross_refs = cross_reference_signals(candidate_metadata)
            if is_cross_referenced(new_signals, candidate_cross_refs) or is_cross_referenced(
                candidate_signals, new_cross_refs
            ):
                return DeduplicationDecision(
                    action="merge_strong_signal",
                    target_candidate_public_id=candidate["public_id"],
                    reason="one candidate's URL cross-references the other's own URL",
                )

        # Step C: a weak signal (same normalized name only) -- never
        # auto-merged, only flagged for human review.
        for candidate in existing_candidates:
            candidate_metadata = _candidate_as_metadata(candidate)
            if is_possible_duplicate(metadata, candidate_metadata):
                return DeduplicationDecision(
                    action="possible_duplicate",
                    target_candidate_public_id=candidate["public_id"],
                    reason="same normalized name, but no strong signal -- flagged for review",
                )

        return DeduplicationDecision(
            action="new", target_candidate_public_id=None, reason="no matching signal found"
        )
