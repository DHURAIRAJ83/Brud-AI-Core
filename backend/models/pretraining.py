"""Pretraining API request schemas."""

from typing import Any

from pydantic import Field

from backend.core.validation import DomainModel


class PretrainingJobCreate(DomainModel):
    name: str = Field(min_length=1, max_length=160)
    dataset_version_public_id: str
    tokenizer_version_public_id: str
    core_model_version_public_id: str
    job_mode: str = "smoke_pretraining"
    configuration: dict[str, Any] = Field(default_factory=dict)


class PretrainingJobPatch(DomainModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    configuration: dict[str, Any] | None = None


class CheckpointCompareRequest(DomainModel):
    left_checkpoint_public_id: str
    right_checkpoint_public_id: str
