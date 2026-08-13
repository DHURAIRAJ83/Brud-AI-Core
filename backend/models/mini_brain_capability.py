"""MB-04C: Model Capability Optimization API schemas."""

from pydantic import Field

from backend.core.validation import DomainModel


class CapabilityAnalyzeRequest(DomainModel):
    question: str = Field(min_length=1, max_length=1000)


class CapabilityGenerateRequest(DomainModel):
    question: str = Field(min_length=1, max_length=1000)
    timeout_seconds: float = Field(default=90.0, gt=0, le=300)


class CapabilityProfileRequest(DomainModel):
    model_name: str | None = None
    quantization: str | None = None
