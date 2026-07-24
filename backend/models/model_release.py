"""Phase 14 model-release registry API request schemas."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from backend.core.validation import DomainModel


class ModelReleaseFamilyCreate(DomainModel):
    name: str = Field(min_length=1, max_length=160)
    slug: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9][a-z0-9-]*$")
    description: str = Field(default="", max_length=4000)
    intended_use: str = Field(default="", max_length=2000)
    supported_languages: list[str] = Field(default_factory=lambda: ["ta", "en", "tgl", "mixed"])
    compatibility_policy: dict[str, Any] = Field(default_factory=dict)


class ModelReleaseFamilyPatch(DomainModel):
    description: str | None = Field(default=None, max_length=4000)
    intended_use: str | None = Field(default=None, max_length=2000)
    supported_languages: list[str] | None = None
    compatibility_policy: dict[str, Any] | None = None
    lifecycle_status: str | None = Field(default=None, max_length=20)


class ModelReleaseCandidateCreate(DomainModel):
    model_release_family_public_id: str
    core_model_version_public_id: str
    dataset_version_public_id: str | None = None
    instruction_tuning_candidate_public_id: str | None = None
    model_evaluation_run_public_id: str | None = None
    label: str | None = Field(default=None, max_length=80)
    notes: str = Field(default="", max_length=4000)


class ModelReleaseCandidatePatch(DomainModel):
    label: str | None = Field(default=None, max_length=80)
    notes: str | None = Field(default=None, max_length=4000)


class ModelCardOverrides(DomainModel):
    summary: str = Field(default="", max_length=2000)
    intended_uses: str = Field(default="", max_length=2000)
    out_of_scope_uses: str = Field(default="", max_length=2000)
    known_limitations: str = Field(default="", max_length=2000)
    safety_limitations: str = Field(default="", max_length=2000)
    licence_and_provenance: str = Field(default="", max_length=2000)


class ApprovalCreate(DomainModel):
    role: str = Field(min_length=1, max_length=20)
    decision: str = Field(min_length=1, max_length=40)
    comment: str = Field(default="", max_length=2000)


class ModelReleaseCreate(DomainModel):
    candidate_public_id: str
    version: str = Field(min_length=1, max_length=40)
    prerelease_label: str | None = Field(default=None, max_length=40)


class ModelReleaseComparisonCreate(DomainModel):
    left_release_public_id: str
    right_release_public_id: str


class RollbackPlanCreate(DomainModel):
    target_release_public_id: str
    reason: str = Field(default="", max_length=2000)


class RollbackApprovalCreate(DomainModel):
    comment: str = Field(default="", max_length=2000)


class BundleCreate(DomainModel):
    bundle_format: str = Field(default="zip", max_length=20)
