"""MB-12: Knowledge Pipeline Coordinator API schemas."""

from pydantic import Field

from backend.core.validation import DomainModel


class CreateSessionRequest(DomainModel):
    topic: str = Field(min_length=1, max_length=200)


class LinkResearchRequest(DomainModel):
    mb09_session_public_id: str = Field(min_length=1, max_length=100)


class LinkResearchCenterRequest(DomainModel):
    mb10_session_public_id: str = Field(min_length=1, max_length=100)


class LinkDatasetEvolutionRequest(DomainModel):
    mb11_session_public_id: str = Field(min_length=1, max_length=100)


class LinkTrainingRequest(DomainModel):
    mb06_session_public_id: str = Field(min_length=1, max_length=100)


class AdminDecisionRequest(DomainModel):
    decision: str = Field(min_length=1, max_length=40)
