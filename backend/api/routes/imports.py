"""Authenticated, CSRF-protected dataset import and preview endpoints."""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import Response
from pydantic import ValidationError as PydanticValidationError

from backend.api.auth import AdminDependency, CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.core.validation import LanguageCode
from backend.database.repositories.base import ValidationError
from backend.models.domain import DatasetRecordType
from backend.models.imports import ImportConfirm, ImportMode, MappingUpdate
from backend.services.import_service import ImportService

router = APIRouter(
    prefix="/admin/datasets/imports",
    tags=["admin-dataset-imports"],
    dependencies=[Depends(require_admin)],
)


def service(settings) -> ImportService:
    return ImportService(settings)


@router.post("")
async def upload_import(
    settings: SettingsDependency,
    admin: CsrfDependency,
    file: Annotated[UploadFile, File()],
    record_type: Annotated[str, Form()] = "instruction",
    default_language: Annotated[str, Form()] = "unknown",
    import_mode: Annotated[str, Form()] = "create_only",
    encoding: Annotated[str, Form()] = "utf-8",
    field_mapping_json: Annotated[str, Form()] = "{}",
    parser_options_json: Annotated[str, Form()] = "{}",
):
    import_service = service(settings)
    try:
        field_mapping = json.loads(field_mapping_json)
        parser_options = json.loads(parser_options_json)
        if not isinstance(field_mapping, dict) or not isinstance(parser_options, dict):
            raise ValueError("mapping values must be objects")
        mapping = MappingUpdate(field_mapping=field_mapping, parser_options=parser_options)
        return await import_service.receive_upload(
            file,
            record_type=DatasetRecordType(record_type).value,
            default_language=LanguageCode(default_language).value,
            import_mode=ImportMode(import_mode).value,
            field_mapping=mapping.field_mapping,
            parser_options=mapping.parser_options,
            encoding=encoding,
            admin_id=admin.admin.public_id,
        )
    except ValidationError as exc:
        import_service.audit_upload_rejection(
            admin.admin.public_id, file.filename, type(exc).__name__
        )
        raise
    except (json.JSONDecodeError, PydanticValidationError, ValueError, TypeError) as exc:
        import_service.audit_upload_rejection(
            admin.admin.public_id, file.filename, type(exc).__name__
        )
        raise ValidationError(
            "invalid import mapping, parser option, record type, or language"
        ) from exc


@router.get("")
async def list_imports(
    settings: SettingsDependency,
    status: str | None = None,
    file_type: str | None = None,
    search: str | None = Query(default=None, max_length=200),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
):
    return service(settings).list_jobs(
        status=status, file_type=file_type, search=search, page=page, page_size=page_size
    )


@router.get("/{public_id}")
async def get_import(public_id: str, settings: SettingsDependency):
    return service(settings).get_job(public_id)


@router.get("/{public_id}/rows")
async def import_rows(
    public_id: str,
    settings: SettingsDependency,
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    return service(settings).rows(public_id, status, page, page_size)


@router.post("/{public_id}/parse")
async def parse_import(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).parse(public_id, admin.admin.public_id)


@router.patch("/{public_id}/mapping")
async def update_mapping(
    public_id: str,
    payload: MappingUpdate,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return service(settings).update_mapping(public_id, payload, admin.admin.public_id)


@router.post("/{public_id}/confirm")
async def confirm_import(
    public_id: str,
    payload: ImportConfirm,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return service(settings).confirm(public_id, payload, admin.admin.public_id)


@router.post("/{public_id}/cancel")
async def cancel_import(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).cancel(public_id, admin.admin.public_id)


@router.get("/{public_id}/events")
async def import_events(public_id: str, settings: SettingsDependency):
    return {"items": service(settings).events(public_id)}


@router.get("/{public_id}/report")
async def import_report(public_id: str, settings: SettingsDependency, admin: AdminDependency):
    report = service(settings).report_csv(public_id, admin.admin.public_id)
    return Response(
        content=report,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="brud-import-{public_id}.csv"'},
    )
