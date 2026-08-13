"""MB-08: Continuous Learning & Feedback Engine API schemas."""

from pydantic import Field

from backend.core.validation import DomainModel


class ContinuousLearningSessionCreateRequest(DomainModel):
    cycle_window_days: int = Field(default=30, ge=1, le=365)


class AdminReviewRequest(DomainModel):
    decision: str = Field(min_length=1, max_length=20)
