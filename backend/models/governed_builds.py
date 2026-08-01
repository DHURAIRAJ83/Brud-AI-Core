"""Request models for the Phase 7 Governed Build / Data Lineage API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from backend.core.validation import DomainModel

TargetPipeline = Literal[
    "dataset_version",
    "rag",
    "tokenizer",
    "pretraining",
    "instruction_tuning",
    "evaluation",
    "commercial_release",
    "public_export",
]


class CreateGovernedBuildRequest(DomainModel):
    target_pipeline: TargetPipeline
    build_label: str = Field(default="", max_length=200)
    configuration: dict[str, Any] = Field(default_factory=dict)


class UpdateGovernedBuildRequest(DomainModel):
    build_label: str | None = Field(default=None, max_length=200)
    configuration: dict[str, Any] | None = None


class UpdateSelectionRequest(DomainModel):
    item_public_id: str
    included: bool


class RagIngestRequest(DomainModel):
    knowledge_space_public_id: str
    title: str = Field(min_length=1, max_length=300)


class CreateLineageEdgeRequest(DomainModel):
    upstream_entity_type: str
    upstream_entity_id: str
    downstream_entity_type: str
    downstream_entity_id: str
    relationship_type: str
    metadata: dict[str, Any] = Field(default_factory=dict)
