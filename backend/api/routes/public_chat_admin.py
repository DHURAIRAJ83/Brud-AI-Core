"""Phase 18 Public Smart Answer Router -- Admin-only diagnostics API,
under `/api/admin/public-chat-routing`.

Read-only. Reads from `public_chat_routing_events` /
`public_chat_feedback_events` (migration 040) via
`PublicChatRoutingRepository`. Never exposes raw public question or
answer text -- those are never persisted in the first place; only
input hashes and structured classification/route outputs are stored,
mirroring Phase 17's `knowledge_routing` admin diagnostics convention.
This router never modifies routing policy, model assignments, or RAG
activation.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from backend.api.auth import require_admin
from backend.api.dependencies import SettingsDependency
from backend.database.repositories.base import NotFoundError
from backend.database.repositories.public_chat import PublicChatRoutingRepository

router = APIRouter(
    prefix="/admin/public-chat-routing",
    tags=["public-chat-routing"],
    dependencies=[Depends(require_admin)],
)


def repository(settings: SettingsDependency) -> PublicChatRoutingRepository:
    return PublicChatRoutingRepository(settings.resolved_database_path)


@router.get("/overview")
async def get_overview(settings: SettingsDependency) -> dict[str, Any]:
    repo = repository(settings)
    metrics = repo.aggregate_metrics()
    language = repo.language_compliance_summary()
    return {
        **metrics,
        "language_compliance": language,
        "clarification_count": metrics["by_resolved_route"].get("clarify", 0),
        "refusal_count": metrics["by_resolved_route"].get("refuse", 0),
        "insufficient_count": metrics["by_resolved_route"].get("insufficient", 0),
    }


@router.get("/events")
async def list_events(
    settings: SettingsDependency,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    resolved_route: str | None = None,
) -> dict[str, Any]:
    repo = repository(settings)
    events = repo.list_events(limit=limit, offset=offset, resolved_route=resolved_route)
    return {"events": events, "count": len(events)}


@router.get("/events/{public_id}")
async def get_event(public_id: str, settings: SettingsDependency) -> dict[str, Any]:
    repo = repository(settings)
    event = repo.get_event(public_id)
    if event is None:
        raise NotFoundError(f"public chat routing event not found: {public_id}")
    return event


__all__ = ["router"]
