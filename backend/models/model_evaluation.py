"""Phase 13 multilingual evaluation, safety, and chat-readiness API schemas."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from backend.core.validation import DomainModel


class ModelEvaluationSuiteCreate(DomainModel):
    name: str = Field(min_length=1, max_length=160)
    version: str = Field(min_length=1, max_length=40)
    description: str = Field(default="", max_length=4000)
    supported_languages: list[str] = Field(default_factory=lambda: ["ta", "en", "tgl", "mixed"])
    generation_configuration: dict[str, Any] = Field(default_factory=dict)
    automated_thresholds: dict[str, Any] = Field(default_factory=dict)
    human_review_rubric: dict[str, Any] = Field(default_factory=dict)
    readiness_gate_configuration: dict[str, Any] = Field(default_factory=dict)


class ModelEvaluationSuitePatch(DomainModel):
    description: str | None = Field(default=None, max_length=4000)
    generation_configuration: dict[str, Any] | None = None
    automated_thresholds: dict[str, Any] | None = None
    human_review_rubric: dict[str, Any] | None = None
    readiness_gate_configuration: dict[str, Any] | None = None


class ModelEvaluationFixtureCreate(DomainModel):
    category: str = Field(min_length=1, max_length=60)
    language: str = Field(min_length=2, max_length=8)
    prompt: str = Field(min_length=1, max_length=2000)
    system_prompt: str | None = Field(default=None, max_length=2000)
    expected_response_language: str | None = Field(default=None, max_length=8)
    expected_format: str | None = Field(default=None, max_length=60)
    expected_keywords: list[str] = Field(default_factory=list)
    forbidden_keywords: list[str] = Field(default_factory=list)
    reference_answer: str | None = Field(default=None, max_length=4000)
    reference_facts: list[str] = Field(default_factory=list)
    refusal_expected: bool = False
    max_new_tokens: int = Field(default=32, ge=1, le=128)
    timeout_seconds: float = Field(default=5.0, gt=0, le=60.0)
    severity: str = Field(default="medium", max_length=20)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModelEvaluationFixtureSetCreate(DomainModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=4000)
    fixtures: list[ModelEvaluationFixtureCreate] = Field(min_length=1)


class ModelEvaluationRunCreate(DomainModel):
    model_evaluation_fixture_set_public_id: str
    candidate_core_model_version_public_id: str
    generation_configuration: dict[str, Any] = Field(default_factory=dict)


class HumanReviewCreate(DomainModel):
    model_evaluation_output_public_id: str
    language: str = Field(min_length=2, max_length=8)
    category: str = Field(min_length=1, max_length=60)
    relevance_score: int = Field(ge=1, le=5)
    correctness_score: int | None = Field(default=None, ge=1, le=5)
    instruction_following_score: int = Field(ge=1, le=5)
    language_quality_score: int = Field(ge=1, le=5)
    safety_score: int = Field(ge=1, le=5)
    overall_score: int = Field(ge=1, le=5)
    verdict: str = Field(min_length=1, max_length=40)
    comment: str = Field(default="", max_length=4000)


class ModelEvaluationComparisonCreate(DomainModel):
    left_run_public_id: str
    right_run_public_id: str
