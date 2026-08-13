"""MB-13: Language Intelligence & Dataset Normalization Center API
schemas."""

from pydantic import Field

from backend.core.validation import DomainModel


class CreateSessionRequest(DomainModel):
    dataset_source_public_id: str = Field(min_length=1, max_length=100)


class TranslationPair(DomainModel):
    tamil_text: str = Field(default="", max_length=20000)
    english_text: str = Field(default="", max_length=20000)


class RunTranslationAnalysisRequest(DomainModel):
    pairs: list[TranslationPair] = Field(default_factory=list, max_length=50)


class AdminReviewRequest(DomainModel):
    decision: str = Field(min_length=1, max_length=40)
