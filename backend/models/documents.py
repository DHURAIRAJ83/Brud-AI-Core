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
    change_summary: str = Field(default="", max_length=2000)
    correction_types: list[str] = Field(default_factory=list)


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


class SourceLinkRequest(DomainModel):
    source_public_id: str = Field(min_length=1, max_length=200)


class ReviewActionRequest(DomainModel):
    notes: str = Field(default="", max_length=4000)


class OcrRerunRequest(DomainModel):
    ocr_language: str | None = None


class ExtractionRerunRequest(DomainModel):
    strategy: ExtractionStrategy = ExtractionStrategy.AUTO


class CleanupSuggestionItem(DomainModel):
    suggestion_type: str
    original_text: str = ""
    proposed_text: str = ""
    reason: str = ""
    confidence: float = 0.0
    risk_level: str = "low"
    reason_code: str = ""


class ApplyCleanupRequest(DomainModel):
    suggestions: list[CleanupSuggestionItem] = Field(default_factory=list, min_length=1)


class RepeatedElementReview(DomainModel):
    action: str
    confirm: bool = False
    target_pages: list[int] | None = None

    @field_validator("action")
    @classmethod
    def validate_action(cls, value: str) -> str:
        if value not in ("accept", "reject", "apply_selected", "apply_all"):
            raise ValueError(f"unsupported repeated-element action: {value!r}")
        return value


class SftTask(StrEnum):
    DEFINITION = "definition"
    FACT_ANSWER = "fact_answer"
    EXPLANATION = "explanation"
    CONTEXTUAL_MEANING = "contextual_meaning"
    MULTIPLE_MEANINGS = "multiple_meanings"
    GRAMMAR = "grammar"
    SPELLING_CORRECTION = "spelling_correction"
    GRAMMAR_CORRECTION = "grammar_correction"
    INSTRUCTION_FOLLOWING = "instruction_following"
    SUMMARIZATION = "summarization"
    CLARIFICATION_REQUEST = "clarification_request"
    TAMIL_TO_ENGLISH = "Tamil_to_English"
    ENGLISH_TO_TAMIL = "English_to_Tamil"
    TANGLISH_INPUT_TO_TAMIL = "Tanglish_input_to_Tamil"
    BASIC_MATH_REASONING = "basic_math_reasoning"
    COMPUTER_BASICS = "computer_basics"
    SAFETY_RESPONSE = "safety_response"


class SftCandidateGenerationRequest(DomainModel):
    chunk_public_ids: list[str] | None = None
    max_candidates: int | None = Field(default=None, ge=1, le=500)


class SftCandidateReviewAction(DomainModel):
    action: str
    edited_instruction: str | None = Field(default=None, max_length=20_000)
    edited_context: str | None = Field(default=None, max_length=100_000)
    edited_response: str | None = Field(default=None, max_length=100_000)
    notes: str = Field(default="", max_length=4000)

    @field_validator("action")
    @classmethod
    def validate_action(cls, value: str) -> str:
        if value not in ("approve", "reject", "edit", "needs_correction"):
            raise ValueError(f"unsupported sft candidate review action: {value!r}")
        return value


class SftBulkApprovalRequest(DomainModel):
    candidate_public_ids: list[str] = Field(min_length=1, max_length=100)
    confirm: bool

    @model_validator(mode="after")
    def explicit_confirmation(self) -> "SftBulkApprovalRequest":
        if not self.confirm:
            raise ValueError("explicit bulk-approval confirmation is required")
        return self


class SftExportRequest(DomainModel):
    confirm: bool

    @model_validator(mode="after")
    def explicit_confirmation(self) -> "SftExportRequest":
        if not self.confirm:
            raise ValueError("explicit export confirmation is required")
        return self


class TamilQualityReviewAction(DomainModel):
    action: str
    edited_text: str | None = Field(default=None, max_length=100_000)
    apply_to_exact_duplicates_only: bool = False
    notes: str = Field(default="", max_length=4000)

    @field_validator("action")
    @classmethod
    def validate_action(cls, value: str) -> str:
        if value not in ("accept", "reject", "edit", "ignore"):
            raise ValueError(f"unsupported tamil quality review action: {value!r}")
        return value


# --- Production integration: dataset handoff / tamil rules / classification / security ------


class SftExportValidateRequest(DomainModel):
    pass


class SftHandoffIngestRequest(DomainModel):
    confirm: bool

    @model_validator(mode="after")
    def explicit_confirmation(self) -> "SftHandoffIngestRequest":
        if not self.confirm:
            raise ValueError("explicit dataset handoff ingestion confirmation is required")
        return self


class DatasetVersionProposalRequest(DomainModel):
    dataset_name: str = Field(min_length=1, max_length=200)
    dataset_version: str = Field(min_length=1, max_length=50)


class ConfirmBuildRequest(DomainModel):
    confirm: bool

    @model_validator(mode="after")
    def explicit_confirmation(self) -> "ConfirmBuildRequest":
        if not self.confirm:
            raise ValueError("explicit dataset-version build confirmation is required")
        return self


class TamilCorrectionRuleCreate(DomainModel):
    incorrect_form: str = Field(min_length=1, max_length=2000)
    approved_correction: str = Field(min_length=1, max_length=2000)
    issue_category: str
    evidence: str = Field(default="", max_length=4000)
    confidence_band: str = "medium"
    meaning_change_risk: str

    @field_validator("issue_category")
    @classmethod
    def validate_issue_category(cls, value: str) -> str:
        allowed = {
            "known_ocr_substitution", "pulli_error", "vowel_sign_error", "grapheme_integrity",
            "zero_width_contamination", "unicode_normalization_mismatch", "spelling_variant",
            "word_boundary_anomaly", "punctuation_spacing", "mixed_script_contamination",
        }
        if value not in allowed:
            raise ValueError(f"unsupported Tamil correction issue_category: {value!r}")
        return value

    @field_validator("meaning_change_risk")
    @classmethod
    def validate_meaning_change_risk(cls, value: str) -> str:
        allowed = {"mechanical", "spelling", "grammatical", "meaning_sensitive", "ambiguous"}
        if value not in allowed:
            raise ValueError(f"unsupported Tamil correction meaning_change_risk: {value!r}")
        return value


class TamilCorrectionRuleReviewAction(DomainModel):
    action: str
    notes: str = Field(default="", max_length=4000)

    @field_validator("action")
    @classmethod
    def validate_action(cls, value: str) -> str:
        if value not in ("submit_review", "approve", "activate", "reject"):
            raise ValueError(f"unsupported Tamil correction rule action: {value!r}")
        return value


class SecurityFindingReviewAction(DomainModel):
    action: str

    @field_validator("action")
    @classmethod
    def validate_action(cls, value: str) -> str:
        if value not in ("reviewed", "dismissed"):
            raise ValueError(f"unsupported security finding review action: {value!r}")
        return value
