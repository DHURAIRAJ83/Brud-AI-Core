"""MB-03: Brud Intelligence Engine API schemas."""

from pydantic import Field

from backend.core.validation import DomainModel


class QuestionAnalyzeRequest(DomainModel):
    question: str = Field(min_length=1, max_length=1000)
