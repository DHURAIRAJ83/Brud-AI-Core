"""Phase 18 public Smart Answer Router -- replaces the Phase 1
placeholder. Fully public (no admin auth, no CSRF, matching the
placeholder's own existing convention and Rule: "no Admin
authentication requirement for normal public chat"). Every request is
bounded, rate-limited, and routed through `PublicChatRoutingService`,
which itself never duplicates model/RAG/memory/citation/language logic
-- it only calls existing, already-tested services.
"""

from __future__ import annotations

from typing import Any

import pydantic
from fastapi import APIRouter, Request

from backend.api.dependencies import SettingsDependency
from backend.core.exceptions import BrudError
from backend.database.repositories.public_chat import PublicChatRoutingRepository
from backend.models.public_chat import (
    MAX_MESSAGE_LENGTH,
    PublicChatCapabilities,
    PublicChatFeedbackRequest,
    PublicChatRequest,
    PublicChatResponse,
)
from backend.services.deterministic_tool_registry import get_tool_descriptor
from backend.services.public_chat_rate_limiter import check_rate_limit
from backend.services.public_chat_routing_service import PublicChatRoutingService
from backend.services.public_memory_scope_resolver import PublicMemoryScopeResolver
from backend.services.public_model_assignment_resolver import PublicModelAssignmentResolver
from backend.services.public_rag_scope_resolver import PublicRagScopeResolver
from backend.services.trusted_web_answer_service import TrustedWebAnswerService
from core_model.public_chat.help_faq import HELP_FAQ_ENTRIES

router = APIRouter(tags=["chat"])


class ChatRateLimited(BrudError):
    status_code = 429
    code = "CHAT_RATE_LIMITED"

    def __init__(self) -> None:
        super().__init__("Too many requests. Please wait a moment and try again.")


class ChatInputTooLarge(BrudError):
    status_code = 422
    code = "CHAT_INPUT_TOO_LARGE"

    def __init__(self) -> None:
        super().__init__(f"message must be at most {MAX_MESSAGE_LENGTH} characters.")


class ChatInvalidRequest(BrudError):
    status_code = 422
    code = "CHAT_INVALID_REQUEST"


def _client_key(request: Request) -> str:
    client = request.client
    return client.host if client else "unknown"


@router.post("/chat", response_model=PublicChatResponse)
async def chat(request: Request, settings: SettingsDependency) -> PublicChatResponse:
    allowed = check_rate_limit(
        _client_key(request),
        max_requests=settings.public_chat_rate_limit_max_requests,
        window_seconds=settings.public_chat_rate_limit_window_seconds,
    )
    if not allowed:
        raise ChatRateLimited()

    try:
        body = await request.json()
    except Exception as exc:
        raise ChatInvalidRequest("request body must be valid JSON.") from exc

    try:
        payload = PublicChatRequest.model_validate(body)
    except pydantic.ValidationError as exc:
        if any(error.get("loc") == ("message",) for error in exc.errors()):
            raise ChatInputTooLarge() from exc
        raise ChatInvalidRequest("request body failed validation.") from exc

    service = PublicChatRoutingService(settings)
    return service.handle_message(payload)


@router.get("/chat/capabilities", response_model=PublicChatCapabilities)
async def chat_capabilities(settings: SettingsDependency) -> PublicChatCapabilities:
    model_available = PublicModelAssignmentResolver(
        settings.resolved_database_path, settings
    ).resolve() is not None
    rag_available = PublicRagScopeResolver(
        settings.resolved_database_path, settings
    ).resolve() is not None
    memory_available = PublicMemoryScopeResolver(
        settings.resolved_database_path, settings
    ).resolve() is not None
    trusted_web_available = TrustedWebAnswerService(settings).is_available()
    calculator = get_tool_descriptor("calculator")
    unit_conversion = get_tool_descriptor("unit_conversion")
    date_time_arithmetic = get_tool_descriptor("date_time_arithmetic")
    calculator_available = calculator is not None and calculator.public_enabled
    unit_conversion_available = unit_conversion is not None and unit_conversion.public_enabled
    date_time_arithmetic_available = (
        date_time_arithmetic is not None and date_time_arithmetic.public_enabled
    )
    return PublicChatCapabilities(
        core_model_available=model_available,
        approved_rag_available=rag_available,
        memory_available=memory_available,
        trusted_web_available=trusted_web_available,
        tool_available=(
            calculator_available or unit_conversion_available or date_time_arithmetic_available
        ),
        calculator_available=calculator_available,
        unit_conversion_available=unit_conversion_available,
        date_time_arithmetic_available=date_time_arithmetic_available,
        external_mcp_enabled=settings.external_mcp_enabled,
    )


@router.post("/chat/feedback")
async def chat_feedback(
    payload: PublicChatFeedbackRequest, settings: SettingsDependency
) -> dict[str, Any]:
    repository = PublicChatRoutingRepository(settings.resolved_database_path)
    record = repository.record_feedback(
        {
            "request_id": payload.request_id,
            "route_used": payload.route_used,
            "answer_hash": payload.answer_hash,
            "feedback_type": payload.feedback_type,
            "comment": payload.comment,
        }
    )
    return {"public_id": record["public_id"], "accepted": True}


@router.get("/chat/help")
async def chat_help() -> dict[str, Any]:
    """Static, deterministic reference explaining the public router's own
    behavior (route selection, why Web/Tool are unavailable, etc.) --
    never used to auto-answer a real question, see Step 32 in
    `core_model/public_chat/help_faq.py` for why."""

    return {"entries": list(HELP_FAQ_ENTRIES), "count": len(HELP_FAQ_ENTRIES)}


__all__ = ["router"]
