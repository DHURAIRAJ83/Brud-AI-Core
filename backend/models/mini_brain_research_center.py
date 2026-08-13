"""MB-10: Research & Knowledge Acquisition Center API schemas."""

from pydantic import Field

from backend.core.validation import DomainModel


class CreateSessionRequest(DomainModel):
    topic: str = Field(min_length=1, max_length=200)


class PrepareResearchRequestRequest(DomainModel):
    planning_center_session_public_id: str | None = Field(default=None, max_length=100)
    priority: str | None = Field(default=None, max_length=40)


class SelectModeRequest(DomainModel):
    mode: str = Field(min_length=1, max_length=40)
    requested_provider_keys: list[str] = Field(default_factory=list, max_length=10)


class BuildLocalDraftRequest(DomainModel):
    existing_dataset_source_public_id: str | None = None


class ProviderOutput(DomainModel):
    provider: str = Field(min_length=1, max_length=40)
    output_text: str = Field(min_length=1, max_length=20000)


class IngestProviderResultsRequest(DomainModel):
    provider_outputs: list[ProviderOutput] = Field(min_length=1, max_length=10)


class DraftAdminReviewRequest(DomainModel):
    decision: str = Field(min_length=1, max_length=40)


class RagAdminReviewRequest(DomainModel):
    decision: str = Field(min_length=1, max_length=40)


class RunRagEvaluationRequest(DomainModel):
    rag_sandbox_experiment_public_id: str = Field(min_length=1, max_length=100)
    retrieval_run_public_id: str = Field(min_length=1, max_length=100)
    generation_assignment_public_id: str = Field(min_length=1, max_length=100)


class AnalyzeTrainingReportRequest(DomainModel):
    learning_supervisor_session_public_id: str = Field(min_length=1, max_length=100)


class RecordMemoryRequest(DomainModel):
    notes: str = Field(default="", max_length=4000)


class AddProviderRequest(DomainModel):
    provider_key: str = Field(min_length=1, max_length=40)
    display_name: str = Field(min_length=1, max_length=100)
    requires_external_call: bool = True
    description: str = Field(default="", max_length=2000)


class SetProviderStatusRequest(DomainModel):
    status: str = Field(min_length=1, max_length=20)
