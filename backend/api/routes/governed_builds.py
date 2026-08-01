"""Phase 7 (Data Studio) Governed Build / Pipeline API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.core.json_utils import dumps_json
from backend.models.governed_builds import (
    CreateGovernedBuildRequest,
    RagIngestRequest,
    UpdateGovernedBuildRequest,
    UpdateSelectionRequest,
)
from backend.services.dataset_governance_manifest_service import DatasetGovernanceManifestService
from backend.services.governed_build_service import GovernedBuildService
from backend.services.governed_rag_handoff_service import GovernedRagHandoffService
from backend.services.governed_training_handoff_service import GovernedTrainingHandoffService
from backend.services.public_commercial_preflight_service import (
    PublicCommercialPreflightService,
)

router = APIRouter(
    prefix="/admin/governed-builds",
    tags=["admin-governed-builds"],
    dependencies=[Depends(require_admin)],
)


def build_service(settings) -> GovernedBuildService:
    return GovernedBuildService(settings)


def manifest_service(settings) -> DatasetGovernanceManifestService:
    return DatasetGovernanceManifestService(settings)


def rag_service(settings) -> GovernedRagHandoffService:
    return GovernedRagHandoffService(settings)


def training_service(settings) -> GovernedTrainingHandoffService:
    return GovernedTrainingHandoffService(settings)


def preflight_service(settings) -> PublicCommercialPreflightService:
    return PublicCommercialPreflightService(settings)


@router.get("/summary")
async def summary(settings: SettingsDependency) -> dict[str, Any]:
    listing = build_service(settings).list(page=1, page_size=1)
    return {"counts_by_status": listing["counts_by_status"]}


@router.get("")
async def list_builds(
    settings: SettingsDependency,
    status: str | None = None,
    target_pipeline: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
) -> dict[str, Any]:
    return build_service(settings).list(
        status=status, target_pipeline=target_pipeline, page=page, page_size=page_size
    )


@router.post("")
async def create_build(
    payload: CreateGovernedBuildRequest, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return build_service(settings).create(
        target_pipeline=payload.target_pipeline,
        build_label=payload.build_label,
        configuration=payload.configuration,
        admin_id=admin.admin.public_id,
    )


@router.get("/{public_id}")
async def get_build(public_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return build_service(settings).get(public_id)


@router.patch("/{public_id}")
async def update_build(
    public_id: str,
    payload: UpdateGovernedBuildRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    if payload.build_label is not None:
        fields["build_label"] = payload.build_label
    if payload.configuration is not None:
        fields["configuration_json"] = dumps_json(payload.configuration)
    return build_service(settings).update(public_id, fields, admin_id=admin.admin.public_id)


@router.post("/{public_id}/preview")
async def preview_build(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return build_service(settings).preview(public_id, admin_id=admin.admin.public_id)


@router.post("/{public_id}/preflight")
async def preflight_build(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return build_service(settings).preflight(public_id, admin_id=admin.admin.public_id)


@router.post("/{public_id}/confirm")
async def confirm_build(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return build_service(settings).confirm(public_id, admin_id=admin.admin.public_id)


@router.post("/{public_id}/execute")
async def execute_build(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return build_service(settings).execute(public_id, admin_id=admin.admin.public_id)


@router.post("/{public_id}/cancel")
async def cancel_build(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return build_service(settings).cancel(public_id, admin_id=admin.admin.public_id)


@router.post("/{public_id}/selection")
async def update_selection(
    public_id: str,
    payload: UpdateSelectionRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return build_service(settings).update_selection(
        public_id, payload.item_public_id, included=payload.included, admin_id=admin.admin.public_id
    )


@router.get("/{public_id}/items")
async def build_items(public_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return build_service(settings).items(public_id)


@router.get("/{public_id}/blocked-items")
async def blocked_items(public_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return build_service(settings).blocked_items(public_id)


@router.get("/{public_id}/manifest")
async def get_manifest(public_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return manifest_service(settings).get(public_id)


@router.post("/{public_id}/manifest")
async def generate_manifest(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    extension = manifest_service(settings).generate(public_id, admin_id=admin.admin.public_id)
    return {"governance_extension": extension}


@router.get("/{public_id}/history")
async def build_history(public_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return build_service(settings).history(public_id)


# --- target-specific handoff endpoints (Step 23) --------------------------


@router.post("/{public_id}/dataset-version")
async def dataset_version_handoff(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return build_service(settings).execute(public_id, admin_id=admin.admin.public_id)


@router.post("/{public_id}/rag-handoff")
async def rag_handoff(
    public_id: str,
    payload: RagIngestRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return rag_service(settings).ingest(
        public_id,
        knowledge_space_public_id=payload.knowledge_space_public_id,
        title=payload.title,
        admin_id=admin.admin.public_id,
    )


@router.post("/{public_id}/tokenizer-handoff")
async def tokenizer_handoff(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return training_service(settings).tokenizer_handoff(public_id, admin_id=admin.admin.public_id)


@router.post("/{public_id}/pretraining-handoff")
async def pretraining_handoff(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return training_service(settings).pretraining_handoff(
        public_id, admin_id=admin.admin.public_id
    )


@router.post("/{public_id}/sft-handoff")
async def sft_handoff(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return training_service(settings).sft_handoff(public_id, admin_id=admin.admin.public_id)


@router.post("/{public_id}/evaluation-handoff")
async def evaluation_handoff(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return training_service(settings).evaluation_handoff(public_id, admin_id=admin.admin.public_id)


@router.post("/{public_id}/public-export-preflight")
async def public_export_preflight(public_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return preflight_service(settings).check(public_id)


@router.post("/{public_id}/commercial-preflight")
async def commercial_preflight(public_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return preflight_service(settings).check(public_id)
