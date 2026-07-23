"""Phase 10 training-reliability API request schemas."""

from __future__ import annotations

from pydantic import Field

from backend.core.validation import DomainModel


class RecoveryRequest(DomainModel):
    comment: str | None = Field(default=None, max_length=2000)


class RunComparisonRequest(DomainModel):
    left_job_public_id: str
    right_job_public_id: str


class RetentionApplyRequest(DomainModel):
    checkpoint_public_ids: list[str] = Field(min_length=1, max_length=100)


class PromotionRequest(DomainModel):
    override_comment: str | None = Field(default=None, max_length=2000)
