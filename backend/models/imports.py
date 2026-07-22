"""Validated API schemas for the Phase 4 dataset import pipeline."""

from enum import StrEnum
from typing import Any

from pydantic import Field, field_validator, model_validator

from backend.core.validation import DomainModel, LanguageCode
from backend.models.domain import DatasetRecordType


class ImportMode(StrEnum):
    CREATE_ONLY = "create_only"
    SKIP_DUPLICATES = "skip_duplicates"


class TxtMode(StrEnum):
    ONE_RECORD_PER_LINE = "one_record_per_line"
    WHOLE_FILE_AS_PRETRAIN = "whole_file_as_pretrain"


ALLOWED_MAPPING_TARGETS = {
    "record_type",
    "language",
    "instruction",
    "input_text",
    "output_text",
    "normalized_input",
    "metadata",
    "source_language",
    "target_language",
}


class MappingUpdate(DomainModel):
    field_mapping: dict[str, str] = Field(default_factory=dict)
    parser_options: dict[str, Any] = Field(default_factory=dict)
    record_type: DatasetRecordType | None = None
    default_language: LanguageCode | None = None
    import_mode: ImportMode | None = None

    @field_validator("field_mapping")
    @classmethod
    def validate_mapping(cls, value: dict[str, str]) -> dict[str, str]:
        unknown = set(value) - ALLOWED_MAPPING_TARGETS
        if unknown:
            raise ValueError(f"unknown mapping targets: {', '.join(sorted(unknown))}")
        sources = [source for source in value.values() if source]
        if len(sources) != len(set(sources)):
            raise ValueError("one source field cannot map to multiple targets")
        return value


class ImportConfirm(DomainModel):
    confirm: bool
    include_warnings: bool = True

    @model_validator(mode="after")
    def explicit_confirmation(self) -> "ImportConfirm":
        if not self.confirm:
            raise ValueError("explicit import confirmation is required")
        return self


class ImportPage(DomainModel):
    items: list[dict[str, Any]]
    page: int
    page_size: int
    total: int
    total_pages: int
