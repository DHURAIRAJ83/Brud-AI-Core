"""Phase 11 Licence Evidence, Terms Snapshot & Dataset Verification API.

Admin-only, CSRF-protected, under `/api/admin/dataset-verification`.
No endpoint here ever downloads a dataset payload file, imports
records, activates RAG, creates a training dataset version, starts
training, or releases a model -- a verification case only ever
produces an evidence-backed record for human review. See
docs/data_verification/phase11_licence_evidence_verification_plan.md.
"""

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import Field

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.core.validation import DomainModel
from backend.database.repositories.dataset_verification import DatasetVerificationRepository
from backend.services.dataset_verification_case_service import ExternalDatasetVerificationService
from backend.services.dataset_verification_evidence_service import (
    ExternalDatasetEvidenceService,
    ExternalDatasetIdentityVerificationService,
    ExternalDatasetLicenceService,
    ExternalDatasetTermsService,
)
from backend.services.dataset_verification_permission_service import (
    ExternalDatasetPermissionAssessmentService,
    ExternalDatasetUpstreamReviewService,
)
from backend.services.dataset_verification_report_service import (
    ExternalDatasetConflictService,
    ExternalDatasetReverificationService,
    ExternalDatasetVerificationReportService,
    ExternalDatasetWithdrawalService,
)
from backend.services.dataset_verification_source_rights_service import (
    ExternalDatasetSourceRightsIntegrationService,
)

router = APIRouter(
    prefix="/admin/dataset-verification",
    tags=["dataset-verification"],
    dependencies=[Depends(require_admin)],
)


def repository(settings: SettingsDependency) -> DatasetVerificationRepository:
    return DatasetVerificationRepository(settings.resolved_database_path)


def case_service(settings) -> ExternalDatasetVerificationService:
    return ExternalDatasetVerificationService(settings)


def evidence_service(settings) -> ExternalDatasetEvidenceService:
    return ExternalDatasetEvidenceService(settings)


def identity_service(settings) -> ExternalDatasetIdentityVerificationService:
    return ExternalDatasetIdentityVerificationService(settings)


def licence_service(settings) -> ExternalDatasetLicenceService:
    return ExternalDatasetLicenceService(settings)


def terms_service(settings) -> ExternalDatasetTermsService:
    return ExternalDatasetTermsService(settings)


def permission_service(settings) -> ExternalDatasetPermissionAssessmentService:
    return ExternalDatasetPermissionAssessmentService(settings)


def upstream_service(settings) -> ExternalDatasetUpstreamReviewService:
    return ExternalDatasetUpstreamReviewService(settings)


def conflict_service(settings) -> ExternalDatasetConflictService:
    return ExternalDatasetConflictService(settings)


def report_service(settings) -> ExternalDatasetVerificationReportService:
    return ExternalDatasetVerificationReportService(settings)


def reverification_service(settings) -> ExternalDatasetReverificationService:
    return ExternalDatasetReverificationService(settings)


def withdrawal_service(settings) -> ExternalDatasetWithdrawalService:
    return ExternalDatasetWithdrawalService(settings)


def source_rights_service(settings) -> ExternalDatasetSourceRightsIntegrationService:
    return ExternalDatasetSourceRightsIntegrationService(settings)


# -- request models --------------------------------------------------------------


class CaseCreateRequest(DomainModel):
    candidate_public_id: str
    search_session_public_id: str | None = None
    verification_scope: str = Field(default="", max_length=2000)
    force_new_version: bool = False


class EvidenceCollectRequest(DomainModel):
    evidence_type: str
    source_url: str = Field(max_length=2000)
    provider_public_id: str | None = None
    authority_level: str | None = None


class EvidenceManualRequest(DomainModel):
    evidence_type: str
    content_text: str = Field(min_length=1, max_length=200_000)
    source_url: str | None = Field(default=None, max_length=2000)
    authority_level: str = "manual_unverified"
    ocr_derived: bool = False


class IdentityManualSignalRequest(DomainModel):
    signal_type: str
    expected_value: str | None = Field(default=None, max_length=2000)
    observed_value: str | None = Field(default=None, max_length=2000)
    matched: bool
    reason: str = Field(min_length=1, max_length=2000)
    evidence_snapshot_public_id: str | None = None


class PermissionReviewRequest(DomainModel):
    status: str
    reason: str = Field(min_length=1, max_length=2000)
    conditions: dict[str, Any] = Field(default_factory=dict)


class CommercialUseAssessRequest(DomainModel):
    intended_use_category: str


class UpstreamSourceCreateRequest(DomainModel):
    upstream_name: str = Field(min_length=1, max_length=300)
    upstream_url: str | None = Field(default=None, max_length=2000)
    upstream_organization: str | None = Field(default=None, max_length=300)
    upstream_licence: str | None = Field(default=None, max_length=300)
    upstream_terms: str | None = Field(default=None, max_length=200_000)
    relationship_type: str = "unknown"
    coverage_notes: str = Field(default="", max_length=2000)


class UpstreamVerifyRequest(DomainModel):
    verification_status: str


class ConflictResolveRequest(DomainModel):
    resolution_status: str
    resolution_reason: str = Field(min_length=1, max_length=2000)


class WithdrawalNoticeCreateRequest(DomainModel):
    notice_type: str
    source_url: str | None = Field(default=None, max_length=2000)
    notice_text: str = Field(default="", max_length=200_000)
    effective_at: str | None = None


# -- cases --------------------------------------------------------------------------


@router.get("/overview")
async def get_overview(settings: SettingsDependency) -> dict[str, Any]:
    return case_service(settings).overview()


@router.post("/cases")
async def create_case(
    payload: CaseCreateRequest, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return case_service(settings).create_case(
        candidate_public_id=payload.candidate_public_id,
        search_session_public_id=payload.search_session_public_id,
        verification_scope=payload.verification_scope,
        force_new_version=payload.force_new_version,
        admin_id=admin.admin.public_id,
    )


@router.get("/cases")
async def list_cases(
    settings: SettingsDependency,
    status: str | None = None,
    candidate_public_id: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
) -> dict[str, Any]:
    offset = (page - 1) * page_size
    items = case_service(settings).list_cases(
        status=status, candidate_public_id=candidate_public_id, limit=page_size, offset=offset
    )
    return {"items": items, "page": page, "page_size": page_size}


@router.get("/cases/{case_public_id}")
async def get_case(case_public_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return case_service(settings).get_case(case_public_id)


@router.post("/cases/{case_public_id}/start")
async def start_case(
    case_public_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return case_service(settings).start(case_public_id, admin_id=admin.admin.public_id)


@router.post("/cases/{case_public_id}/cancel")
async def cancel_case(
    case_public_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return case_service(settings).cancel(case_public_id, admin_id=admin.admin.public_id)


# -- evidence ----------------------------------------------------------------------


@router.get("/cases/{case_public_id}/evidence")
async def list_evidence(
    case_public_id: str,
    settings: SettingsDependency,
    evidence_type: str | None = None,
    current_only: bool = True,
) -> dict[str, Any]:
    items = repository(settings).list_evidence_snapshots(
        case_public_id, evidence_type=evidence_type, current_only=current_only
    )
    return {"items": items}


@router.post("/cases/{case_public_id}/evidence/collect")
async def collect_evidence(
    case_public_id: str,
    payload: EvidenceCollectRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return evidence_service(settings).collect_evidence(
        case_public_id,
        evidence_type=payload.evidence_type,
        source_url=payload.source_url,
        provider_public_id=payload.provider_public_id,
        authority_level=payload.authority_level,
        admin_public_id=admin.admin.public_id,
    )


@router.post("/cases/{case_public_id}/evidence/manual")
async def add_manual_evidence(
    case_public_id: str,
    payload: EvidenceManualRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return evidence_service(settings).add_manual_evidence(
        case_public_id,
        evidence_type=payload.evidence_type,
        content_text=payload.content_text,
        source_url=payload.source_url,
        authority_level=payload.authority_level,
        ocr_derived=payload.ocr_derived,
        admin_public_id=admin.admin.public_id,
    )


@router.post("/cases/{case_public_id}/evidence/{evidence_public_id}/refresh")
async def refresh_evidence(
    case_public_id: str,
    evidence_public_id: str,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return evidence_service(settings).refresh_evidence(
        case_public_id, evidence_public_id, admin_public_id=admin.admin.public_id
    )


# -- identity ------------------------------------------------------------------------


@router.get("/cases/{case_public_id}/identity")
async def list_identity_checks(case_public_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return {"items": repository(settings).list_identity_checks(case_public_id)}


@router.post("/cases/{case_public_id}/identity/assess")
async def assess_identity(
    case_public_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return identity_service(settings).assess(case_public_id, admin_public_id=admin.admin.public_id)


@router.post("/cases/{case_public_id}/identity/manual-signal")
async def record_manual_identity_signal(
    case_public_id: str,
    payload: IdentityManualSignalRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return identity_service(settings).record_manual_signal(
        case_public_id,
        signal_type=payload.signal_type,
        expected_value=payload.expected_value,
        observed_value=payload.observed_value,
        matched=payload.matched,
        reason=payload.reason,
        evidence_snapshot_public_id=payload.evidence_snapshot_public_id,
        admin_public_id=admin.admin.public_id,
    )


# -- licence & terms -------------------------------------------------------------------


@router.post("/cases/{case_public_id}/licence/assess")
async def assess_licence(
    case_public_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return licence_service(settings).assess(case_public_id, admin_public_id=admin.admin.public_id)


@router.get("/cases/{case_public_id}/terms")
async def get_terms_summary(case_public_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return terms_service(settings).get_terms_snapshot_summary(case_public_id)


# -- permissions ---------------------------------------------------------------------


@router.get("/cases/{case_public_id}/permissions")
async def list_permissions(case_public_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return {"items": repository(settings).list_permission_assessments(case_public_id)}


@router.get("/cases/{case_public_id}/permissions/reviews")
async def list_permission_reviews(
    case_public_id: str, settings: SettingsDependency
) -> dict[str, Any]:
    return {"items": repository(settings).list_reviews(case_public_id)}


@router.post("/cases/{case_public_id}/permissions/assess")
async def assess_permissions(
    case_public_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    results = permission_service(settings).assess(
        case_public_id, admin_public_id=admin.admin.public_id
    )
    return {"items": results}


@router.post("/cases/{case_public_id}/permissions/commercial-use")
async def assess_commercial_use(
    case_public_id: str,
    payload: CommercialUseAssessRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return permission_service(settings).assess_commercial_use(
        case_public_id,
        intended_use_category=payload.intended_use_category,
        admin_public_id=admin.admin.public_id,
    )


@router.post("/cases/{case_public_id}/permissions/{permission_type}/review")
async def review_permission(
    case_public_id: str,
    permission_type: str,
    payload: PermissionReviewRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return permission_service(settings).review(
        case_public_id,
        permission_type,
        status=payload.status,
        reviewed_by=admin.admin.public_id,
        reason=payload.reason,
        conditions=payload.conditions,
    )


# -- upstream sources ------------------------------------------------------------------


@router.get("/cases/{case_public_id}/upstreams")
async def list_upstreams(case_public_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return {"items": repository(settings).list_upstream_sources(case_public_id)}


@router.post("/cases/{case_public_id}/upstreams")
async def add_upstream(
    case_public_id: str,
    payload: UpstreamSourceCreateRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return upstream_service(settings).add_upstream_source(
        case_public_id, payload.model_dump(), admin_public_id=admin.admin.public_id
    )


@router.post("/cases/{case_public_id}/upstreams/{upstream_public_id}/verify")
async def verify_upstream(
    case_public_id: str,
    upstream_public_id: str,
    payload: UpstreamVerifyRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return upstream_service(settings).verify_upstream_source(
        case_public_id,
        upstream_public_id,
        verification_status=payload.verification_status,
        admin_public_id=admin.admin.public_id,
    )


# -- conflicts -----------------------------------------------------------------------


@router.get("/cases/{case_public_id}/conflicts")
async def list_conflicts(case_public_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return {"items": repository(settings).list_conflict_events(case_public_id)}


@router.post("/cases/{case_public_id}/conflicts/detect")
async def detect_conflicts(
    case_public_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return {
        "items": conflict_service(settings).detect(
            case_public_id, admin_public_id=admin.admin.public_id
        )
    }


@router.post("/cases/{case_public_id}/conflicts/{conflict_public_id}/resolve")
async def resolve_conflict(
    case_public_id: str,
    conflict_public_id: str,
    payload: ConflictResolveRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return conflict_service(settings).resolve(
        case_public_id,
        conflict_public_id,
        resolution_status=payload.resolution_status,
        resolution_reason=payload.resolution_reason,
        admin_public_id=admin.admin.public_id,
    )


# -- finalize / report / reverify / withdrawal ------------------------------------------


@router.post("/cases/{case_public_id}/finalize")
async def finalize_case(
    case_public_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return report_service(settings).finalize(case_public_id, admin_public_id=admin.admin.public_id)


@router.get("/cases/{case_public_id}/report")
async def get_report(case_public_id: str, settings: SettingsDependency) -> dict[str, Any]:
    case = repository(settings).get_case(case_public_id)
    return {"locked_at": case["locked_at"], "status": case["status"], "report": case["report"]}


@router.post("/cases/{case_public_id}/reverify")
async def reverify_case(
    case_public_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return reverification_service(settings).check(
        case_public_id, admin_public_id=admin.admin.public_id
    )


@router.get("/cases/{case_public_id}/withdrawal-notices")
async def list_withdrawal_notices(
    case_public_id: str, settings: SettingsDependency
) -> dict[str, Any]:
    return {"items": repository(settings).list_withdrawal_notices(case_public_id)}


@router.post("/cases/{case_public_id}/withdrawal-notices")
async def record_withdrawal_notice(
    case_public_id: str,
    payload: WithdrawalNoticeCreateRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return withdrawal_service(settings).record_notice(
        case_public_id, payload.model_dump(), admin_public_id=admin.admin.public_id
    )


@router.get("/cases/{case_public_id}/events")
async def list_events(
    case_public_id: str, settings: SettingsDependency, limit: int = Query(default=100, ge=1, le=200)
) -> dict[str, Any]:
    return {"items": repository(settings).list_events(case_public_id, limit=limit)}


# -- Source & Rights Registry integration (propose-only, never a direct write) -------


@router.get("/cases/{case_public_id}/source-rights/existing-source")
async def find_existing_source(case_public_id: str, settings: SettingsDependency) -> dict[str, Any]:
    existing = source_rights_service(settings).find_existing_source(case_public_id)
    return {"existing_source": existing}


@router.post("/cases/{case_public_id}/source-rights/draft-proposal")
async def draft_source_rights_proposal(
    case_public_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return source_rights_service(settings).draft_source_update_proposal(
        case_public_id, admin_id=admin.admin.public_id
    )
