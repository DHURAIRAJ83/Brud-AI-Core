"""Phase 17 Knowledge Domain / Freshness / Evidence / Learning-Target
Router -- Admin-only diagnostic API, under `/api/admin/knowledge-routing`.

Every endpoint here calls only the pure classification pipeline
(`core_model.knowledge_routing.pipeline.classify`) via
`KnowledgeRoutingClassificationService` -- never Model, RAG, Web, Tool,
or Memory. Every response is a **recommendation**, never an executed
route. This router does not modify `/api/chat` or
`ChatOrchestrationService` in any way.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.core.validation import DomainModel
from backend.database.repositories.base import ValidationError
from backend.services.knowledge_routing_classification_service import (
    KnowledgeRoutingClassificationService,
)
from core_model.knowledge_routing import CONTEXT_TYPES
from core_model.knowledge_routing.pipeline import MAX_INPUT_LENGTH, ClassificationInputError
from core_model.knowledge_routing.policy_loader import PolicyValidationError, get_policy
from core_model.knowledge_routing.reason_codes import REASON_CODE_REGISTRY


def _as_validation_error(exc: ClassificationInputError | ValueError) -> ValidationError:
    return ValidationError(str(exc))

router = APIRouter(
    prefix="/admin/knowledge-routing",
    tags=["knowledge-routing"],
    dependencies=[Depends(require_admin)],
)


def service(settings: SettingsDependency) -> KnowledgeRoutingClassificationService:
    return KnowledgeRoutingClassificationService(settings)


class ClassifyTextRequest(DomainModel):
    text: str
    context_type: str = "public_chat_question"
    persist: bool = True

    def validated_text(self) -> str:
        text = self.text.strip()
        if not text:
            raise ValidationError("text must not be empty")
        if len(text) > MAX_INPUT_LENGTH:
            raise ValidationError(f"text exceeds max length of {MAX_INPUT_LENGTH}")
        return text


class ClassifyRecordRequest(DomainModel):
    context_type: str
    record: dict[str, Any]
    persist: bool = True


@router.get("/policy")
async def get_policy_snapshot() -> dict[str, Any]:
    """Read-only snapshot of the loaded, checksum-verified policy file."""

    try:
        policy = get_policy()
    except PolicyValidationError as exc:
        return {"valid": False, "error": str(exc)}
    return {
        "valid": True,
        "policy_version": policy["policy_version"],
        "taxonomy_version": policy["taxonomy_version"],
        "policy_checksum_sha256": policy.get("policy_checksum_sha256"),
        "domain_count": len(policy.get("domains", {})),
        "intent_count": len(policy.get("intents", {})),
    }


@router.get("/reason-codes")
async def list_reason_codes() -> dict[str, Any]:
    return {"reason_codes": REASON_CODE_REGISTRY, "count": len(REASON_CODE_REGISTRY)}


@router.get("/context-types")
async def list_context_types() -> dict[str, Any]:
    return {"context_types": list(CONTEXT_TYPES)}


@router.post("/classify")
async def classify_text(
    payload: ClassifyTextRequest, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    svc = service(settings)
    text = payload.validated_text()
    if payload.context_type not in CONTEXT_TYPES:
        raise ValidationError(f"unknown context_type: {payload.context_type!r}")
    try:
        return svc.classify_text(
            text,
            context_type=payload.context_type,
            actor_reference=admin.admin.public_id,
            persist=payload.persist,
        )
    except ClassificationInputError as exc:
        raise _as_validation_error(exc) from exc


@router.post("/classify-record")
async def classify_record(
    payload: ClassifyRecordRequest, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    svc = service(settings)
    if payload.context_type not in CONTEXT_TYPES:
        raise ValidationError(f"unknown context_type: {payload.context_type!r}")
    try:
        return svc.classify_structured_record(
            payload.context_type,
            payload.record,
            actor_reference=admin.admin.public_id,
            persist=payload.persist,
        )
    except (ClassificationInputError, ValueError) as exc:
        raise _as_validation_error(exc) from exc


@router.get("/decisions/{decision_public_id}")
async def get_decision(decision_public_id: str, settings: SettingsDependency) -> dict[str, Any]:
    svc = service(settings)
    return svc.get_decision(decision_public_id)


@router.get("/decisions")
async def list_decisions(
    settings: SettingsDependency,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    context_type: str | None = None,
    execution_route: str | None = None,
    domain: str | None = None,
) -> dict[str, Any]:
    svc = service(settings)
    decisions = svc.list_decisions(
        limit=limit,
        offset=offset,
        context_type=context_type,
        execution_route=execution_route,
        domain=domain,
    )
    return {"decisions": decisions, "count": len(decisions)}


@router.get("/metrics")
async def get_metrics(settings: SettingsDependency) -> dict[str, Any]:
    svc = service(settings)
    return svc.aggregate_metrics()


__all__ = ["router"]
