"""Request models for the Phase 6 Data Governance (Quality, Duplicate,
Conflict & Approval Integration) API."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from backend.core.validation import DomainModel

EntityType = Literal[
    "document_page",
    "manual_data_record",
    "semantic_chunk",
    "structured_record_candidate",
    "document_candidate",
    "dataset_record",
]

ReviewStatus = Literal[
    "open",
    "in_review",
    "waiting_for_correction",
    "waiting_for_source",
    "waiting_for_verification",
    "resolved",
    "rejected",
    "archived",
]

ReviewPriority = Literal["low", "normal", "high", "urgent"]

TargetUse = Literal[
    "rag",
    "training",
    "evaluation",
    "commercial",
    "public_export",
    "redistribution",
    "dataset_export",
    "rag_handoff",
]

ApprovalDecision = Literal["allowed", "blocked", "needs_review"]


class OpenReviewItemRequest(DomainModel):
    entity_type: EntityType
    entity_public_id: str
    reason: str = Field(min_length=1, max_length=2000)
    priority: ReviewPriority = "normal"
    entity_revision_public_id: str | None = None
    source_public_id: str | None = None
    document_public_id: str | None = None
    page_public_id: str | None = None


class AssignReviewRequest(DomainModel):
    assignee_admin_public_id: str = Field(min_length=1)


class SetReviewStatusRequest(DomainModel):
    status: ReviewStatus
    notes: str = Field(default="", max_length=2000)


class AddReviewNoteRequest(DomainModel):
    note: str = Field(min_length=1, max_length=2000)


class EntityRef(DomainModel):
    entity_type: EntityType
    entity_public_id: str


class ResolveGroupRequest(DomainModel):
    resolution_action: str = Field(min_length=1)
    resolution_reason: str = Field(min_length=1, max_length=2000)
    selected_entities: list[EntityRef] = Field(default_factory=list)


class OverrideApprovalRequest(DomainModel):
    decision: ApprovalDecision
    reason: str = Field(min_length=1, max_length=2000)
