"""Validated request schemas for document extraction and candidate review."""

from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from backend.core.validation import DomainModel, LanguageCode
from backend.models.domain import DatasetRecordType


class ExtractionStrategy(StrEnum):
    AUTO = "auto"
    EMBEDDED = "embedded_text"
    OCR = "ocr"
    HYBRID = "hybrid"


class SegmentMode(StrEnum):
    PARAGRAPH = "paragraph_as_pretrain"
    PAGE = "page_as_pretrain"
    FIXED = "fixed_window_pretrain"


class ProcessRequest(DomainModel):
    strategy: ExtractionStrategy = ExtractionStrategy.AUTO
    pages: list[int] | None = None
    ocr_language: str | None = None

    @field_validator("pages")
    @classmethod
    def validate_pages(cls, value: list[int] | None) -> list[int] | None:
        if value is not None and (not value or len(value) > 300 or any(page < 1 for page in value)):
            raise ValueError("pages must be a bounded list of positive page numbers")
        return sorted(set(value)) if value else value


class PageEdit(DomainModel):
    cleaned_text: str = Field(min_length=1, max_length=100_000)


class SegmentRequest(DomainModel):
    mode: SegmentMode = SegmentMode.PARAGRAPH
    language: LanguageCode = LanguageCode.UNKNOWN
    max_chars: int | None = Field(default=None, ge=100, le=20_000)
    overlap_chars: int | None = Field(default=None, ge=0, le=5000)

    @model_validator(mode="after")
    def overlap_is_smaller(self) -> "SegmentRequest":
        if (
            self.max_chars is not None
            and self.overlap_chars is not None
            and self.overlap_chars >= self.max_chars
        ):
            raise ValueError("overlap must be smaller than segment size")
        return self


class CandidatePatch(DomainModel):
    candidate_type: DatasetRecordType | None = None
    language: LanguageCode | None = None
    instruction: str | None = Field(default=None, max_length=20_000)
    input_text: str | None = Field(default=None, max_length=100_000)
    output_text: str | None = Field(default=None, max_length=100_000)
    normalized_input: str | None = Field(default=None, max_length=100_000)
    candidate_text: str | None = Field(default=None, max_length=100_000)


class CandidateImport(DomainModel):
    confirm: bool

    @model_validator(mode="after")
    def explicit_confirmation(self) -> "CandidateImport":
        if not self.confirm:
            raise ValueError("explicit candidate import confirmation is required")
        return self
