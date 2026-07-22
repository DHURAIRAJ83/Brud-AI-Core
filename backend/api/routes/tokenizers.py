"""Authenticated tokenizer training and registry APIs."""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.database.repositories.tokenizers import TokenizerRepository
from backend.models.tokenizers import (
    AssignmentPatch,
    CompareRequest,
    DecodeRequest,
    EncodeRequest,
    TokenizerExportCreate,
    TokenizerFamilyCreate,
    TokenizerFamilyPatch,
    TokenizerJobCreate,
    TokenizerVersionCreate,
    TokenizerVersionPatch,
)
from backend.services.tokenizer_registry import TokenizerService

router = APIRouter(
    prefix="/admin/tokenizers", tags=["admin-tokenizers"], dependencies=[Depends(require_admin)]
)


def service(settings) -> TokenizerService:
    return TokenizerService(TokenizerRepository(settings.resolved_database_path), settings)


@router.get("/capabilities")
async def capabilities(settings: SettingsDependency):
    return service(settings).capabilities()


@router.get("/families")
async def families(
    settings: SettingsDependency,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
):
    return service(settings).list_families(page, page_size)


@router.post("/families")
async def create_family(
    payload: TokenizerFamilyCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).create_family(payload, admin.admin.public_id)


@router.get("/families/{public_id}")
async def family(public_id: str, settings: SettingsDependency):
    return service(settings).get_family(public_id)


@router.patch("/families/{public_id}")
async def patch_family(
    public_id: str,
    payload: TokenizerFamilyPatch,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return service(settings).patch_family(public_id, payload, admin.admin.public_id)


@router.get("/versions")
async def versions(
    settings: SettingsDependency,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
):
    return service(settings).list_versions(page, page_size)


@router.post("/versions")
async def create_version(
    payload: TokenizerVersionCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).create_version(payload, admin.admin.public_id)


@router.get("/versions/{public_id}")
async def version(public_id: str, settings: SettingsDependency):
    return service(settings).get_version(public_id)


@router.patch("/versions/{public_id}")
async def patch_version(
    public_id: str,
    payload: TokenizerVersionPatch,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return service(settings).patch_version(public_id, payload, admin.admin.public_id)


@router.post("/versions/{public_id}/activate")
async def activate(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).activate(public_id, admin.admin.public_id)


@router.post("/versions/{public_id}/retire")
async def retire(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).retire(public_id, admin.admin.public_id)


@router.post("/versions/{public_id}/verify")
async def verify_version(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).verify(public_id, admin.admin.public_id)


@router.post("/jobs")
async def create_job(
    payload: TokenizerJobCreate,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return service(settings).create_job(payload, admin.admin.public_id)


@router.get("/jobs")
async def jobs(
    settings: SettingsDependency,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
):
    return service(settings).list_jobs(page, page_size)


@router.get("/jobs/{public_id}")
async def job(public_id: str, settings: SettingsDependency):
    return service(settings).get_job(public_id)


@router.post("/jobs/{public_id}/build-corpus")
async def build_corpus(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).build_corpus(public_id, admin.admin.public_id)


@router.post("/jobs/{public_id}/dry-run")
async def dry_run(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).dry_run(public_id, admin.admin.public_id)


@router.post("/jobs/{public_id}/train")
async def train(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).train(public_id, admin.admin.public_id)


@router.post("/jobs/{public_id}/evaluate")
async def evaluate_job(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    job_payload = service(settings).get_job(public_id)
    return service(settings).evaluate(
        job_payload["tokenizer_version_public_id"],
        admin.admin.public_id,
    )


@router.post("/jobs/{public_id}/cancel")
async def cancel(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    _ = admin
    return service(settings).get_job(public_id)


@router.get("/jobs/{public_id}/events")
async def events(public_id: str, settings: SettingsDependency):
    return service(settings).job_events(public_id)


@router.get("/versions/{public_id}/evaluations")
async def evaluations(public_id: str, settings: SettingsDependency):
    return service(settings).evaluations(public_id)


@router.post("/versions/{public_id}/evaluations")
async def create_evaluation(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).evaluate(public_id, admin.admin.public_id)


@router.get("/evaluations/{evaluation_public_id}")
async def evaluation(evaluation_public_id: str, settings: SettingsDependency):
    items = service(settings).evaluation_results(evaluation_public_id)
    return {"public_id": evaluation_public_id, "results": items["items"]}


@router.get("/evaluations/{evaluation_public_id}/results")
async def evaluation_results(evaluation_public_id: str, settings: SettingsDependency):
    return service(settings).evaluation_results(evaluation_public_id)


@router.post("/versions/{public_id}/encode")
async def encode(public_id: str, payload: EncodeRequest, settings: SettingsDependency):
    return service(settings).encode(public_id, payload.text)


@router.post("/versions/{public_id}/decode")
async def decode(public_id: str, payload: DecodeRequest, settings: SettingsDependency):
    return service(settings).decode(public_id, payload.ids)


@router.post("/compare")
async def compare(payload: CompareRequest, settings: SettingsDependency):
    return service(settings).compare(
        payload.left_version_public_id, payload.right_version_public_id, payload.sample_text
    )


@router.get("/assignments")
async def assignments(settings: SettingsDependency):
    return service(settings).assignments()


@router.patch("/assignments/{assignment_key}")
async def patch_assignment(
    assignment_key: str,
    payload: AssignmentPatch,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return service(settings).patch_assignment(assignment_key, payload, admin.admin.public_id)


@router.post("/versions/{public_id}/exports")
async def create_export(
    public_id: str,
    payload: TokenizerExportCreate,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return service(settings).export(public_id, payload.export_format, admin.admin.public_id)


@router.get("/versions/{public_id}/exports")
async def exports(public_id: str, settings: SettingsDependency):
    return service(settings).list_exports(public_id)


@router.get("/exports/{export_public_id}")
async def export(export_public_id: str, settings: SettingsDependency):
    return service(settings).get_export(export_public_id)


@router.get("/exports/{export_public_id}/download")
async def download_export(export_public_id: str, settings: SettingsDependency):
    path = service(settings).export_file(export_public_id)
    return Response(
        content=path.read_bytes(),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="artifact_manifest.json"'},
    )


@router.post("/exports/{export_public_id}/verify")
async def verify_export(export_public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).verify_export(export_public_id, admin.admin.public_id)
