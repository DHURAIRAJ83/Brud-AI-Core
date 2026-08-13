"""MB-23: Public Chat Runtime & Self-Improvement Feedback Loop API
schemas."""

from pydantic import Field

from backend.core.validation import DomainModel
from backend.models.public_chat import MAX_COMMENT_LENGTH, MAX_MESSAGE_LENGTH


class StartSessionRequest(DomainModel):
    language: str = Field(default="auto", max_length=10)


class SendMessageRequest(DomainModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)


class SubmitFeedbackRequest(DomainModel):
    satisfaction_rating: float | None = Field(default=None, ge=0.0, le=1.0)
    comment: str | None = Field(default=None, max_length=MAX_COMMENT_LENGTH)


class ReviewCandidateRequest(DomainModel):
    decision: str = Field(min_length=1, max_length=20)
    notes: str | None = Field(default=None, max_length=2000)


class GenerateCandidatesRequest(DomainModel):
    minimum_frequency: int = Field(default=2, ge=1, le=1000)
