"""MB-04B: Response Quality Engine API schemas."""

from typing import Any

from pydantic import Field

from backend.core.validation import DomainModel


class QualityCheckRequest(DomainModel):
    response_text: str = Field(min_length=1, max_length=20000)
    prompt_text: str = Field(default="", max_length=20000)
    expected_output_language: str = Field(default="english", pattern="^(english|tamil)$")
    response_plan: dict[str, Any] = Field(default_factory=dict)
    final_response: dict[str, Any] | None = None


class QualityFormatRequest(DomainModel):
    text: str = Field(min_length=1, max_length=20000)


class QualityGenerateRequest(DomainModel):
    question: str = Field(min_length=1, max_length=1000)
    max_tokens: int = Field(default=256, ge=1, le=1024)
    timeout_seconds: float = Field(default=90.0, gt=0, le=300)
    knowledge_budget_chars: int = Field(default=900, ge=100, le=4000)
