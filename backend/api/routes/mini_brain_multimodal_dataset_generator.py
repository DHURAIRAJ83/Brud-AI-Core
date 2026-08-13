"""MB-16: Brud Mini Brain Multimodal Dataset Generator Center --
authenticated admin-only APIs. Independent prefix (`/admin/mini-brain/
multimodal-dataset-generator`), separate from every system this phase
reads from (MB-13 Language Intelligence, MB-14 Vision Intelligence,
MB-15 Vision Model Center, Dataset Studio, Document Workspace). No
route here writes a Dataset Studio record, edits Document Workspace,
starts training, or deploys a model -- every mutating route only ever
writes to MB-16's own tables. Every generated dataset stays Draft
until an admin certifies it.

Each workflow stage gets its own independently-callable route,
mirroring the precedent set by MB-06 through MB-15, so every stage is
independently testable.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.models.mini_brain_multimodal_dataset_generator import (
    AdminReviewRequest,
    CreateSessionRequest,
    ExportDraftRequest,
    MergeDatasetsRequest,
    SplitDatasetRequest,
)
from backend.services.mini_brain_multimodal_dataset_generator_service import (
    MiniBrainMultimodalDatasetGeneratorService,
)

router = APIRouter(
    prefix="/admin/mini-brain/multimodal-dataset-generator",
    tags=["admin-mini-brain-multimodal-dataset-generator"],
    dependencies=[Depends(require_admin)],
)


def service(settings) -> MiniBrainMultimodalDatasetGeneratorService:
    return MiniBrainMultimodalDatasetGeneratorService(settings)


@router.get("/diagnostics")
async def diagnostics():
    return {
        "dataset_studio_writes_performed": False,
        "document_workspace_writes_performed": False,
        "mb13_writes_performed": False,
        "mb14_writes_performed": False,
        "mb15_writes_performed": False,
        "training_started": False,
        "runtime_activated": False,
        "models_deployed": False,
        "automatic_export": False,
        "automatic_approval": False,
        "writes_scope": (
            "own tables only (mini_brain_multimodal_dataset_sessions/_records/_events, "
            "mini_brain_multimodal_dataset_memory)"
        ),
        "record_types": [
            "conversation", "instruction", "qa", "caption", "vision", "grounding", "reasoning", "training",
        ],
        "pipeline_stages": [
            "collect_sources", "collect_text", "collect_images", "merge_metadata", "conversation_builder",
            "instruction_builder", "dataset_draft", "quality_analysis", "duplicate_detection", "report",
            "awaiting_admin_review", "certified", "closed",
        ],
    }


# -- sessions ----------------------------------------------------------------


@router.post("/sessions")
async def create_session(payload: CreateSessionRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).create_session(
        document_source_public_id=payload.document_source_public_id,
        dataset_source_public_id=payload.dataset_source_public_id,
        language_session_public_id=payload.language_session_public_id,
        vision_session_public_id=payload.vision_session_public_id,
        vision_model_session_public_id=payload.vision_model_session_public_id,
        admin_id=admin.admin.public_id,
    )


@router.get("/sessions")
async def list_sessions(
    settings: SettingsDependency,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return service(settings).list_sessions(limit=limit, offset=offset)


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, settings: SettingsDependency):
    return service(settings).session(session_id)


@router.get("/sessions/{session_id}/events")
async def list_events(
    session_id: str,
    settings: SettingsDependency,
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return service(settings).events(session_id, limit=limit, offset=offset)


@router.get("/sessions/{session_id}/records")
async def list_records(
    session_id: str, settings: SettingsDependency, record_type: str | None = None, status: str | None = None,
):
    return service(settings).list_records(session_id, record_type=record_type, status=status)


@router.get("/dataset-memory")
async def list_memory(
    settings: SettingsDependency,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return service(settings).list_memory(limit=limit, offset=offset)


# -- stages --------------------------------------------------------------------


@router.post("/sessions/{session_id}/collect-sources")
async def run_collect_sources(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_collect_sources_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/collect-text")
async def run_collect_text(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_collect_text_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/collect-images")
async def run_collect_images(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_collect_images_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/merge-metadata")
async def run_merge_metadata(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_merge_metadata_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/conversation-builder")
async def run_conversation_builder(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_conversation_builder_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/instruction-builder")
async def run_instruction_builder(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_instruction_builder_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/dataset-draft")
async def run_dataset_draft(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_dataset_draft_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/quality-analysis")
async def run_quality_analysis(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_quality_analysis_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/duplicate-detection")
async def run_duplicate_detection(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_duplicate_detection_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/report")
async def generate_report(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).generate_report_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/admin-review")
async def admin_review(
    session_id: str, payload: AdminReviewRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).admin_review(session_id, decision=payload.decision, admin_id=admin.admin.public_id)


# -- draft-lifecycle actions ----------------------------------------------------------


@router.post("/sessions/{session_id}/delete-draft")
async def delete_draft(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).delete_draft(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/export-draft")
async def export_draft(
    session_id: str, payload: ExportDraftRequest, settings: SettingsDependency, admin: CsrfDependency
):
    del admin
    return service(settings).export_draft(session_id, export_format=payload.export_format)


@router.post("/sessions/{session_id}/split")
async def split_dataset(
    session_id: str, payload: SplitDatasetRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).split_dataset(
        session_id, record_public_ids=payload.record_public_ids, admin_id=admin.admin.public_id,
    )


@router.post("/merge")
async def merge_datasets(payload: MergeDatasetsRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).merge_datasets(payload.session_public_ids, admin_id=admin.admin.public_id)
