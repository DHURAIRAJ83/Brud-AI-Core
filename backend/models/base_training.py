"""Phase 11 base-training API request schemas."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from backend.core.validation import DomainModel


class BaseTrainingExperimentCreate(DomainModel):
    name: str = Field(min_length=1, max_length=160)
    objective: str = Field(default="", max_length=2000)
    dataset_version_public_id: str
    initialization_seed: int = 42
    sampling_seed: int = 42
    training_configuration: dict[str, Any] = Field(default_factory=dict)
    evaluation_configuration: dict[str, Any] = Field(default_factory=dict)
    resource_limits: dict[str, Any] = Field(default_factory=dict)


class BaseTrainingExperimentPatch(DomainModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    objective: str | None = Field(default=None, max_length=2000)
    tokenizer_version_public_id: str | None = None
    core_model_version_public_id: str | None = None


class BaseTrainingRunCreate(DomainModel):
    run_label: str = Field(min_length=1, max_length=160)
    configuration: dict[str, Any] = Field(default_factory=dict)
    config_diff: dict[str, Any] = Field(default_factory=dict)


class BaseTrainingRunCompareRequest(DomainModel):
    left_run_public_id: str
    right_run_public_id: str


class CandidateSelectionRequest(DomainModel):
    override_comment: str | None = Field(default=None, max_length=2000)
