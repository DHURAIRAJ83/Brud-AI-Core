"""Phase 6 dataset version, build, and export request models."""

from typing import Any

from pydantic import Field

from backend.core.validation import DomainModel


class DatasetVersionCreate(DomainModel):
    name: str = Field(min_length=1, max_length=120)
    version: str = Field(min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=2000)
    parent_dataset_version_public_id: str | None = None


class DatasetVersionPatch(DomainModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)


class SplitConfiguration(DomainModel):
    train_percent: int = Field(default=90, ge=0, le=100)
    validation_percent: int = Field(default=5, ge=0, le=100)
    test_percent: int = Field(default=5, ge=0, le=100)
    seed: int = Field(default=42, ge=0)


class BuildCreate(DomainModel):
    dataset_name: str = Field(min_length=1, max_length=120)
    dataset_version: str = Field(min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=2000)
    selection_filters: dict[str, Any] = Field(default_factory=dict)
    split_configuration: SplitConfiguration | None = None
    minimum_quality_score: float = Field(default=0.0, ge=0, le=1)
    require_ready_quality: bool = False


class BuildRunRequest(DomainModel):
    confirm: bool = False
    allow_warnings: bool = False


class ExportCreate(DomainModel):
    export_format: str = "jsonl"


class ArchiveVersionRequest(DomainModel):
    comments: str | None = Field(default=None, max_length=4000)
