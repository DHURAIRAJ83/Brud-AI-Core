"""Request/response models for the Phase 2 Source, Rights & Usage Registry."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from backend.core.validation import DomainModel

SourceType = Literal[
    "human_created",
    "admin_created",
    "teacher_created",
    "institution_created",
    "document_derived",
    "government_source",
    "public_domain",
    "open_dataset",
    "licensed_dataset",
    "permission_granted",
    "user_contributed",
    "ai_assisted",
    "ai_generated",
    "web_source",
    "unknown",
]

SourceStatus = Literal["draft", "needs_review", "verified", "restricted", "rejected", "archived"]

RiskLevel = Literal["low", "medium", "high", "unknown"]

RightsStatus = Literal[
    "unknown",
    "pending_review",
    "public_domain",
    "open_license",
    "licensed",
    "permission_granted",
    "internal_only",
    "restricted",
    "prohibited",
    "expired",
]

VerificationStatus = Literal[
    "unverified",
    "self_declared",
    "document_verified",
    "owner_confirmed",
    "legal_reviewed",
    "rejected",
]

VerificationAction = Literal[
    "self_declare",
    "document_verify",
    "owner_confirm",
    "legal_review",
    "reject",
    "expire",
    "restrict",
]

TargetUse = Literal[
    "rag", "training", "evaluation", "commercial", "public_export", "redistribution"
]

EntityType = Literal[
    "dataset_record",
    "dataset_source",
    "dataset_version",
    "import_job",
    "document",
    "document_page",
    "corpus_source_registry",
    "corpus_item",
    "chunk",
    "rag_knowledge_source",
    "rag_item",
    "evaluation_case",
]

RelationshipType = Literal[
    "primary_source",
    "supporting_source",
    "derived_from",
    "verified_against",
    "translated_from",
    "generated_from",
]


class DataSourceCreate(DomainModel):
    source_code: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=300)
    source_type: SourceType
    owner_name: str | None = Field(default=None, max_length=200)
    author_name: str | None = Field(default=None, max_length=200)
    publisher_name: str | None = Field(default=None, max_length=200)
    organization_name: str | None = Field(default=None, max_length=200)
    source_url: str | None = Field(default=None, max_length=2000)
    source_reference: str | None = Field(default=None, max_length=2000)
    publication_year: int | None = Field(default=None, ge=0, le=9999)
    edition: str | None = Field(default=None, max_length=100)
    language_codes: list[str] = Field(default_factory=list)
    description: str = Field(default="", max_length=4000)
    knowledge_risk: RiskLevel = "unknown"
    fact_dependency: RiskLevel = "unknown"
    verification_required: bool = False
    independent_reviewer_required: bool = False
    internal_rag_policy_allows_unknown_rights: bool = False
    acquired_at: str | None = None


class DataSourcePatch(DomainModel):
    title: str | None = Field(default=None, max_length=300)
    owner_name: str | None = Field(default=None, max_length=200)
    author_name: str | None = Field(default=None, max_length=200)
    publisher_name: str | None = Field(default=None, max_length=200)
    organization_name: str | None = Field(default=None, max_length=200)
    source_url: str | None = Field(default=None, max_length=2000)
    source_reference: str | None = Field(default=None, max_length=2000)
    publication_year: int | None = Field(default=None, ge=0, le=9999)
    edition: str | None = Field(default=None, max_length=100)
    language_codes: list[str] | None = None
    description: str | None = Field(default=None, max_length=4000)
    knowledge_risk: RiskLevel | None = None
    fact_dependency: RiskLevel | None = None
    verification_required: bool | None = None
    independent_reviewer_required: bool | None = None
    internal_rag_policy_allows_unknown_rights: bool | None = None
    acquired_at: str | None = None


class SourceRightsUpsert(DomainModel):
    rights_status: RightsStatus = "unknown"
    license_name: str | None = Field(default=None, max_length=200)
    license_identifier: str | None = Field(default=None, max_length=200)
    license_url: str | None = Field(default=None, max_length=2000)
    copyright_owner: str | None = Field(default=None, max_length=200)
    permission_reference: str | None = Field(default=None, max_length=500)
    permission_document_reference: str | None = Field(default=None, max_length=500)
    permission_received_at: str | None = None
    permission_expires_at: str | None = None
    attribution_required: bool = False
    attribution_text: str | None = Field(default=None, max_length=2000)
    share_alike_required: bool = False
    modification_allowed: bool = False
    commercial_use_allowed: bool = False
    rag_use_allowed: bool = False
    training_use_allowed: bool = False
    evaluation_use_allowed: bool = False
    public_export_allowed: bool = False
    redistribution_allowed: bool = False
    internal_only: bool = False
    review_notes: str = Field(default="", max_length=4000)


class VerificationActionRequest(DomainModel):
    action: VerificationAction
    evidence_reference: str | None = Field(default=None, max_length=500)
    notes: str = Field(default="", max_length=4000)


class LinkCreate(DomainModel):
    entity_type: EntityType
    entity_public_id: str = Field(min_length=1, max_length=200)
    relationship_type: RelationshipType = "primary_source"
    source_page: str | None = Field(default=None, max_length=100)
    source_section: str | None = Field(default=None, max_length=200)
    source_locator: str | None = Field(default=None, max_length=500)


class UsageCheckRequest(DomainModel):
    target_use: TargetUse


class DataSourcePublic(DomainModel):
    public_id: str
    source_code: str
    title: str
    source_type: str
    owner_name: str | None
    author_name: str | None
    publisher_name: str | None
    organization_name: str | None
    source_url: str | None
    source_reference: str | None
    publication_year: int | None
    edition: str | None
    language_codes: list[str]
    description: str
    knowledge_risk: str
    fact_dependency: str
    verification_required: bool
    independent_reviewer_required: bool
    internal_rag_policy_allows_unknown_rights: bool
    acquired_at: str | None
    created_by_admin_public_id: str
    status: str
    created_at: Any
    updated_at: Any
