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
    LicenceReviewDecision,
    NormalizationRunCreate,
    SegmentationRequest,
    SnapshotCreate,
    SourceLicenceCreate,
    SourceRegistryCreate,
    SourceRegistryPatch,
    VersionCreate,
)
from backend.services.corpus_build_service import CorpusBuildService
from backend.services.corpus_export_service import CorpusExportService
from backend.services.corpus_processing_service import CorpusProcessingService
from backend.services.corpus_quality_service import CorpusQualityService
from backend.services.corpus_source_service import CorpusSourceService

router = APIRouter(
    prefix="/admin/corpus", tags=["admin-corpus"], dependencies=[Depends(require_admin)]
)


class SourceTransitionRequest(BaseModel):
    target_status: str = Field(min_length=1, max_length=40)
    reason: str = Field(default="", max_length=2000)


class OriginVerificationRequest(BaseModel):
    evidence: str = Field(min_length=1, max_length=4000)


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
