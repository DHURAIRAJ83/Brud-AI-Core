"""Authenticated and CSRF-protected document processing endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import Response

from backend.api.auth import AdminDependency, CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.core.validation import LanguageCode
from backend.database.repositories.base import ConflictError, ValidationError
from backend.models.documents import (
    CandidateImport,
    CandidatePatch,
    ExtractionStrategy,
    PageEdit,
    ProcessRequest,
    SegmentRequest,
)
from backend.services.document_service import DocumentService

router = APIRouter(
    prefix="/admin/documents",
    tags=["admin-documents"],
    dependencies=[Depends(require_admin)],
)


def service(settings) -> DocumentService:
    return DocumentService(settings)


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
    return service(settings).edit_page(
        public_id, page_number, payload.cleaned_text, admin.admin.public_id
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
