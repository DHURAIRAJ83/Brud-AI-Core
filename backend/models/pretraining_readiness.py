"""Phase 21A request models: tokenizer corpus builds, tokenizer
candidate comparisons, base-model resource estimates, pretraining
dataset snapshots, training configuration validation, smoke runs, and
the base-model readiness gate."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from backend.core.validation import DomainModel


class TokenizerCorpusBuildCreate(DomainModel):
    corpus_release_public_id: str


class TokenizerCandidateComparisonCreate(DomainModel):
    tokenizer_corpus_build_public_id: str
    vocabulary_sizes: list[int] = Field(default_factory=lambda: [2000, 4000, 8000])
    include_unigram_candidate: bool = False


class TokenizerApprovalRequest(DomainModel):
    tokenizer_version_public_id: str


class ResourceEstimateCreate(DomainModel):
    profile_name: str = Field(min_length=1, max_length=40)
    vocabulary_size: int = Field(ge=1)
    total_training_tokens: int = Field(default=1_000_000, ge=1)
    safe_ram_ceiling_bytes: int | None = Field(default=None, ge=1)


class PretrainingSnapshotCreate(DomainModel):
    corpus_release_public_id: str
    tokenizer_version_public_id: str
    maximum_sequence_length: int = Field(default=512, ge=2, le=8192)
    deterministic_seed: int = Field(default=42, ge=0)


class TrainingConfigValidateRequest(DomainModel):
    pretraining_dataset_snapshot_public_id: str
    base_model_resource_estimate_public_id: str
    configuration: dict[str, Any] = Field(default_factory=dict)


class SmokeRunCreate(DomainModel):
    pretraining_dataset_snapshot_public_id: str
    base_model_resource_estimate_public_id: str
    total_steps: int = Field(default=20, ge=1, le=50)
    configuration: dict[str, Any] = Field(default_factory=dict)


class BaseModelReadinessEvaluationCreate(DomainModel):
    pretraining_dataset_snapshot_public_id: str
    tokenizer_candidate_comparison_public_id: str | None = None
    base_model_resource_estimate_public_id: str | None = None
    pretraining_smoke_run_public_id: str | None = None
