"""MB-05.1: Advanced Dataset Intelligence API schemas."""

from pydantic import Field

from backend.core.validation import DomainModel


class AdvancedDatasetRequest(DomainModel):
    source_public_id: str = Field(min_length=1, max_length=100)
