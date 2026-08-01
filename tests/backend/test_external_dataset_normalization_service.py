from datetime import UTC, datetime, timedelta

from backend.services.external_dataset_normalization_service import (
    ExternalDatasetNormalizationService,
    bound_and_redact_raw_metadata,
    derive_freshness_status,
)
from core_model.data_discovery import MAX_RAW_METADATA_BYTES
from core_model.data_discovery.candidate_model import NormalizedDatasetMetadata

PROVIDER_ID = "11111111-1111-1111-1111-111111111111"


def test_derive_freshness_status_buckets() -> None:
    now = datetime.now(UTC)
    fresh = (now - timedelta(days=10)).isoformat()
    aging = (now - timedelta(days=200)).isoformat()
    stale = (now - timedelta(days=800)).isoformat()
    assert derive_freshness_status(fresh) == "fresh"
    assert derive_freshness_status(aging) == "aging"
    assert derive_freshness_status(stale) == "stale"
    assert derive_freshness_status(None) == "unknown"
    assert derive_freshness_status("not-a-date") == "unknown"


def test_derive_freshness_status_handles_zulu_suffix() -> None:
    now = datetime.now(UTC)
    timestamp = (now - timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert derive_freshness_status(timestamp) == "fresh"


def test_bound_and_redact_raw_metadata_redacts_secret_shaped_keys() -> None:
    raw = {"downloads": 100, "auth_token": "super-secret-value"}
    evidence = bound_and_redact_raw_metadata(raw)
    assert evidence.raw_metadata["auth_token"] == "[REDACTED]"
    assert evidence.raw_metadata["downloads"] == 100
    assert evidence.truncated is False
    assert len(evidence.checksum) == 64


def test_bound_and_redact_raw_metadata_truncates_oversized_payload() -> None:
    raw = {"description": "x" * (MAX_RAW_METADATA_BYTES * 2)}
    evidence = bound_and_redact_raw_metadata(raw)
    assert evidence.truncated is True
    assert evidence.raw_metadata["_truncated"] is True
    assert "description" in evidence.raw_metadata["_original_keys"]


def test_bound_and_redact_raw_metadata_never_raises_on_unserializable_value() -> None:
    raw = {"score": float("nan")}
    evidence = bound_and_redact_raw_metadata(raw)
    assert evidence.truncated is True
    assert evidence.raw_metadata["_truncated"] is True


def test_build_candidate_fields_maps_known_data_and_preserves_unknowns() -> None:
    metadata = NormalizedDatasetMetadata(
        provider_dataset_id="org/tamil-asr",
        name="Tamil ASR Corpus",
        description="Speech transcripts",
        organization="org",
        tags=("asr", "tamil"),
        dataset_card_url="https://huggingface.co/datasets/org/tamil-asr",
        licence_declared="cc-by-4.0",
        record_count=1000,
        gated=False,
    )
    fields = ExternalDatasetNormalizationService.build_candidate_fields(metadata)
    assert fields["canonical_name"] == "Tamil ASR Corpus"
    assert fields["normalized_name"] == "tamil asr corpus"
    assert fields["declared_licence"] == "cc-by-4.0"
    assert fields["licence_status"] == "declared"
    assert fields["dataset_card_present"] is True
    assert fields["record_count"] == 1000
    assert fields["candidate_entry_method"] == "provider_search"
    # Fields the connector could not determine stay honestly empty/None.
    assert fields["modality"] is None
    assert fields["languages"] == []
    assert fields["organization"] == "org"


def test_build_candidate_fields_licence_status_unknown_when_undeclared() -> None:
    metadata = NormalizedDatasetMetadata(provider_dataset_id="x", name="X")
    fields = ExternalDatasetNormalizationService.build_candidate_fields(metadata)
    assert fields["declared_licence"] is None
    assert fields["licence_status"] == "unknown"


def test_build_candidate_source_fields_prefers_repository_then_homepage_then_card() -> None:
    metadata = NormalizedDatasetMetadata(
        provider_dataset_id="org/x",
        name="X",
        homepage_url="https://example.org/home",
        dataset_card_url="https://example.org/card",
        raw_metadata={"downloads": 5},
    )
    fields = ExternalDatasetNormalizationService.build_candidate_source_fields(
        metadata, provider_public_id=PROVIDER_ID
    )
    assert fields["source_url"] == "https://example.org/home"
    assert fields["provider_public_id"] == PROVIDER_ID
    assert fields["raw_metadata"] == {"downloads": 5}
    assert fields["warnings"] == []


def test_build_candidate_source_fields_flags_truncation_warning() -> None:
    metadata = NormalizedDatasetMetadata(
        provider_dataset_id="org/x",
        name="X",
        raw_metadata={"description": "x" * (MAX_RAW_METADATA_BYTES * 2)},
    )
    fields = ExternalDatasetNormalizationService.build_candidate_source_fields(
        metadata, provider_public_id=PROVIDER_ID
    )
    assert fields["warnings"] == ["raw_metadata_truncated"]
