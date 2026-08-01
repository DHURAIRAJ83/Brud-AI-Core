"""Conservative, signal-based deduplication (Step 7). Two candidates
are only ever auto-merged when they share a *strong* signal (exact
provider dataset id re-seen, normalized organization+name, an
identical repository/homepage/dataset-card URL, or an identical
canonical identifier). Anything weaker -- similar titles, a shared name
with a different organization -- is never merged automatically; it is
either left as separate candidates or flagged
``possible_duplicate_group`` for human review. Every provider source is
preserved regardless of merge outcome (enforced by the repository/
service layer, not this module).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from core_model.data_discovery.candidate_model import NormalizedDatasetMetadata


@dataclass(frozen=True)
class DuplicateSignal:
    kind: str
    value: str


def _normalize_text(value: str) -> str:
    lowered = value.strip().lower()
    return re.sub(r"[\s_\-]+", " ", lowered).strip()


def normalize_name(value: str) -> str:
    """Public wrapper around `_normalize_text` -- the exact
    whitespace/case-insensitive form stored as a candidate's
    `normalized_name` column, so persisted data and this module's own
    duplicate-signal comparisons never drift apart."""

    return _normalize_text(value)


def _normalize_url(url: str) -> str:
    parts = urlsplit(url.strip().lower())
    path = parts.path.rstrip("/")
    return f"{parts.netloc}{path}"


def strong_signals(
    metadata: NormalizedDatasetMetadata, *, provider_code: str
) -> tuple[DuplicateSignal, ...]:
    signals: list[DuplicateSignal] = [
        DuplicateSignal("provider_dataset_id", f"{provider_code}:{metadata.provider_dataset_id}")
    ]
    if metadata.organization and metadata.name:
        org_name = f"{_normalize_text(metadata.organization)}::{_normalize_text(metadata.name)}"
        signals.append(DuplicateSignal("org_name", org_name))
    if metadata.repository_url:
        signals.append(DuplicateSignal("repository_url", _normalize_url(metadata.repository_url)))
    if metadata.homepage_url:
        signals.append(DuplicateSignal("homepage_url", _normalize_url(metadata.homepage_url)))
    if metadata.dataset_card_url:
        card_url = _normalize_url(metadata.dataset_card_url)
        signals.append(DuplicateSignal("dataset_card_url", card_url))
    return tuple(signals)


def cross_reference_signals(metadata: NormalizedDatasetMetadata) -> tuple[DuplicateSignal, ...]:
    """URLs one candidate declares that might point at *another*
    provider's own homepage/repository/card URL -- e.g. a GitHub repo
    whose homepage field is literally the Hugging Face dataset page.
    Compared against the target signals in `is_strong_duplicate`."""

    signals = []
    for url in (metadata.repository_url, metadata.homepage_url, metadata.dataset_card_url):
        if url:
            signals.append(DuplicateSignal("cross_reference_url", _normalize_url(url)))
    return tuple(signals)


def is_strong_duplicate(
    signals_a: tuple[DuplicateSignal, ...], signals_b: tuple[DuplicateSignal, ...]
) -> bool:
    set_a = {(s.kind, s.value) for s in signals_a if s.kind != "provider_dataset_id"}
    set_b = {(s.kind, s.value) for s in signals_b if s.kind != "provider_dataset_id"}
    if set_a & set_b:
        return True
    # provider_dataset_id only counts as a match when it is literally
    # the same string (already provider-scoped by construction).
    ids_a = {s.value for s in signals_a if s.kind == "provider_dataset_id"}
    ids_b = {s.value for s in signals_b if s.kind == "provider_dataset_id"}
    return bool(ids_a & ids_b)


def is_cross_referenced(
    signals_a: tuple[DuplicateSignal, ...], cross_refs_b: tuple[DuplicateSignal, ...]
) -> bool:
    """True when B explicitly links to one of A's own URLs (e.g. a
    GitHub mirror repo whose homepage is the original Hugging Face
    dataset page) -- a strong, deliberate signal, not a title guess."""

    url_kinds = ("repository_url", "homepage_url", "dataset_card_url")
    url_values_a = {s.value for s in signals_a if s.kind in url_kinds}
    cross_values_b = {s.value for s in cross_refs_b}
    return bool(url_values_a & cross_values_b)


def is_possible_duplicate(
    metadata_a: NormalizedDatasetMetadata, metadata_b: NormalizedDatasetMetadata
) -> bool:
    """A weak, non-merging signal: same normalized name, but not
    already caught by a strong signal (e.g. different organization, or
    no organization recorded at all) -- flagged for human review,
    never auto-merged, per rule 7's "if uncertain" instruction."""

    return _normalize_text(metadata_a.name) == _normalize_text(metadata_b.name)
