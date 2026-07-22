"""Core model API schemas."""

from typing import Any

from pydantic import Field

from backend.core.validation import DomainModel


class CoreFamilyCreate(DomainModel):
    name: str = Field(min_length=1, max_length=120)
    display_name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)


class CoreFamilyPatch(DomainModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    status: str | None = None


class CoreConfigCreate(DomainModel):
    name: str = Field(min_length=1, max_length=120)
    config_version: str = Field(min_length=1, max_length=80)
    tokenizer_version_public_id: str
    preset: str = Field(default="micro")
    context_length: int | None = None
    hidden_size: int | None = None
    intermediate_size: int | None = None
    num_hidden_layers: int | None = None
    num_attention_heads: int | None = None
    num_key_value_heads: int | None = None
    rope_theta: float = 10000.0
    rms_norm_epsilon: float = 1e-6
    attention_dropout: float = Field(default=0.0, ge=0, le=1)
    residual_dropout: float = Field(default=0.0, ge=0, le=1)
    embedding_dropout: float = Field(default=0.0, ge=0, le=1)
    initializer_range: float = Field(default=0.02, gt=0, le=1)
    tie_word_embeddings: bool = True
    use_bias: bool = False
    configuration: dict[str, Any] = Field(default_factory=dict)


class CoreConfigPatch(DomainModel):
    configuration: dict[str, Any] | None = None


class CoreVersionCreate(DomainModel):
    family_public_id: str
    config_public_id: str
    version: str = Field(min_length=1, max_length=80)
    initialization_seed: int = Field(default=42, ge=0, le=2_147_483_647)


class ForwardTestRequest(DomainModel):
    input_ids: list[int] = Field(min_length=2, max_length=256)
    labels: list[int] | None = None


class CoreAssignmentPatch(DomainModel):
    core_model_version_public_id: str | None = None
    enabled: bool = True
    configuration: dict[str, Any] = Field(default_factory=dict)
