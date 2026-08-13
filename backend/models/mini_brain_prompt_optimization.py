"""MB-04A: Prompt & Context Optimization API schemas."""

from pydantic import Field

from backend.core.validation import DomainModel


class PromptOptimizeRequest(DomainModel):
    question: str = Field(min_length=1, max_length=1000)
    max_tokens: int = Field(default=256, ge=1, le=1024)
    timeout_seconds: float = Field(default=90.0, gt=0, le=300)
    knowledge_budget_chars: int = Field(default=900, ge=100, le=4000)


class LanguageDetectRequest(DomainModel):
    question: str = Field(min_length=1, max_length=1000)
