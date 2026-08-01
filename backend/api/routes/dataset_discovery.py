"""Phase 10 Live Dataset Discovery, Normalization & Comparison API.

Admin-only, CSRF-protected, under `/api/admin/dataset-discovery`.
Every mutation runs through the same repository/service layer as the
rest of the codebase, so the same guarantees apply here: no endpoint
downloads a file, imports a dataset, or grants a licence/RAG/training/
commercial approval -- a search session and its candidates are always
research artifacts for human review, never an import pipeline. See
docs/data_discovery/phase10_live_dataset_discovery_plan.md.
"""

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import Field

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.core.validation import DomainModel
from backend.database.repositories.external_dataset_discovery import (
    ExternalDatasetDiscoveryRepository,
)
from backend.services.external_dataset_comparison_service import ExternalDatasetComparisonService
from backend.services.external_dataset_search_service import (
    ExternalDatasetCandidateService,
    ExternalDatasetSearchExecutionService,
    ExternalDatasetSearchSessionService,
)

router = APIRouter(
    prefix="/admin/dataset-discovery",
    tags=["dataset-discovery"],
    dependencies=[Depends(require_admin)],
)


def session_service(settings) -> ExternalDatasetSearchSessionService:
    return ExternalDatasetSearchSessionService(settings)


def execution_service(settings) -> ExternalDatasetSearchExecutionService:
    return ExternalDatasetSearchExecutionService(settings)


def candidate_service(settings) -> ExternalDatasetCandidateService:
    return ExternalDatasetCandidateService(settings)


def comparison_service(settings) -> ExternalDatasetComparisonService:
    return ExternalDatasetComparisonService(discovery_repository(settings))


def discovery_repository(settings) -> ExternalDatasetDiscoveryRepository:
    return ExternalDatasetDiscoveryRepository(settings.resolved_database_path)


class SessionCreateRequest(DomainModel):
    title: str = Field(default="", max_length=300)


class RequirementsSetRequest(DomainModel):
    modality: str = "text"
    languages: list[str] = Field(default_factory=list)
    tasks: list[str] = Field(default_factory=list)
    intended_uses: list[str] = Field(default_factory=list)
    commercial_requirement: str = "unknown"
    domain_tags: list[str] = Field(default_factory=list)
    preferred_providers: list[str] = Field(default_factory=list)
    excluded_providers: list[str] = Field(default_factory=list)
    minimum_records: int | None = None
    maximum_download_size_bytes: int | None = None
    preferred_file_formats: list[str] = Field(default_factory=list)
    quality_preferences: dict[str, Any] = Field(default_factory=dict)
    licence_preferences: dict[str, Any] = Field(default_factory=dict)
    free_text_requirement: str = Field(default="", max_length=2000)
    inferred_fields: dict[str, Any] = Field(default_factory=dict)
    confirmed_fields: dict[str, Any] = Field(default_factory=dict)
    unknown_fields: list[str] = Field(default_factory=list)


class ManualCandidateCreateRequest(DomainModel):
    canonical_name: str = Field(min_length=1, max_length=300)
    normalized_name: str | None = Field(default=None, max_length=300)
    description: str = Field(default="", max_length=4000)
    organization: str | None = Field(default=None, max_length=300)
    modality: str | None = None
    languages: list[str] = Field(default_factory=list)
    tasks: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    declared_licence: str | None = Field(default=None, max_length=200)
    record_count: int | None = None
    download_size_bytes: int | None = None
    file_formats: list[str] = Field(default_factory=list)
    dataset_card_url: str | None = Field(default=None, max_length=500)
    homepage_url: str | None = Field(default=None, max_length=500)
    repository_url: str | None = Field(default=None, max_length=500)
    gated: bool = False
    private: bool = False
    authentication_required: bool = False
    version: str | None = Field(default=None, max_length=100)
    revision: str | None = Field(default=None, max_length=100)
    last_modified_at: str | None = None


class ComparisonCreateRequest(DomainModel):
    candidate_ids: list[str] = Field(min_length=2, max_length=5)


@router.post("/sessions")
async def create_session(
    payload: SessionCreateRequest, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return session_service(settings).create_session(
        title=payload.title, admin_id=admin.admin.public_id
    )


@router.get("/sessions")
async def list_sessions(
    settings: SettingsDependency,
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
) -> dict[str, Any]:
    offset = (page - 1) * page_size
    items = session_service(settings).list_sessions(status=status, limit=page_size, offset=offset)
    return {"items": items, "page": page, "page_size": page_size}


@router.get("/sessions/{public_id}")
async def get_session(public_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return session_service(settings).get_session(public_id)


@router.get("/sessions/{public_id}/requirements")
async def get_requirements(public_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return session_service(settings).get_requirements(public_id) or {}


@router.put("/sessions/{public_id}/requirements")
async def set_requirements(
    public_id: str,
    payload: RequirementsSetRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return session_service(settings).set_requirements(
        public_id, payload.model_dump(), admin_id=admin.admin.public_id
    )


@router.post("/sessions/{public_id}/search")
async def run_search(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return execution_service(settings).run_search(public_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{public_id}/cancel")
async def cancel_session(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return session_service(settings).cancel_session(public_id, admin_id=admin.admin.public_id)


@router.get("/sessions/{public_id}/candidates")
async def list_candidates(
    public_id: str, settings: SettingsDependency, include_excluded: bool = True
) -> dict[str, Any]:
    return {
        "items": candidate_service(settings).list_candidates(
            public_id, include_excluded=include_excluded
        )
    }


@router.post("/sessions/{public_id}/candidates")
async def add_manual_candidate(
    public_id: str,
    payload: ManualCandidateCreateRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    values = payload.model_dump()
    if not values.get("normalized_name"):
        values.pop("normalized_name", None)
    return candidate_service(settings).add_manual_candidate(
        public_id, values, admin_id=admin.admin.public_id
    )


@router.get("/candidates/{candidate_public_id}")
async def get_candidate(candidate_public_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return candidate_service(settings).get_candidate_detail(candidate_public_id)


@router.post("/candidates/{candidate_public_id}/exclude")
async def exclude_candidate(
    candidate_public_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return candidate_service(settings).exclude_candidate(
        candidate_public_id, admin_id=admin.admin.public_id
    )


@router.post("/candidates/{candidate_public_id}/restore")
async def restore_candidate(
    candidate_public_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return candidate_service(settings).restore_candidate(
        candidate_public_id, admin_id=admin.admin.public_id
    )


@router.get("/sessions/{public_id}/provider-runs")
async def list_provider_runs(public_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return {"items": discovery_repository(settings).list_provider_runs(public_id)}


@router.get("/sessions/{public_id}/events")
async def list_events(
    public_id: str, settings: SettingsDependency, limit: int = Query(default=50, ge=1, le=200)
) -> dict[str, Any]:
    return {"items": discovery_repository(settings).list_events(public_id, limit=limit)}


@router.post("/sessions/{public_id}/comparisons")
async def create_comparison(
    public_id: str,
    payload: ComparisonCreateRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return comparison_service(settings).create_comparison(
        public_id, payload.candidate_ids, created_by_admin_public_id=admin.admin.public_id
    )


@router.get("/sessions/{public_id}/comparisons")
async def list_comparisons(public_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return {"items": discovery_repository(settings).list_comparisons(public_id)}


@router.get("/comparisons/{comparison_public_id}")
async def get_comparison(comparison_public_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return discovery_repository(settings).get_comparison(comparison_public_id)
