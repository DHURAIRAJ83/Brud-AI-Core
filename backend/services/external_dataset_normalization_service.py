"""Phase 10 Step 6: normalization + raw evidence preservation.

Turns one connector's already-normalized `NormalizedDatasetMetadata`
into (a) the fields for an `external_dataset_candidates` row and (b)
safe, bounded, redacted raw evidence for an
`external_dataset_candidate_sources` row -- centrally, once, so no
individual connector duplicates bounding/redaction/checksum logic (see
docs/data_discovery/phase10_live_dataset_discovery_plan.md section 4).

Nothing here ever downloads a file, follows a link, executes any part
of a provider's response, or invents a field a connector could not
determine -- an unknown field stays `None`/empty rather than being
defaulted to a real-looking value. A single malformed/oversized raw
response degrades to a truncation placeholder rather than raising, so
one provider's bad payload can never abort the whole search session.
"""

from __future__ import annotations

import hashlib
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from backend.core.json_utils import JsonValidationError, dumps_json, redact_secrets
from core_model.data_discovery import MAX_RAW_METADATA_BYTES
from core_model.data_discovery.candidate_model import NormalizedDatasetMetadata
from core_model.data_discovery.deduplication import normalize_name

# Recency thresholds (Step 6's own derived field, not a scoring
# decision -- `core_model.data_discovery.scoring.score_recency`
# consumes this same `freshness_status`, it does not recompute it).
FRESHNESS_FRESH_DAYS = 90
FRESHNESS_AGING_DAYS = 365


def _normalize_unicode(value: str) -> str:
    """NFC-normalizes text so visually identical strings built from
    different combining-character sequences compare and store
    identically -- keeps `normalized_name` (and therefore
    deduplication) stable across providers that encode the same name
    differently."""

    return unicodedata.normalize("NFC", value)


def derive_freshness_status(last_modified_at: str | None) -> str:
    """Deterministic, timestamp-only classification -- never a
    popularity or download-count signal. An unparseable or missing
    timestamp honestly stays `"unknown"` rather than guessing."""

    if not last_modified_at:
        return "unknown"
    try:
        parsed = datetime.fromisoformat(last_modified_at.replace("Z", "+00:00"))
    except ValueError:
        return "unknown"
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    age_days = (datetime.now(UTC) - parsed).days
    if age_days < 0:
        return "unknown"
    if age_days <= FRESHNESS_FRESH_DAYS:
        return "fresh"
    if age_days <= FRESHNESS_AGING_DAYS:
        return "aging"
    return "stale"


@dataclass(frozen=True)
class BoundedRawEvidence:
    raw_metadata: dict[str, Any]
    checksum: str
    truncated: bool


def bound_and_redact_raw_metadata(
    raw_metadata: dict[str, Any], *, max_bytes: int = MAX_RAW_METADATA_BYTES
) -> BoundedRawEvidence:
    """Redacts anything secret-shaped, then bounds the result to
    `max_bytes`. A payload that still will not fit (or contains a
    value `dumps_json` cannot safely serialize, e.g. a non-compliant
    literal `NaN`/`Infinity` some providers emit) degrades to a small,
    auditable truncation placeholder instead of raising -- the
    candidate is still created, just without that provider's full raw
    evidence."""

    redacted = redact_secrets(raw_metadata)
    try:
        serialized = dumps_json(redacted, max_bytes=max_bytes)
    except (JsonValidationError, ValueError, TypeError):
        placeholder = {
            "_truncated": True,
            "_reason": "raw metadata exceeded the bounded size or contained a non-JSON-safe value",
            "_original_keys": sorted(str(key) for key in raw_metadata),
        }
        serialized = dumps_json(placeholder, max_bytes=max_bytes)
        checksum = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        return BoundedRawEvidence(raw_metadata=placeholder, checksum=checksum, truncated=True)
    checksum = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return BoundedRawEvidence(raw_metadata=redacted, checksum=checksum, truncated=False)


class ExternalDatasetNormalizationService:
    """Stateless: every method is a pure transformation from a
    connector's `NormalizedDatasetMetadata` to the dicts the Phase 10
    repository layer (`ExternalDatasetDiscoveryRepository`) expects.
    Never touches the database itself -- callers (Task #119's search
    execution service) own persistence and dedup/scoring integration."""

    @staticmethod
    def build_candidate_fields(metadata: NormalizedDatasetMetadata) -> dict[str, Any]:
        name = _normalize_unicode(metadata.name.strip()) if metadata.name else metadata.name
        description = _normalize_unicode(metadata.description) if metadata.description else ""
        return {
            "canonical_name": name,
            "normalized_name": normalize_name(name) if name else "",
            "modality": metadata.modality,
            "languages": list(metadata.languages),
            "tasks": list(metadata.tasks),
            "description": description,
            "organization": metadata.organization,
            "authors": list(metadata.authors),
            "tags": list(metadata.tags),
            "declared_licence": metadata.licence_declared,
            "licence_status": "declared" if metadata.licence_declared else "unknown",
            "record_count": metadata.record_count,
            "download_size_bytes": metadata.download_size_bytes,
            "file_formats": list(metadata.file_formats),
            "dataset_card_present": bool(metadata.dataset_card_url),
            "dataset_card_url": metadata.dataset_card_url,
            "homepage_url": metadata.homepage_url,
            "repository_url": metadata.repository_url,
            "gated": metadata.gated,
            "private": metadata.private,
            "authentication_required": metadata.requires_authentication,
            "version": metadata.version,
            "revision": metadata.revision,
            "last_modified_at": metadata.last_modified_at,
            "freshness_status": derive_freshness_status(metadata.last_modified_at),
            "candidate_entry_method": "provider_search",
        }

    @staticmethod
    def build_candidate_source_fields(
        metadata: NormalizedDatasetMetadata,
        *,
        provider_public_id: str,
        response_status: str = "success",
    ) -> dict[str, Any]:
        evidence = bound_and_redact_raw_metadata(metadata.raw_metadata)
        source_url = metadata.repository_url or metadata.homepage_url or metadata.dataset_card_url
        warnings = []
        if evidence.truncated:
            warnings.append("raw_metadata_truncated")
        return {
            "provider_public_id": provider_public_id,
            "provider_dataset_id": metadata.provider_dataset_id,
            "source_url": source_url,
            "dataset_card_url": metadata.dataset_card_url,
            "metadata_url": None,
            "version": metadata.version,
            "revision": metadata.revision,
            "raw_metadata": evidence.raw_metadata,
            "raw_metadata_checksum": evidence.checksum,
            "response_status": response_status,
            "warnings": warnings,
        }
