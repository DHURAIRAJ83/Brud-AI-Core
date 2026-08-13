"""MB-04: CPU Runtime & Model Integration API schemas."""

from typing import Any

from pydantic import Field

from backend.core.validation import DomainModel


class ModelRegisterRequest(DomainModel):
    name: str = Field(min_length=1, max_length=200)
    path: str = Field(min_length=1, max_length=1000)
    quantization: str = Field(min_length=1, max_length=40)
    context_length: int = Field(gt=0, le=131072)


class LoadModelRequest(DomainModel):
    model_public_id: str


class GenerateRequest(DomainModel):
    response_plan: dict[str, Any]
    max_tokens: int = Field(default=256, gt=0, le=4096)
    timeout_seconds: float = Field(default=30.0, gt=0, le=300)
