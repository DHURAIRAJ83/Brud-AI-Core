"""Phase 19 Tamil corpus builder admin API.

Every mutation requires admin authentication and CSRF. There is no
public-facing route here, and nothing in this router starts model
training -- corpus building and export remain entirely separate from
the pretraining/instruction-tuning pipelines.
"""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.database.repositories.corpus import CorpusRepository
from backend.models.corpus import (
    BalancePolicyCreate,
    BalancePreviewRequest,
    BuildCreate,
    CollectionCreate,
    CollectionMemberCreate,
    ContaminationRunCreate,
    CorpusCompareRequest,
    CorpusPolicyCreate,
    CorpusPolicyPatch,
    DeduplicationRunCreate,
    ExportCreate,
    ExtractionRunCreate,
    IngestionJobCreate,
    LabelCorrection,
    LicenceReviewDecision,
    NormalizationProfileCreate,
    NormalizationRunCreate,
    PartitionPreviewRequest,
    ProtectedContentEntryCreate,
    ProtectedContentSetCreate,
    ReadinessEvaluationCreate,
    ReleaseApprovalCreate,
    ReleaseCreate,
    SegmentationProfileCreate,
    SegmentationRequest,
    SnapshotCreate,
    SourceInspectRequest,
    SourceLicenceCreate,
    SourceRegistryCreate,
    SourceRegistryPatch,
    SourceReviewUpdate,
    TokenizerAnalysisCreate,
    VersionCreate,
)
from backend.services.corpus_build_service import CorpusBuildService
from backend.services.corpus_export_service import CorpusExportService
from backend.services.corpus_ingestion_service import CorpusIngestionService
from backend.services.corpus_processing_service import CorpusProcessingService
from backend.services.corpus_profile_service import CorpusProfileService
from backend.services.corpus_quality_service import CorpusQualityService
from backend.services.corpus_readiness_service import CorpusReadinessService
from backend.services.corpus_release_service import CorpusReleaseService
from backend.services.corpus_source_service import CorpusSourceService
from backend.services.corpus_tokenizer_analysis_service import CorpusTokenizerAnalysisService

router = APIRouter(
    prefix="/admin/corpus", tags=["admin-corpus"], dependencies=[Depends(require_admin)]
)


class SourceTransitionRequest(BaseModel):
    target_status: str = Field(min_length=1, max_length=40)
    reason: str = Field(default="", max_length=2000)


class OriginVerificationRequest(BaseModel):
    evidence: str = Field(min_length=1, max_length=4000)


class ProductionLifecycleTransitionRequest(BaseModel):
    target_status: str = Field(min_length=1, max_length=40)
    reason: str = Field(default="", max_length=2000)


class IngestionJobRunRequest(BaseModel):
    relative_paths: list[str] = Field(min_length=1)


class ExportReleaseRequest(BaseModel):
    export_public_id: str = Field(min_length=1, max_length=64)


def _repository(settings) -> CorpusRepository:
    return CorpusRepository(settings.resolved_database_path)


def source_service(settings) -> CorpusSourceService:
    return CorpusSourceService(_repository(settings), settings)


def processing_service(settings) -> CorpusProcessingService:
    return CorpusProcessingService(_repository(settings), settings)


def quality_service(settings) -> CorpusQualityService:
    return CorpusQualityService(_repository(settings), settings)


def build_service(settings) -> CorpusBuildService:
    return CorpusBuildService(_repository(settings), settings)


def export_service(settings) -> CorpusExportService:
    return CorpusExportService(_repository(settings), settings)


def profile_service(settings) -> CorpusProfileService:
    return CorpusProfileService(_repository(settings), settings)


def ingestion_service(settings) -> CorpusIngestionService:
    return CorpusIngestionService(_repository(settings), settings)


def tokenizer_analysis_service(settings) -> CorpusTokenizerAnalysisService:
    return CorpusTokenizerAnalysisService(_repository(settings), settings)


def readiness_service(settings) -> CorpusReadinessService:
    return CorpusReadinessService(_repository(settings), settings)


def release_service(settings) -> CorpusReleaseService:
    return CorpusReleaseService(_repository(settings), settings)


# --- policies -----------------------------------------------------


@router.get("/policies")
async def list_policies(settings: SettingsDependency):
    return source_service(settings).list_policies()


@router.post("/policies")
async def create_policy(
    payload: CorpusPolicyCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return source_service(settings).create_policy(payload, admin.admin.public_id)


@router.get("/policies/{public_id}")
async def get_policy(public_id: str, settings: SettingsDependency):
    return source_service(settings).get_policy(public_id)


@router.patch("/policies/{public_id}")
async def patch_policy(
    public_id: str, payload: CorpusPolicyPatch, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return source_service(settings).patch_policy(public_id, payload, admin.admin.public_id)


@router.post("/policies/{public_id}/validate")
async def validate_policy(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return source_service(settings).validate_policy(public_id, admin.admin.public_id)


@router.post("/policies/{public_id}/activate")
async def activate_policy(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return source_service(settings).activate_policy(public_id, admin.admin.public_id)


# --- sources -----------------------------------------------------


@router.get("/sources")
async def list_sources(settings: SettingsDependency):
    return source_service(settings).list_sources()


@router.post("/sources")
async def create_source(
    payload: SourceRegistryCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return source_service(settings).create_source(payload, admin.admin.public_id)


@router.get("/sources/{public_id}")
async def get_source(public_id: str, settings: SettingsDependency):
    return source_service(settings).get_source(public_id)


@router.patch("/sources/{public_id}")
async def patch_source(
    public_id: str, payload: SourceRegistryPatch, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return source_service(settings).patch_source(public_id, payload, admin.admin.public_id)


@router.post("/sources/{public_id}/transition")
async def transition_source(
    public_id: str, payload: SourceTransitionRequest, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return source_service(settings).transition_source_status(
        public_id, payload.target_status, admin.admin.public_id, reason=payload.reason
    )


@router.post("/sources/{public_id}/verify-origin")
async def verify_origin(
    public_id: str, payload: OriginVerificationRequest, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return source_service(settings).verify_origin(
        public_id, admin.admin.public_id, evidence=payload.evidence
    )


@router.get("/sources/{public_id}/training-eligibility")
async def source_training_eligibility(public_id: str, settings: SettingsDependency):
    return source_service(settings).training_eligibility(public_id)


# --- licences -----------------------------------------------------


@router.post("/sources/{public_id}/licences")
async def create_licence(
    public_id: str, payload: SourceLicenceCreate, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return source_service(settings).create_licence(public_id, payload, admin.admin.public_id)


@router.post("/licences/{public_id}/review")
async def review_licence(
    public_id: str, payload: LicenceReviewDecision, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return source_service(settings).review_licence(public_id, payload, admin.admin.public_id)


# --- snapshots -----------------------------------------------------


@router.post("/sources/{public_id}/snapshots")
async def create_snapshot(
    public_id: str, payload: SnapshotCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return source_service(settings).create_snapshot(public_id, payload, admin.admin.public_id)


@router.get("/sources/{public_id}/snapshots")
async def list_snapshots(public_id: str, settings: SettingsDependency):
    return source_service(settings).list_snapshots(public_id)


@router.get("/snapshots/{public_id}")
async def get_snapshot(public_id: str, settings: SettingsDependency):
    return source_service(settings).get_snapshot(public_id)


# --- extraction -----------------------------------------------------


@router.post("/snapshots/{public_id}/extraction-runs")
async def create_extraction_run(
    public_id: str, payload: ExtractionRunCreate, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return processing_service(settings).create_extraction_run(
        public_id, payload, admin.admin.public_id
    )


@router.get("/extraction-runs/{public_id}")
async def get_extraction_run(public_id: str, settings: SettingsDependency):
    return processing_service(settings).get_extraction_run(public_id)


# --- normalization -----------------------------------------------------


@router.post("/extraction-runs/{public_id}/normalization-runs")
async def create_normalization_run(
    public_id: str, payload: NormalizationRunCreate, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return processing_service(settings).create_normalization_run(
        public_id, payload, admin.admin.public_id
    )


@router.get("/normalization-runs/{public_id}")
async def get_normalization_run(public_id: str, settings: SettingsDependency):
    return processing_service(settings).get_normalization_run(public_id)


# --- segmentation -----------------------------------------------------


@router.post("/normalized-documents/{public_id}/segment")
async def segment_normalized_document(
    public_id: str, payload: SegmentationRequest, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return processing_service(settings).segment_normalized_document(
        public_id, payload, admin.admin.public_id
    )


# --- quality/privacy/safety assessment -----------------------------------------------------


@router.post("/segments/{public_id}/assess")
async def assess_segment(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return quality_service(settings).assess_segment(public_id, admin.admin.public_id)


# --- deduplication -----------------------------------------------------


@router.post("/deduplication-runs")
async def create_deduplication_run(
    payload: DeduplicationRunCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return quality_service(settings).run_deduplication(payload, admin.admin.public_id)


@router.get("/deduplication-runs/{public_id}")
async def get_deduplication_run(public_id: str, settings: SettingsDependency):
    return quality_service(settings).get_deduplication_run(public_id)


# --- contamination -----------------------------------------------------


@router.post("/contamination-runs")
async def create_contamination_run(
    payload: ContaminationRunCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return quality_service(settings).run_contamination_check(payload, admin.admin.public_id)


@router.get("/contamination-runs/{public_id}")
async def get_contamination_run(public_id: str, settings: SettingsDependency):
    return quality_service(settings).get_contamination_run(public_id)


# --- collections -----------------------------------------------------


@router.get("/collections")
async def list_collections(settings: SettingsDependency):
    return build_service(settings).list_collections()


@router.post("/collections")
async def create_collection(
    payload: CollectionCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return build_service(settings).create_collection(payload, admin.admin.public_id)


@router.get("/collections/{public_id}")
async def get_collection(public_id: str, settings: SettingsDependency):
    return build_service(settings).get_collection(public_id)


@router.post("/collections/{public_id}/members")
async def add_collection_member(
    public_id: str, payload: CollectionMemberCreate, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return build_service(settings).add_member(
        public_id, payload.segment_public_id, admin.admin.public_id
    )


# --- balance policies -----------------------------------------------------


@router.get("/balance-policies")
async def list_balance_policies(settings: SettingsDependency):
    return build_service(settings).list_balance_policies()


@router.post("/balance-policies")
async def create_balance_policy(
    payload: BalancePolicyCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return build_service(settings).create_balance_policy(payload, admin.admin.public_id)


# --- builds -----------------------------------------------------


@router.get("/builds")
async def list_builds(settings: SettingsDependency):
    return build_service(settings).list_builds()


@router.post("/builds")
async def create_build(payload: BuildCreate, settings: SettingsDependency, admin: CsrfDependency):
    return build_service(settings).create_build(payload, admin.admin.public_id)


@router.get("/builds/{public_id}")
async def get_build(public_id: str, settings: SettingsDependency):
    return build_service(settings).get_build(public_id)


@router.get("/builds/{public_id}/balance-report")
async def build_balance_report(public_id: str, settings: SettingsDependency):
    return build_service(settings).balance_report(public_id)


# --- versions -----------------------------------------------------


@router.get("/versions")
async def list_versions(settings: SettingsDependency):
    return build_service(settings).list_versions()


@router.post("/builds/{public_id}/versions")
async def create_version(
    public_id: str, payload: VersionCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return build_service(settings).create_version(public_id, payload, admin.admin.public_id)


@router.get("/versions/{public_id}")
async def get_version(public_id: str, settings: SettingsDependency):
    return build_service(settings).get_version(public_id)


# --- exports -----------------------------------------------------


@router.post("/versions/{public_id}/exports")
async def create_export(
    public_id: str, payload: ExportCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return export_service(settings).create_export(public_id, payload, admin.admin.public_id)


@router.get("/exports/{public_id}")
async def get_export(public_id: str, settings: SettingsDependency):
    return export_service(settings).get_export(public_id)


# --- manifests -----------------------------------------------------


@router.post("/versions/{public_id}/manifest")
async def generate_manifest(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return export_service(settings).generate_manifest(public_id, admin.admin.public_id)


@router.get("/versions/{public_id}/manifest")
async def get_manifest(public_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return export_service(settings).get_manifest(public_id)


# --- comparisons -----------------------------------------------------


@router.post("/compare")
async def compare_versions_route(
    payload: CorpusCompareRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return export_service(settings).compare(payload, admin.admin.public_id)


@router.get("/comparisons/{public_id}")
async def get_comparison(public_id: str, settings: SettingsDependency):
    return export_service(settings).get_comparison(public_id)


# --- Phase 20: source governance -----------------------------------------------------


@router.patch("/sources/{public_id}/review-metadata")
async def set_source_review_metadata(
    public_id: str, payload: SourceReviewUpdate, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return source_service(settings).set_review_metadata(public_id, payload, admin.admin.public_id)


@router.post("/sources/{public_id}/production-lifecycle")
async def advance_source_production_lifecycle(
    public_id: str, payload: ProductionLifecycleTransitionRequest, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return source_service(settings).advance_production_lifecycle(
        public_id, payload.target_status, admin.admin.public_id, reason=payload.reason
    )


# --- Phase 20: normalization profiles -----------------------------------------------------


@router.get("/normalization-profiles")
async def list_normalization_profiles(settings: SettingsDependency):
    return profile_service(settings).list_normalization_profiles()


@router.post("/normalization-profiles")
async def create_normalization_profile(
    payload: NormalizationProfileCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return profile_service(settings).create_normalization_profile(payload, admin.admin.public_id)


@router.get("/normalization-profiles/{public_id}")
async def get_normalization_profile(public_id: str, settings: SettingsDependency):
    return profile_service(settings).get_normalization_profile(public_id)


@router.post("/normalization-profiles/{public_id}/activate")
async def activate_normalization_profile(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
):
    return profile_service(settings).activate_normalization_profile(
        public_id, admin.admin.public_id
    )


@router.post("/normalization-profiles/{public_id}/archive")
async def archive_normalization_profile(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
):
    return profile_service(settings).archive_normalization_profile(
        public_id, admin.admin.public_id
    )


# --- Phase 20: segmentation profiles -----------------------------------------------------


@router.get("/segmentation-profiles")
async def list_segmentation_profiles(settings: SettingsDependency):
    return profile_service(settings).list_segmentation_profiles()


@router.post("/segmentation-profiles")
async def create_segmentation_profile(
    payload: SegmentationProfileCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return profile_service(settings).create_segmentation_profile(payload, admin.admin.public_id)


@router.get("/segmentation-profiles/{public_id}")
async def get_segmentation_profile(public_id: str, settings: SettingsDependency):
    return profile_service(settings).get_segmentation_profile(public_id)


@router.post("/segmentation-profiles/{public_id}/activate")
async def activate_segmentation_profile(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
):
    return profile_service(settings).activate_segmentation_profile(
        public_id, admin.admin.public_id
    )


@router.post("/segmentation-profiles/{public_id}/archive")
async def archive_segmentation_profile(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
):
    return profile_service(settings).archive_segmentation_profile(
        public_id, admin.admin.public_id
    )


# --- Phase 20: ingestion jobs -----------------------------------------------------


@router.post("/sources/{public_id}/inspect-file")
async def inspect_source_file(
    public_id: str, payload: SourceInspectRequest, settings: SettingsDependency,
):
    del public_id  # read-only inspection; the approved root is source-agnostic
    return ingestion_service(settings).inspect_source_file(
        payload.relative_path, payload.declared_format
    )


@router.get("/sources/{public_id}/ingestion-jobs")
async def list_source_ingestion_jobs(public_id: str, settings: SettingsDependency):
    return ingestion_service(settings).list_jobs(public_id)


@router.post("/sources/{public_id}/ingestion-jobs")
async def create_ingestion_job(
    public_id: str, payload: IngestionJobCreate, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return ingestion_service(settings).create_job(public_id, payload, admin.admin.public_id)


@router.get("/ingestion-jobs/{public_id}")
async def get_ingestion_job(public_id: str, settings: SettingsDependency):
    return ingestion_service(settings).get_job(public_id)


@router.post("/ingestion-jobs/{public_id}/run")
async def run_ingestion_job(
    public_id: str, payload: IngestionJobRunRequest, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return ingestion_service(settings).run_job(
        public_id, payload.relative_paths, admin.admin.public_id
    )


@router.post("/ingestion-jobs/{public_id}/cancel")
async def cancel_ingestion_job(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return ingestion_service(settings).cancel_job(public_id, admin.admin.public_id)


@router.post("/ingestion-jobs/{public_id}/retry")
async def retry_ingestion_job(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return ingestion_service(settings).retry_job(public_id, admin.admin.public_id)


# --- Phase 20: label correction -----------------------------------------------------


@router.get("/segments/{public_id}/assessments")
async def segment_assessments(public_id: str, settings: SettingsDependency):
    return quality_service(settings).assessments_for_segment(public_id)


@router.post("/segments/{public_id}/correct-label")
async def correct_segment_label(
    public_id: str, payload: LabelCorrection, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return quality_service(settings).correct_label(public_id, payload, admin.admin.public_id)


# --- Phase 20: protected content registry -----------------------------------------------------


@router.get("/protected-content-sets")
async def list_protected_content_sets(settings: SettingsDependency):
    return quality_service(settings).list_protected_content_sets()


@router.post("/protected-content-sets")
async def create_protected_content_set(
    payload: ProtectedContentSetCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return quality_service(settings).create_protected_content_set(payload, admin.admin.public_id)


@router.get("/protected-content-sets/{public_id}")
async def get_protected_content_set(public_id: str, settings: SettingsDependency):
    return quality_service(settings).get_protected_content_set(public_id)


@router.post("/protected-content-sets/{public_id}/activate")
async def activate_protected_content_set(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
):
    return quality_service(settings).activate_protected_content_set(
        public_id, admin.admin.public_id
    )


@router.post("/protected-content-sets/{public_id}/entries")
async def add_protected_content_entries(
    public_id: str, payload: ProtectedContentEntryCreate, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return quality_service(settings).add_protected_content_entries(
        public_id, payload, admin.admin.public_id
    )


# --- Phase 20: balance/partition previews -----------------------------------------------------


@router.post("/collections/{public_id}/preview-balance")
async def preview_collection_balance(
    public_id: str, payload: BalancePreviewRequest, settings: SettingsDependency,
):
    return build_service(settings).preview_balance(public_id, payload)


@router.post("/collections/{public_id}/preview-partitions")
async def preview_collection_partitions(
    public_id: str, payload: PartitionPreviewRequest, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return build_service(settings).preview_partitions(public_id, payload, admin.admin.public_id)


# --- Phase 20: tokenizer compatibility analysis -----------------------------------------------


@router.post("/tokenizer-analyses")
async def create_tokenizer_analysis(
    payload: TokenizerAnalysisCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return tokenizer_analysis_service(settings).create_analysis(payload, admin.admin.public_id)


@router.get("/tokenizer-analyses/{public_id}")
async def get_tokenizer_analysis(public_id: str, settings: SettingsDependency):
    return tokenizer_analysis_service(settings).get_analysis(public_id)


# --- Phase 20: pretraining readiness -----------------------------------------------------


@router.post("/readiness-evaluations")
async def create_readiness_evaluation(
    payload: ReadinessEvaluationCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return readiness_service(settings).evaluate(payload, admin.admin.public_id)


@router.get("/readiness-evaluations/{public_id}")
async def get_readiness_evaluation(public_id: str, settings: SettingsDependency):
    return readiness_service(settings).get_evaluation(public_id)


# --- Phase 20: releases -----------------------------------------------------


@router.get("/releases")
async def list_releases(settings: SettingsDependency):
    return release_service(settings).list_releases()


@router.post("/releases")
async def create_release(
    payload: ReleaseCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return release_service(settings).create_release(payload, admin.admin.public_id)


@router.get("/releases/{public_id}")
async def get_release(public_id: str, settings: SettingsDependency):
    return release_service(settings).get_release(public_id)


@router.post("/releases/{public_id}/validate")
async def validate_release(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return release_service(settings).validate_release(public_id, admin.admin.public_id)


@router.post("/releases/{public_id}/approve")
async def approve_release(
    public_id: str, payload: ReleaseApprovalCreate, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return release_service(settings).record_approval(public_id, payload, admin.admin.public_id)


@router.post("/releases/{public_id}/finalize")
async def finalize_release(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return release_service(settings).finalize_release(public_id, admin.admin.public_id)


@router.post("/releases/{public_id}/export")
async def export_release(
    public_id: str, payload: ExportReleaseRequest, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return release_service(settings).mark_exported(
        public_id, payload.export_public_id, admin.admin.public_id
    )


@router.post("/releases/{public_id}/retire")
async def retire_release(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return release_service(settings).retire_release(public_id, admin.admin.public_id)
