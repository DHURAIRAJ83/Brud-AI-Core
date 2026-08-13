"""MB-16: Multimodal Dataset Generator Center API schemas."""

from pydantic import Field

from backend.core.validation import DomainModel


class CreateSessionRequest(DomainModel):
    document_source_public_id: str = Field(min_length=1, max_length=100)
    dataset_source_public_id: str | None = Field(default=None, max_length=100)
    language_session_public_id: str | None = Field(default=None, max_length=100)
    vision_session_public_id: str | None = Field(default=None, max_length=100)
    vision_model_session_public_id: str | None = Field(default=None, max_length=100)


class AdminReviewRequest(DomainModel):
    decision: str = Field(min_length=1, max_length=40)


class ExportDraftRequest(DomainModel):
    export_format: str = Field(default="json", min_length=1, max_length=10)


class SplitDatasetRequest(DomainModel):
    record_public_ids: list[str] = Field(min_length=1, max_length=5000)


class MergeDatasetsRequest(DomainModel):
    session_public_ids: list[str] = Field(min_length=2, max_length=100)
