"""Tokenizer API request models for Phase 7."""

from typing import Any

from pydantic import Field

from backend.core.validation import DomainModel

SPECIAL_TOKENS = [
    "<pad>",
    "<unk>",
    "<bos>",
    "<eos>",
    "<system>",
    "<user>",
    "<assistant>",
    "<ta>",
    "<en>",
    "<tgl>",
    "<mixed>",
]


class TokenizerFamilyCreate(DomainModel):
    name: str = Field(min_length=1, max_length=120)
    display_name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)


class TokenizerFamilyPatch(DomainModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    status: str | None = None


class TokenizerVersionCreate(DomainModel):
    family_public_id: str
    version: str = Field(min_length=1, max_length=80)
    dataset_version_public_id: str
    algorithm: str = "bpe"
    vocabulary_size: int = Field(default=16000, ge=1)
    character_coverage: float = Field(default=0.9995, gt=0, le=1)
    normalization_rule_name: str = "nmt_nfkc"
    special_tokens: list[str] = Field(default_factory=lambda: list(SPECIAL_TOKENS))
    configuration: dict[str, Any] = Field(default_factory=dict)


class TokenizerVersionPatch(DomainModel):
    vocabulary_size: int | None = Field(default=None, ge=1)
    character_coverage: float | None = Field(default=None, gt=0, le=1)
    configuration: dict[str, Any] | None = None


class TokenizerJobCreate(DomainModel):
    tokenizer_version_public_id: str
    job_type: str = "full_pipeline"
    configuration: dict[str, Any] = Field(default_factory=dict)


class EncodeRequest(DomainModel):
    text: str = Field(min_length=1, max_length=20_000)


class DecodeRequest(DomainModel):
    ids: list[int] = Field(min_length=1, max_length=20_000)


class CompareRequest(DomainModel):
    left_version_public_id: str
    right_version_public_id: str
    sample_text: str = Field(min_length=1, max_length=20_000)


class AssignmentPatch(DomainModel):
    tokenizer_version_public_id: str | None = None
    fallback_tokenizer_version_public_id: str | None = None
    enabled: bool = False
    configuration: dict[str, Any] = Field(default_factory=dict)


class TokenizerExportCreate(DomainModel):
    export_format: str = "sentencepiece_bundle"
