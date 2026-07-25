"""Phase 19 Tamil corpus builder API request schemas."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from backend.core.validation import DomainModel


class CorpusPolicyCreate(DomainModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=2000)
    supported_languages: list[str] = Field(default_factory=lambda: ["ta", "en", "tgl", "mixed"])
    allowed_source_types: list[str] = Field(default_factory=list)
    allowed_licence_statuses: list[str] = Field(
        default_factory=lambda: ["approved", "approved_with_conditions"]
    )
    require_verified_origin: bool = True
    require_licence_review: bool = True
    require_privacy_scan: bool = True
    require_safety_scan: bool = True
    require_quality_assessment: bool = True
    require_deduplication: bool = True
    require_contamination_check: bool = True
    maximum_source_bytes: int = Field(default=200_000_000, ge=1)
    maximum_document_characters: int = Field(default=2_000_000, ge=1)
    maximum_segment_characters: int = Field(default=8000, ge=1)
    minimum_segment_characters: int = Field(default=100, ge=1)
    default_retention_seconds: int = Field(default=31_536_000, ge=0)
    export_format_policy: dict[str, Any] = Field(default_factory=lambda: {"formats": ["jsonl"]})


class CorpusPolicyPatch(DomainModel):
    description: str | None = Field(default=None, max_length=2000)
    maximum_segment_characters: int | None = Field(default=None, ge=1)
    minimum_segment_characters: int | None = Field(default=None, ge=1)


class SourceRegistryCreate(DomainModel):
    corpus_policy_public_id: str
    title: str = Field(min_length=1, max_length=300)
    source_type: str = Field(min_length=1, max_length=40)
    author_or_organisation: str | None = Field(default=None, max_length=300)
    publisher: str | None = Field(default=None, max_length=300)
    original_publication_date: str | None = None
    source_reference: str = Field(default="", max_length=2000)
    language: str = Field(default="unknown", max_length=10)
    domain: str = Field(default="general", max_length=40)
    ownership_claim: str = Field(default="unknown", max_length=200)
    origin_reference_public_id: str | None = None
    intended_use: str = Field(default="pretraining_corpus", max_length=60)


class SourceRegistryPatch(DomainModel):
    title: str | None = Field(default=None, max_length=300)
    publisher: str | None = Field(default=None, max_length=300)
    source_reference: str | None = Field(default=None, max_length=2000)
    domain: str | None = Field(default=None, max_length=40)


class SourceLicenceCreate(DomainModel):
    licence_family: str = Field(min_length=1, max_length=60)
    licence_name: str | None = Field(default=None, max_length=200)
    licence_version: str | None = Field(default=None, max_length=40)
    licence_text_reference: str | None = Field(default=None, max_length=2000)
    copyright_holder: str | None = Field(default=None, max_length=300)
    allowed_uses: list[str] = Field(default_factory=list)
    prohibited_uses: list[str] = Field(default_factory=list)
    attribution_required: bool = False
    share_alike_required: bool = False
    commercial_use_permitted: bool = False
    modification_permitted: bool = False
    ai_training_permitted: bool = False
    redistribution_permitted: bool = False
    evidence_type: str = Field(default="admin_asserted", max_length=60)
    valid_from: str | None = None
    expires_at: str | None = None


class SourceLicencePatch(DomainModel):
    review_notes: str | None = Field(default=None, max_length=4000)
    expires_at: str | None = None


class LicenceReviewDecision(DomainModel):
    review_status: str = Field(min_length=1, max_length=40)
    review_notes: str = Field(default="", max_length=4000)


class SnapshotCreate(DomainModel):
    files: list[dict[str, Any]] = Field(default_factory=list)


class ExtractionRunCreate(DomainModel):
    extraction_method: str = Field(min_length=1, max_length=40)
    ocr_language_configuration: str = Field(default="tam+eng", max_length=40)


class NormalizationRunCreate(DomainModel):
    normalization_version: str = Field(default="v1", max_length=20)


class SegmentationRequest(DomainModel):
    strategy: str = Field(default="heading_section", max_length=40)


class QualityAssessRequest(DomainModel):
    subject_type: str = Field(default="segment", max_length=40)


class DeduplicationRunCreate(DomainModel):
    scope_description: str = Field(default="", max_length=2000)
    near_duplicate_method: str = Field(default="character_ngram_jaccard", max_length=40)
    near_duplicate_threshold: float = Field(default=0.85, ge=0, le=1)


class ContaminationRunCreate(DomainModel):
    scope_description: str = Field(default="", max_length=2000)
    test_fixture_texts: list[str] = Field(default_factory=list)
    validation_fixture_texts: list[str] = Field(default_factory=list)
    evaluation_fixture_texts: list[str] = Field(default_factory=list)
    regression_fixture_texts: list[str] = Field(default_factory=list)
    holdout_fixture_texts: list[str] = Field(default_factory=list)
    hidden_prompt_fixture_texts: list[str] = Field(default_factory=list)


class CollectionCreate(DomainModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=2000)
    intended_use: str = Field(default="pretraining_corpus", max_length=60)
    language_policy: dict[str, Any] = Field(default_factory=dict)
    domain_policy: dict[str, Any] = Field(default_factory=dict)
    style_policy: dict[str, Any] = Field(default_factory=dict)
    licence_policy: dict[str, Any] = Field(default_factory=dict)
    quality_policy: dict[str, Any] = Field(default_factory=dict)


class CollectionPatch(DomainModel):
    description: str | None = Field(default=None, max_length=2000)


class CollectionMemberCreate(DomainModel):
    segment_public_id: str


class BalancePolicyCreate(DomainModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=2000)
    language_targets: dict[str, Any] = Field(default_factory=dict)
    domain_targets: dict[str, Any] = Field(default_factory=dict)
    style_targets: dict[str, Any] = Field(default_factory=dict)
    source_type_targets: dict[str, Any] = Field(default_factory=dict)
    licence_family_targets: dict[str, Any] = Field(default_factory=dict)
    content_length_targets: dict[str, Any] = Field(default_factory=dict)
    quality_band_targets: dict[str, Any] = Field(default_factory=dict)
    maximum_single_source_share: float = Field(default=0.3, ge=0, le=1)


class BalancePolicyPatch(DomainModel):
    description: str | None = Field(default=None, max_length=2000)
    maximum_single_source_share: float | None = Field(default=None, ge=0, le=1)


class BuildCreate(DomainModel):
    corpus_policy_public_id: str
    balance_policy_public_id: str
    collection_public_ids: list[str] = Field(default_factory=list)
    deduplication_run_public_id: str | None = None
    contamination_run_public_id: str | None = None
    partition_configuration: dict[str, Any] = Field(
        default_factory=lambda: {"train": 0.98, "validation": 0.01, "test": 0.01, "seed": 42}
    )
    export_policy: dict[str, Any] = Field(default_factory=dict)


class VersionCreate(DomainModel):
    semantic_version: str = Field(min_length=1, max_length=40)


class ExportCreate(DomainModel):
    export_format: str = Field(default="jsonl", max_length=40)
    shard_max_bytes: int = Field(default=50_000_000, ge=1)


class CorpusCompareRequest(DomainModel):
    left_version_public_id: str
    right_version_public_id: str
