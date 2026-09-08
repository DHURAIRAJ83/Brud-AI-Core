"""Governed Admin Assistant API: dashboard understanding, proposals, Admin Review.

Every mutating action is a two-step, two-actor flow:
  1. `POST /proposals` drafts a proposal (no mutation happens here).
  2. `POST /proposals/{id}/review` lets an authenticated admin approve or
     reject it (Admin Review). Only an approved proposal may be executed.
  3. `POST /proposals/{id}/execute` runs the approved proposal through an
     allowlisted existing service call.

All three steps, plus failures, are written to the audit log by the
service layer.
"""

from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from pydantic import Field

from backend.api.auth import AdminDependency, CsrfDependency, require_admin
from backend.api.dependencies import PoolDependency, SettingsDependency
from backend.core.validation import DomainModel
from backend.database.repositories.admin_assistant_context import (
    AdminAssistantContextRepository,
)
from backend.database.repositories.base import ValidationError
from backend.models.domain import AdminApprovalPublic
from backend.services.admin_assistant_chat_service import AdminAssistantChatService
from backend.services.admin_assistant_language_service import AdminAssistantLanguageService
from backend.services.admin_assistant_service import ACTION_EXECUTORS, AdminAssistantService
from backend.services.admin_assistant_write_governance import (
    execute_with_governance,
    propose_with_governance,
)
from backend.services.document_service import DocumentService
from backend.services.import_service import ImportService
from core_model.admin_assistant.action_registry import ACTION_DEFINITIONS
from core_model.admin_assistant.dashboard_registry import DASHBOARD_PAGES, REGISTRY_VERSION
from core_model.admin_assistant.localization import pending_work_lines

router = APIRouter(
    prefix="/admin/assistant", tags=["admin-assistant"], dependencies=[Depends(require_admin)]
)


def service(settings) -> AdminAssistantService:
    return AdminAssistantService(settings)


def language_service(settings) -> AdminAssistantLanguageService:
    return AdminAssistantLanguageService(settings)


def chat_service(settings, pool=None) -> AdminAssistantChatService:
    return AdminAssistantChatService(settings, pool=pool)


class ProposalCreateRequest(DomainModel):
    action_type: str
    target_type: str
    target_public_id: str
    request_payload: dict[str, Any] = Field(default_factory=dict)
    summary: str = Field(default="", max_length=2000)


class ProposalReviewRequest(DomainModel):
    decision: str
    comment: str | None = Field(default=None, max_length=4000)


class ProposalCancelRequest(DomainModel):
    reason: str | None = Field(default=None, max_length=2000)


class ChatMessageRequest(DomainModel):
    message: str = Field(min_length=1, max_length=4000)
    page_id: str = Field(min_length=1, max_length=80)
    tab_id: str | None = Field(default=None, max_length=120)
    entity_type: str | None = Field(default=None, max_length=60)
    entity_public_id: str | None = Field(default=None, max_length=80)
    mode: str = Field(default="guide", max_length=20)
    # Preview/testing only (Step 8) -- resolves this one reply's language
    # without ever silently changing the admin's saved preference.
    response_language_override: str | None = Field(default=None, max_length=20)


class FeedbackCreateRequest(DomainModel):
    rating: Literal["helpful", "not_helpful", "incorrect_guidance", "action_failed"]
    page_id: str | None = Field(default=None, max_length=80)
    action_id: str | None = Field(default=None, max_length=80)
    message_reference: str | None = Field(default=None, max_length=120)
    comment: str = Field(default="", max_length=2000)


class LanguagePreferenceUpdateRequest(DomainModel):
    response_language: str


class LanguagePreferencePreviewRequest(DomainModel):
    message_text: str = Field(default="", max_length=4000)
    response_language_override: str | None = Field(default=None, max_length=20)


@router.get("/overview")
async def overview(settings: SettingsDependency, admin: AdminDependency) -> dict[str, Any]:
    """Read-only summary of every governed area of the Admin Dashboard.
    `localized_guidance` is an additive field rendered in the requesting
    admin's resolved response language -- the original `guidance` list
    stays English-only and unchanged, since other callers/tests already
    depend on that exact contract."""

    result = service(settings).dashboard_overview()
    resolved = language_service(settings).resolve(admin_id=admin.admin.public_id)
    result["localized_guidance"] = pending_work_lines(
        result.get("summary", {}), resolved.resolved_language
    )
    result["resolved_language"] = resolved.resolved_language
    return result


@router.get("/governance-status")
async def governance_status(settings: SettingsDependency) -> dict[str, Any]:
    """Read-only summary of canonical P0-P10G enterprise governance state."""
    return service(settings).get_governance_status()


@router.get("/actions")
async def available_actions() -> dict[str, Any]:
    """Allowlisted action types the assistant may propose, plus (additively)
    each one's pure metadata from the action registry -- risk level, mode,
    payload shape, and bilingual confirmation copy. `action_types` is kept
    exactly as before for backward compatibility."""

    return {
        "action_types": sorted(ACTION_EXECUTORS),
        "actions": [
            {
                "action_type": action.action_type,
                "target_type": action.target_type,
                "risk_level": action.risk_level,
                "mode": action.mode,
                "requires_reason": action.requires_reason,
                "reversible": action.reversible,
                "payload_fields": list(action.payload_fields),
                "summary": action.summary,
                "confirmation_text": action.confirmation_text,
            }
            for action in ACTION_DEFINITIONS
            if action.action_type in ACTION_EXECUTORS
        ],
    }


@router.get("/pages")
async def dashboard_pages() -> dict[str, Any]:
    """The full dashboard page registry -- the assistant's single source
    of truth for page purpose/tabs/safety notes, exposed so the frontend
    never needs its own duplicate copy."""

    return {
        "registry_version": REGISTRY_VERSION,
        "items": [
            {
                "page_id": page.page_id,
                "nav_key": page.nav_key,
                "group": page.group,
                "implemented": page.implemented,
                "mode": page.mode,
                "title": page.title,
                "purpose": page.purpose,
                "tabs": list(page.tabs),
                "related_page_ids": list(page.related_page_ids),
                "safety_note": page.safety_note,
            }
            for page in DASHBOARD_PAGES
        ],
    }


@router.get("/health")
async def assistant_health(settings: SettingsDependency) -> dict[str, Any]:
    """Real, read-only diagnostic: is an LLM-backed reply currently
    possible. Deterministic guide/status features work regardless."""

    return chat_service(settings).llm_status()


@router.get("/preferences")
async def get_language_preference(
    settings: SettingsDependency, admin: AdminDependency
) -> dict[str, Any]:
    """The requesting admin's own saved Admin Assistant response
    language preference -- never another admin's (scoped by their own
    authenticated session, same as every other admin-scoped read
    here)."""

    return language_service(settings).get_preference(admin.admin.public_id)


@router.patch("/preferences")
async def set_language_preference(
    payload: LanguagePreferenceUpdateRequest, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    # `AdminRepository.set_response_language` itself raises `ValidationError`
    # for anything outside `RESPONSE_LANGUAGES` -- the existing
    # `RepositoryError` -> 422 exception handler covers it, no separate
    # check needed here.
    return language_service(settings).set_preference(
        admin.admin.public_id, payload.response_language
    )


@router.post("/preferences/preview")
async def preview_language_resolution(
    payload: LanguagePreferencePreviewRequest, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    """Non-persistent preview (Step 8) -- resolves what response
    language *would* apply without reading or writing the saved
    preference, so an admin can try a mode before committing to it.
    Every other `POST` in this router requires CSRF; this endpoint
    keeps that consistent even though it performs no mutation."""

    del admin
    return language_service(settings).preview(
        message_text=payload.message_text,
        request_override=payload.response_language_override,
    )


@router.post("/chat")
async def send_chat_message(
    payload: ChatMessageRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
    pool: PoolDependency,
) -> dict[str, Any]:
    """Phase 7C-60: opted into the shared app-instance pool, mirroring
    `create_smoke_run`'s (Phase 7C-56) `payload, settings, admin, pool`
    signature exactly. The pool flows through `chat_service(settings, pool)`
    into `AdminAssistantChatService.__init__`, then per-call into
    `run_tool(..., pool=...)` -- it never reaches a tool handler except as
    a pool-backed repository, and only for the one tool
    (`get_recent_audit_events`) whose `ToolDefinition.pool_aware=True`."""

    return chat_service(settings, pool).send_message(
        admin_id=admin.admin.public_id,
        message=payload.message,
        page_id=payload.page_id,
        tab_id=payload.tab_id,
        entity_type=payload.entity_type,
        entity_public_id=payload.entity_public_id,
        mode=payload.mode,
        response_language_override=payload.response_language_override,
    )


@router.post("/feedback")
async def submit_feedback(
    payload: FeedbackCreateRequest, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    repository = AdminAssistantContextRepository(settings.resolved_database_path)
    return repository.create_feedback(
        {
            "rating": payload.rating,
            "page_id": payload.page_id,
            "action_id": payload.action_id,
            "message_reference": payload.message_reference,
            "comment": payload.comment,
            "registry_version": REGISTRY_VERSION,
            "submitted_by_admin_public_id": admin.admin.public_id,
        }
    )


@router.post("/proposals", response_model=AdminApprovalPublic)
async def create_proposal(
    payload: ProposalCreateRequest, settings: SettingsDependency, admin: CsrfDependency
) -> AdminApprovalPublic:
    """Phase 4: routed through `propose_with_governance()` -- the RBAC
    `tool.propose` check -- rather than calling `AdminAssistantService.
    propose()` directly. See admin_assistant_write_governance.py for
    why the check lives here rather than inside the service itself."""

    return propose_with_governance(
        service(settings),
        action_type=payload.action_type,
        target_type=payload.target_type,
        target_public_id=payload.target_public_id,
        request_payload=payload.request_payload,
        requested_by=admin.admin.public_id,
        summary=payload.summary,
    )


@router.get("/proposals")
async def list_proposals(
    settings: SettingsDependency,
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
) -> list[AdminApprovalPublic]:
    offset = (page - 1) * page_size
    return service(settings).list_proposals(status=status, limit=page_size, offset=offset)


@router.get("/proposals/{public_id}")
async def get_proposal(public_id: str, settings: SettingsDependency) -> AdminApprovalPublic:
    return service(settings).get_proposal(public_id)


@router.post("/proposals/{public_id}/review", response_model=AdminApprovalPublic)
async def review_proposal(
    public_id: str,
    payload: ProposalReviewRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> AdminApprovalPublic:
    return service(settings).review(
        public_id,
        decision=payload.decision,
        reviewed_by=admin.admin.public_id,
        comment=payload.comment,
    )


@router.post("/proposals/{public_id}/execute", response_model=AdminApprovalPublic)
async def execute_proposal(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> AdminApprovalPublic:
    """Phase 4: routed through `execute_with_governance()` -- the RBAC
    `tool.execute` check -- rather than calling `AdminAssistantService.
    execute()` directly. See admin_assistant_write_governance.py."""

    return execute_with_governance(
        service(settings), public_id, executor_public_id=admin.admin.public_id
    )


@router.post("/proposals/{public_id}/cancel", response_model=AdminApprovalPublic)
async def cancel_proposal(
    public_id: str,
    payload: ProposalCancelRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> AdminApprovalPublic:
    return service(settings).cancel(
        public_id, cancelled_by=admin.admin.public_id, reason=payload.reason
    )


@router.post("/upload")
async def assistant_upload(
    settings: SettingsDependency,
    admin: CsrfDependency,
    file: Annotated[UploadFile, File()],
    session_id: Annotated[str | None, Form()] = None,
    mode: Annotated[str, Form()] = "guide",
) -> dict[str, Any]:
    """Authenticated, CSRF-protected file upload handler for Admin Assistant chat.

    Accepts PDF documents and dataset text files (.pdf, .jsonl, .json, .csv, .txt).
    PDFs are processed and registered via DocumentService.
    Dataset files are parsed, validated, and staged via ImportService.
    Returns structured metadata and assistant action recommendations.
    """
    raw_filename = file.filename or "uploaded_file"
    suffix = Path(raw_filename).suffix.lower()

    if suffix == ".pdf":
        doc_service = DocumentService(settings)
        doc = await doc_service.upload(
            upload=file,
            strategy="auto",
            language="mixed",
            admin_id=admin.admin.public_id,
        )
        checksum_prefix = doc.get("checksum_prefix") or (doc.get("checksum_sha256") or "")[:12]
        return {
            "status": "success",
            "file_type": "pdf",
            "document": doc,
            "summary": (
                f"PDF '{doc.get('original_filename')}' successfully uploaded and registered. "
                f"Pages: {doc.get('page_count')}, Size: {doc.get('file_size_bytes')} bytes, "
                f"SHA-256: {checksum_prefix}... Ready for Page Review or SFT Candidate Generation."
            ),
            "action_recommendation": {
                "type": "document_review",
                "nav_key": "Documents",
                "document_public_id": doc.get("public_id"),
                "message": "Open in Documents workspace for Tamil OCR quality review and candidate generation.",
            },
        }

    if suffix in {".jsonl", ".json", ".csv", ".tsv", ".txt"}:
        import_service = ImportService(settings)
        imp = await import_service.receive_upload(
            upload=file,
            record_type="instruction",
            default_language="unknown",
            import_mode="create_only",
            field_mapping={},
            parser_options={},
            encoding="utf-8",
            admin_id=admin.admin.public_id,
        )
        checksum_prefix = (imp.get("checksum_sha256") or "")[:12]
        return {
            "status": "success",
            "file_type": "dataset",
            "import": imp,
            "summary": (
                f"Dataset file '{imp.get('original_filename')}' successfully uploaded. "
                f"Status: {imp.get('status')}, Size: {imp.get('file_size_bytes')} bytes, "
                f"SHA-256: {checksum_prefix}... Staged for quarantine review."
            ),
            "action_recommendation": {
                "type": "dataset_import",
                "nav_key": "Sample Import & Quarantine",
                "import_public_id": imp.get("public_id"),
                "message": "Open in Sample Import & Quarantine to review records and schema mappings.",
            },
        }

    raise ValidationError(
        f"unsupported file type '{suffix}'. Supported formats are: .pdf, .jsonl, .json, .csv, .tsv, .txt"
    )

