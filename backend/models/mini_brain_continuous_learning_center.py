"""MB-09: Continuous Learning Center API schemas."""

from typing import Any

from pydantic import Field

from backend.core.validation import DomainModel


class RecordMemoryRequest(DomainModel):
    continuous_learning_session_public_id: str = Field(min_length=1, max_length=100)
    model_version_public_id: str | None = None
    dataset_version_public_id: str | None = None
    benchmark_summary: dict[str, Any] = Field(default_factory=dict)
    admin_decision: str | None = Field(default=None, max_length=40)
    improvement_notes: str = Field(default="", max_length=4000)


class BuildDraftRequest(DomainModel):
    topic: str | None = Field(default=None, max_length=200)


class PrepareProviderRequestRequest(DomainModel):
    requested_providers: list[str] = Field(min_length=1, max_length=5)


class ProviderOutput(DomainModel):
    provider: str = Field(min_length=1, max_length=40)
    output_text: str = Field(min_length=1, max_length=20000)


class IngestProviderResultsRequest(DomainModel):
    provider_outputs: list[ProviderOutput] = Field(min_length=1, max_length=10)


class PlanDatasetEvolutionRequest(DomainModel):
    existing_dataset_source_public_id: str | None = None


class AdminReviewRequest(DomainModel):
    decision: str = Field(min_length=1, max_length=40)
