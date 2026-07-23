"""Phase 12 instruction-tuning API request schemas."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from backend.core.validation import DomainModel


class InstructionTuningExperimentCreate(DomainModel):
    name: str = Field(min_length=1, max_length=160)
    objective: str = Field(default="", max_length=2000)
    base_core_model_version_public_id: str
    dataset_version_public_id: str
    initialization_seed: int = 42
    sampling_seed: int = 42
    training_configuration: dict[str, Any] = Field(default_factory=dict)
    evaluation_configuration: dict[str, Any] = Field(default_factory=dict)
    resource_limits: dict[str, Any] = Field(default_factory=dict)


class InstructionTuningExperimentPatch(DomainModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    objective: str | None = Field(default=None, max_length=2000)
    instruction_template_public_id: str | None = None


class InstructionTemplateCreate(DomainModel):
    name: str = Field(min_length=1, max_length=160)
    version: str = Field(min_length=1, max_length=40)
    tokenizer_version_public_id: str
    insert_language_marker: bool = True


class InstructionTuningRunCreate(DomainModel):
    run_label: str = Field(min_length=1, max_length=160)
    configuration: dict[str, Any] = Field(default_factory=dict)
    config_diff: dict[str, Any] = Field(default_factory=dict)
    truncation_policy: str = Field(default="truncate_prompt_first")


class InstructionTuningRunCompareRequest(DomainModel):
    left_run_public_id: str
    right_run_public_id: str


class InstructionCandidateSelectionRequest(DomainModel):
    override_comment: str | None = Field(default=None, max_length=2000)


class DiagnosticGenerateRequest(DomainModel):
    prompt_text: str = Field(min_length=1, max_length=4000)
    max_new_tokens: int = Field(default=32, ge=1, le=256)
