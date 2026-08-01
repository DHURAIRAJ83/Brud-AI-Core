"""Authenticated and CSRF-protected document processing endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import Response

from backend.api.auth import AdminDependency, CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.core.validation import LanguageCode
from backend.database.repositories.base import ConflictError, ValidationError
from backend.models.documents import (
    ApplyCleanupRequest,
    CandidateImport,
    CandidatePatch,
    ConfirmBuildRequest,
    DatasetVersionProposalRequest,
    ExtractionRerunRequest,
    ExtractionStrategy,
    OcrRerunRequest,
    PageEdit,
    ProcessRequest,
    RepeatedElementReview,
    ReviewActionRequest,
    SecurityFindingReviewAction,
    SegmentRequest,
    SftBulkApprovalRequest,
    SftCandidateGenerationRequest,
    SftCandidateReviewAction,
    SftExportRequest,
    SftHandoffIngestRequest,
    SourceLinkRequest,
    TamilCorrectionRuleCreate,
    TamilCorrectionRuleReviewAction,
    TamilQualityReviewAction,
)
from backend.services.document_content_classification_service import (
    DocumentContentClassificationService,
)
from backend.services.document_security_review_service import DocumentSecurityReviewService
from backend.services.document_service import DocumentService
from backend.services.document_sft_candidate_service import DocumentSftCandidateGenerationService
from backend.services.document_sft_dataset_handoff_service import (
    DocumentSftDatasetHandoffService,
)
from backend.services.document_sft_export_service import DocumentSftExportService
from backend.services.document_tamil_correction_registry_service import (
    DocumentTamilCorrectionRegistryService,
)
from backend.services.document_tamil_quality_service import DocumentTamilQualityService
from backend.services.document_workspace_service import (
    DocumentCleanupService,
    DocumentPageReviewService,
    DocumentPageRevisionService,
    PDFResearchWorkspaceService,
)

router = APIRouter(
    prefix="/admin/documents",
    tags=["admin-documents"],
    dependencies=[Depends(require_admin)],
)


def service(settings) -> DocumentService:
    return DocumentService(settings)


def workspace_service(settings) -> PDFResearchWorkspaceService:
    return PDFResearchWorkspaceService(settings)


def revision_service(settings) -> DocumentPageRevisionService:
    return DocumentPageRevisionService(settings)


def review_service(settings) -> DocumentPageReviewService:
    return DocumentPageReviewService(settings)


def cleanup_service(settings) -> DocumentCleanupService:
    return DocumentCleanupService(settings)


def tamil_quality_service(settings) -> DocumentTamilQualityService:
    return DocumentTamilQualityService(settings)


def sft_candidate_service(settings) -> DocumentSftCandidateGenerationService:
    return DocumentSftCandidateGenerationService(settings)


def sft_export_service(settings) -> DocumentSftExportService:
    return DocumentSftExportService(settings)


def handoff_service(settings) -> DocumentSftDatasetHandoffService:
    return DocumentSftDatasetHandoffService(settings)


def classification_service(settings) -> DocumentContentClassificationService:
    return DocumentContentClassificationService(settings)


def security_service(settings) -> DocumentSecurityReviewService:
    return DocumentSecurityReviewService(settings)


tamil_correction_rules_router = APIRouter(
    prefix="/admin/document-tamil-correction-rules",
    tags=["admin-documents"],
    dependencies=[Depends(require_admin)],
)


def tamil_rules_service(settings) -> DocumentTamilCorrectionRegistryService:
    return DocumentTamilCorrectionRegistryService(settings)


@router.get("/capabilities")
async def capabilities(settings: SettingsDependency):
    return service(settings).capabilities()


@router.post("")
async def upload_document(
    settings: SettingsDependency,
    admin: CsrfDependency,
    file: Annotated[UploadFile, File()],
    extraction_strategy: Annotated[str, Form()] = "auto",
    language: Annotated[str, Form()] = "unknown",
):
    document_service = service(settings)
    try:
        return await document_service.upload(
            file,
            ExtractionStrategy(extraction_strategy).value,
            LanguageCode(language).value,
            admin.admin.public_id,
        )
    except ConflictError:
        raise
    except (ValidationError, ValueError) as exc:
        document_service.audit_rejection(admin.admin.public_id, file.filename, type(exc).__name__)
        raise


@router.get("")
async def documents(
    settings: SettingsDependency,
    status: str | None = None,
    search: str | None = Query(default=None, max_length=200),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
):
    return service(settings).list(status, search, page, page_size)


@router.get("/jobs/{job_public_id}")
async def processing_job(job_public_id: str, settings: SettingsDependency):
    return service(settings).job(job_public_id)


@router.get("/jobs/{job_public_id}/events")
async def processing_events(
    job_public_id: str,
    settings: SettingsDependency,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    return service(settings).events(job_public_id, page, page_size)


@router.get("/{public_id}")
async def document(public_id: str, settings: SettingsDependency):
    return service(settings).get(public_id)


@router.post("/{public_id}/analyze")
async def analyze(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).analyze(public_id, admin.admin.public_id)


@router.post("/{public_id}/process")
async def process(
    public_id: str, payload: ProcessRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).process(public_id, payload, admin.admin.public_id)


@router.post("/{public_id}/cancel")
async def cancel(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).state_action(public_id, "cancelled", admin.admin.public_id)


@router.post("/{public_id}/archive")
async def archive(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).state_action(public_id, "archived", admin.admin.public_id)


@router.get("/{public_id}/pages")
async def pages(
    public_id: str,
    settings: SettingsDependency,
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
):
    return service(settings).pages(public_id, status, page, page_size)


@router.post("/{public_id}/pages/reprocess")
async def reprocess_pages(
    public_id: str, payload: ProcessRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).process(public_id, payload, admin.admin.public_id, reprocess=True)


@router.get("/{public_id}/pages/{page_number}")
async def page(public_id: str, page_number: int, settings: SettingsDependency):
    return service(settings).page(public_id, page_number)


@router.patch("/{public_id}/pages/{page_number}")
async def edit_page(
    public_id: str,
    page_number: int,
    payload: PageEdit,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return revision_service(settings).save_draft(
        public_id,
        page_number,
        payload.cleaned_text,
        admin.admin.public_id,
        change_summary=payload.change_summary,
        correction_types=payload.correction_types,
    )


@router.post("/{public_id}/pages/{page_number}/reprocess")
async def reprocess_page(
    public_id: str,
    page_number: int,
    payload: ProcessRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    payload.pages = [page_number]
    return service(settings).process(public_id, payload, admin.admin.public_id, reprocess=True)


@router.post("/{public_id}/segment")
async def segment(
    public_id: str, payload: SegmentRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).segment(public_id, payload, admin.admin.public_id)


@router.get("/{public_id}/candidates")
async def candidates(
    public_id: str,
    settings: SettingsDependency,
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    return service(settings).candidates(public_id, status, page, page_size)


@router.get("/{public_id}/candidates/{candidate_public_id}")
async def candidate(public_id: str, candidate_public_id: str, settings: SettingsDependency):
    return service(settings).candidate(public_id, candidate_public_id)


@router.patch("/{public_id}/candidates/{candidate_public_id}")
async def edit_candidate(
    public_id: str,
    candidate_public_id: str,
    payload: CandidatePatch,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return service(settings).edit_candidate(
        public_id, candidate_public_id, payload, admin.admin.public_id
    )


@router.post("/{public_id}/candidates/{candidate_public_id}/select")
async def select_candidate(
    public_id: str, candidate_public_id: str, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).candidate_action(
        public_id, candidate_public_id, "selected", admin.admin.public_id
    )


@router.post("/{public_id}/candidates/{candidate_public_id}/reject")
async def reject_candidate(
    public_id: str, candidate_public_id: str, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).candidate_action(
        public_id, candidate_public_id, "rejected", admin.admin.public_id
    )


@router.post("/{public_id}/candidates/import")
async def import_candidates(
    public_id: str,
    payload: CandidateImport,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return service(settings).import_candidates(public_id, admin.admin.public_id)


@router.get("/{public_id}/jobs")
async def jobs(
    public_id: str,
    settings: SettingsDependency,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
):
    return service(settings).jobs(public_id, page, page_size)


@router.get("/{public_id}/report")
async def report(public_id: str, settings: SettingsDependency, admin: AdminDependency):
    value = service(settings).report_csv(public_id, admin.admin.public_id)
    return Response(
        content=value,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="brud-document-{public_id}.csv"'},
    )


# --- Phase 4: PDF Research Workspace (additive) -----------------------------


@router.get("/{public_id}/workspace")
async def workspace(public_id: str, settings: SettingsDependency):
    return workspace_service(settings).workspace(public_id)


@router.post("/{public_id}/source-link")
async def link_source(
    public_id: str, payload: SourceLinkRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return workspace_service(settings).link_source(
        public_id, payload.source_public_id, admin.admin.public_id
    )


@router.get("/{public_id}/pages/{page_number}/image")
async def page_image(public_id: str, page_number: int, settings: SettingsDependency):
    value = workspace_service(settings).render_page_image(public_id, page_number)
    return Response(content=value, media_type="image/png")


@router.get("/{public_id}/pages/{page_number}/extractions")
async def page_extractions(public_id: str, page_number: int, settings: SettingsDependency):
    return workspace_service(settings).extraction_history(public_id, page_number)


@router.get("/{public_id}/pages/{page_number}/revisions")
async def page_revisions(public_id: str, page_number: int, settings: SettingsDependency):
    return revision_service(settings).revisions(public_id, page_number)


@router.post("/{public_id}/pages/{page_number}/revisions/{revision_number}/restore")
async def restore_page_revision(
    public_id: str,
    page_number: int,
    revision_number: int,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return revision_service(settings).restore_revision(
        public_id, page_number, revision_number, admin.admin.public_id
    )


@router.post("/{public_id}/pages/{page_number}/approve")
async def approve_page(
    public_id: str,
    page_number: int,
    payload: ReviewActionRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return review_service(settings).approve(
        public_id, page_number, admin.admin.public_id, payload.notes
    )


@router.post("/{public_id}/pages/{page_number}/reject")
async def reject_page(
    public_id: str,
    page_number: int,
    payload: ReviewActionRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return review_service(settings).reject(
        public_id, page_number, admin.admin.public_id, payload.notes
    )


@router.post("/{public_id}/pages/{page_number}/exclude")
async def exclude_page(
    public_id: str,
    page_number: int,
    payload: ReviewActionRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return review_service(settings).exclude(
        public_id, page_number, admin.admin.public_id, payload.notes
    )


@router.post("/{public_id}/pages/{page_number}/reopen")
async def reopen_page(
    public_id: str,
    page_number: int,
    payload: ReviewActionRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return review_service(settings).reopen(
        public_id, page_number, admin.admin.public_id, payload.notes
    )


@router.post("/{public_id}/pages/{page_number}/request-correction")
async def request_page_correction(
    public_id: str,
    page_number: int,
    payload: ReviewActionRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return review_service(settings).request_correction(
        public_id, page_number, admin.admin.public_id, payload.notes
    )


@router.post("/{public_id}/pages/{page_number}/request-ocr-rerun")
async def request_page_ocr_rerun(
    public_id: str,
    page_number: int,
    payload: OcrRerunRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return review_service(settings).request_ocr_rerun(
        public_id, page_number, admin.admin.public_id, payload.ocr_language
    )


@router.post("/{public_id}/pages/{page_number}/request-extraction-rerun")
async def request_page_extraction_rerun(
    public_id: str,
    page_number: int,
    payload: ExtractionRerunRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return review_service(settings).request_extraction_rerun(
        public_id, page_number, admin.admin.public_id, payload.strategy.value
    )


@router.get("/{public_id}/pages/{page_number}/review-events")
async def page_review_events(public_id: str, page_number: int, settings: SettingsDependency):
    return review_service(settings).review_events(public_id, page_number)


@router.get("/{public_id}/review-summary")
async def review_summary(public_id: str, settings: SettingsDependency):
    return review_service(settings).review_summary(public_id)


@router.get("/{public_id}/pages/{page_number}/cleanup-suggestions")
async def page_cleanup_suggestions(public_id: str, page_number: int, settings: SettingsDependency):
    return cleanup_service(settings).suggestions(public_id, page_number)


@router.post("/{public_id}/pages/{page_number}/apply-cleanup")
async def apply_page_cleanup(
    public_id: str,
    page_number: int,
    payload: ApplyCleanupRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return cleanup_service(settings).apply_suggestions(
        public_id,
        page_number,
        [item.model_dump() for item in payload.suggestions],
        admin.admin.public_id,
    )


@router.post("/{public_id}/repeated-elements/detect")
async def detect_repeated_elements(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
):
    return cleanup_service(settings).detect_repeated_elements(public_id)


@router.get("/{public_id}/repeated-elements")
async def repeated_elements(
    public_id: str, settings: SettingsDependency, status: str | None = None
):
    return cleanup_service(settings).list_repeated_elements(public_id, status)


@router.post("/{public_id}/repeated-elements/{element_public_id}/review")
async def review_repeated_element(
    public_id: str,
    element_public_id: str,
    payload: RepeatedElementReview,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return cleanup_service(settings).review_repeated_element(
        public_id,
        element_public_id,
        payload.action,
        admin.admin.public_id,
        confirm=payload.confirm,
        target_pages=payload.target_pages,
    )


@router.post("/{public_id}/send-to-segmentation")
async def send_to_segmentation(
    public_id: str, payload: SegmentRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return workspace_service(settings).send_to_segmentation(
        public_id, payload, admin.admin.public_id
    )


# --- Tamil quality ------------------------------------------------------------------------


@router.post("/{public_id}/tamil-quality/detect")
async def detect_tamil_quality(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return tamil_quality_service(settings).detect(public_id, admin.admin.public_id)


@router.get("/{public_id}/tamil-quality")
async def tamil_quality_issues(
    public_id: str,
    settings: SettingsDependency,
    review_status: str | None = None,
    issue_type: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    return tamil_quality_service(settings).list_issues(
        public_id, page, page_size, review_status, issue_type
    )


@router.get("/{public_id}/tamil-quality/summary")
async def tamil_quality_summary(public_id: str, settings: SettingsDependency):
    return tamil_quality_service(settings).summary(public_id)


@router.post("/{public_id}/tamil-quality/{issue_public_id}/review")
async def review_tamil_quality_issue(
    public_id: str,
    issue_public_id: str,
    payload: TamilQualityReviewAction,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return tamil_quality_service(settings).review(
        public_id, issue_public_id, payload, admin.admin.public_id
    )


# --- SFT candidates -------------------------------------------------------------------------


@router.post("/{public_id}/sft-candidates/generate")
async def generate_sft_candidates(
    public_id: str,
    payload: SftCandidateGenerationRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return sft_candidate_service(settings).generate(public_id, payload, admin.admin.public_id)


@router.get("/{public_id}/sft-candidates")
async def sft_candidates(
    public_id: str,
    settings: SettingsDependency,
    quality_status: str | None = None,
    task: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    return sft_candidate_service(settings).list_candidates(
        public_id, page, page_size, quality_status, task
    )


@router.get("/{public_id}/sft-candidates/summary")
async def sft_candidates_summary(public_id: str, settings: SettingsDependency):
    return sft_candidate_service(settings).summary(public_id)


@router.post("/{public_id}/sft-candidates/{candidate_public_id}/review")
async def review_sft_candidate(
    public_id: str,
    candidate_public_id: str,
    payload: SftCandidateReviewAction,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return sft_candidate_service(settings).review(
        public_id, candidate_public_id, payload, admin.admin.public_id
    )


@router.post("/{public_id}/sft-candidates/bulk-approve")
async def bulk_approve_sft_candidates(
    public_id: str,
    payload: SftBulkApprovalRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return sft_candidate_service(settings).bulk_approve(public_id, payload, admin.admin.public_id)


# --- SFT export -----------------------------------------------------------------------------


@router.post("/{public_id}/sft-export")
async def export_sft_candidates(
    public_id: str, payload: SftExportRequest, settings: SettingsDependency, admin: CsrfDependency
):
    del payload
    return sft_export_service(settings).export(public_id, admin.admin.public_id)


@router.get("/{public_id}/sft-export/{export_public_id}")
async def get_sft_export(public_id: str, export_public_id: str, settings: SettingsDependency):
    del public_id
    return sft_export_service(settings).get_export(export_public_id)


@router.get("/{public_id}/sft-exports")
async def list_sft_exports(public_id: str, settings: SettingsDependency):
    return sft_export_service(settings).list_exports(public_id)


# --- Production integration: overview / generator eligibility ---------------------------------


@router.get("/{public_id}/overview")
async def document_overview(public_id: str, settings: SettingsDependency):
    document = service(settings).get(public_id)
    return {
        "document": document,
        "review_summary": review_service(settings).review_summary(public_id),
        "sft_candidates_summary": sft_candidate_service(settings).summary(public_id),
        "exports": sft_export_service(settings).list_exports(public_id),
        "handoffs": handoff_service(settings).list_handoffs_for_document(public_id),
        "content_classification_summary": classification_service(settings).summary(public_id),
        "security_summary": security_service(settings).summary(public_id),
    }


@router.get("/{public_id}/generator-eligibility")
async def generator_eligibility(public_id: str, settings: SettingsDependency):
    candidate_service = sft_candidate_service(settings)
    classification = classification_service(settings)
    with candidate_service.repository.transaction() as connection:
        document = candidate_service.repository.document(connection, public_id)
        by_chunk_type = {
            row["chunk_type"]: row["count"]
            for row in connection.execute(
                "SELECT chunk_type,COUNT(*) count FROM semantic_chunks WHERE "
                "document_source_id=? AND status='approved' GROUP BY chunk_type",
                (document["id"],),
            ).fetchall()
        }
    return {
        "document_public_id": public_id,
        "approved_chunk_counts_by_type": by_chunk_type,
        "content_classification_summary": classification.summary(public_id),
        "available_generators": [
            "definition", "explanation", "grammar", "fact_answer", "instruction_following",
            "summarization", "spelling_correction", "Tamil_to_English", "English_to_Tamil",
            "Tanglish_input_to_Tamil", "basic_math_reasoning",
        ],
        "deferred_generators": {
            "contextual_meaning": "no reviewed target-word/context/approved-meaning data exists",
            "multiple_meanings": "no reviewed multi-meaning source-linked data exists",
            "clarification_request": "no approved ambiguity registry exists",
            "computer_basics": "no stable, approved computer-domain chunk source exists",
            "safety_response": "no approved safety policy template source is wired",
            "grammar_correction": "only narrowly covered via reviewed Tamil quality issues",
        },
    }


# --- Production integration: dataset handoff ---------------------------------------------------


@router.post("/{public_id}/sft-export/{export_public_id}/validate")
async def validate_sft_export(
    public_id: str, export_public_id: str, settings: SettingsDependency, admin: AdminDependency
):
    del public_id, admin
    return sft_export_service(settings).validate_export(export_public_id)


@router.post("/{public_id}/sft-export/{export_public_id}/handoff-preview")
async def handoff_preview(
    public_id: str, export_public_id: str, settings: SettingsDependency, admin: AdminDependency
):
    del public_id, admin
    return handoff_service(settings).preview(export_public_id)


@router.post("/{public_id}/sft-export/{export_public_id}/handoff-ingest")
async def handoff_ingest(
    public_id: str,
    export_public_id: str,
    payload: SftHandoffIngestRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    del public_id, payload
    return handoff_service(settings).ingest(export_public_id, admin.admin.public_id)


@router.get("/{public_id}/handoffs")
async def list_handoffs(public_id: str, settings: SettingsDependency):
    return handoff_service(settings).list_handoffs_for_document(public_id)


@router.get("/{public_id}/handoffs/{handoff_public_id}")
async def get_handoff(public_id: str, handoff_public_id: str, settings: SettingsDependency):
    del public_id
    return handoff_service(settings).get_handoff(handoff_public_id)


@router.post("/{public_id}/handoffs/{handoff_public_id}/dataset-version-proposal")
async def propose_dataset_version(
    public_id: str,
    handoff_public_id: str,
    payload: DatasetVersionProposalRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    del public_id
    return handoff_service(settings).propose_dataset_version(
        handoff_public_id, payload.dataset_name, payload.dataset_version, admin.admin.public_id
    )


@router.get("/{public_id}/handoffs/{handoff_public_id}/split-preview")
async def handoff_split_preview(
    public_id: str, handoff_public_id: str, settings: SettingsDependency, admin: AdminDependency
):
    del public_id
    service_instance = handoff_service(settings)
    handoff = service_instance.get_handoff(handoff_public_id)
    if not handoff["dataset_build_public_id"]:
        raise ValidationError("no dataset-version build has been proposed for this handoff yet")
    return service_instance.preview_split(handoff["dataset_build_public_id"], admin.admin.public_id)


@router.post("/{public_id}/handoffs/{handoff_public_id}/confirm-build")
async def confirm_handoff_build(
    public_id: str,
    handoff_public_id: str,
    payload: ConfirmBuildRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    del public_id, payload
    service_instance = handoff_service(settings)
    handoff = service_instance.get_handoff(handoff_public_id)
    if not handoff["dataset_build_public_id"]:
        raise ValidationError("no dataset-version build has been proposed for this handoff yet")
    return service_instance.confirm_build(handoff["dataset_build_public_id"], admin.admin.public_id)


@router.get("/{public_id}/dataset-version-status")
async def dataset_version_status(public_id: str, settings: SettingsDependency):
    handoffs = handoff_service(settings).list_handoffs_for_document(public_id)["items"]
    for handoff in handoffs:
        if handoff["dataset_version_public_id"]:
            return {
                "status": handoff["status"],
                "dataset_version_public_id": handoff["dataset_version_public_id"],
                "dataset_build_public_id": handoff["dataset_build_public_id"],
            }
    return {"status": "no_dataset_version_proposed", "dataset_version_public_id": None}


# --- Production integration: content classification --------------------------------------------


@router.post("/{public_id}/content-classifications/scan")
async def scan_content_classifications(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
):
    return classification_service(settings).classify_document(public_id, admin.admin.public_id)


@router.get("/{public_id}/content-classifications")
async def content_classifications(
    public_id: str,
    settings: SettingsDependency,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    service_instance = classification_service(settings)
    with service_instance.repository.transaction() as connection:
        document = service_instance.repository.document(connection, public_id)
        total = connection.execute(
            "SELECT COUNT(*) FROM document_content_classifications WHERE document_source_id=?",
            (document["id"],),
        ).fetchone()[0]
        offset = (page - 1) * page_size
        rows = connection.execute(
            "SELECT * FROM document_content_classifications WHERE document_source_id=? "
            "ORDER BY page_number LIMIT ? OFFSET ?",
            (document["id"], page_size, offset),
        ).fetchall()
    from backend.database.repositories.documents import decode

    return {
        "items": [decode(row, {"table_data_json"}) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# --- Production integration: security / PII review ----------------------------------------------


@router.post("/{public_id}/security/scan")
async def scan_security_findings(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
):
    return security_service(settings).scan_document(public_id, admin.admin.public_id)


@router.get("/{public_id}/security-findings")
async def security_findings(
    public_id: str,
    settings: SettingsDependency,
    finding_type: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    return security_service(settings).list_findings(public_id, page, page_size, finding_type)


@router.get("/{public_id}/pii-findings")
async def pii_findings(
    public_id: str,
    settings: SettingsDependency,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    result = security_service(settings).list_findings(public_id, page, page_size)
    result["items"] = [
        item for item in result["items"] if item["finding_type"].startswith("pii_")
    ]
    return result


@router.post("/{public_id}/security/{finding_public_id}/review")
async def review_security_finding(
    public_id: str,
    finding_public_id: str,
    payload: SecurityFindingReviewAction,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return security_service(settings).review(
        public_id, finding_public_id, payload.action, admin.admin.public_id
    )


# --- Production integration: Tamil correction rules (global registry) --------------------------


@tamil_correction_rules_router.get("")
async def list_tamil_correction_rules(
    settings: SettingsDependency,
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    return tamil_rules_service(settings).list_rules(page, page_size, status)


@tamil_correction_rules_router.post("")
async def create_tamil_correction_rule(
    payload: TamilCorrectionRuleCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return tamil_rules_service(settings).create_rule(
        incorrect_form=payload.incorrect_form,
        approved_correction=payload.approved_correction,
        issue_category=payload.issue_category,
        evidence=payload.evidence,
        confidence_band=payload.confidence_band,
        meaning_change_risk=payload.meaning_change_risk,
        admin_id=admin.admin.public_id,
    )


@tamil_correction_rules_router.get("/{rule_public_id}")
async def get_tamil_correction_rule(rule_public_id: str, settings: SettingsDependency):
    return tamil_rules_service(settings).get_rule(rule_public_id)


@tamil_correction_rules_router.get("/{rule_public_id}/history")
async def tamil_correction_rule_history(rule_public_id: str, settings: SettingsDependency):
    return tamil_rules_service(settings).review_history(rule_public_id)


@tamil_correction_rules_router.post("/{rule_public_id}/review")
async def review_tamil_correction_rule(
    rule_public_id: str,
    payload: TamilCorrectionRuleReviewAction,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return tamil_rules_service(settings).transition(
        rule_public_id, payload.action, admin.admin.public_id, payload.notes
    )
