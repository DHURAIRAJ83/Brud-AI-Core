"""MB-28: Real Mini Brain LLM Runtime & Admin Assistant Intelligence
Layer -- admin-only APIs. Independent prefix
(`/admin/mini-brain/llm-runtime`), disjoint from the separate,
pre-existing "Phase 8" Admin Assistant system's `/api/admin/assistant`
prefix. No public routes exist in this phase.
"""

from __future__ import annotations

import json
import time
from uuid import uuid4
from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import StreamingResponse

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.models.mini_brain_llm_runtime import (
    ChatRequest,
    ChatResponse,
    DefaultRetrievalProfileResponse,
    DiagnosticsResponse,
    ExplainErrorRequest,
    ExplainPageRequest,
    GroundedChatRequest,
    GroundedChatResponse,
    MessageListResponse,
    NextActionsRequest,
    NextActionsResponse,
    SessionListResponse,
    SessionResponse,
    SetDefaultRetrievalProfileRequest,
    StreamChatRequest,
    SummarizeRegressionRequest,
    SummarizeReportRequest,
    WidgetHealthResponse,
)
from backend.services.mini_brain_llm_runtime_service import MiniBrainLlmRuntimeService

router = APIRouter(
    prefix="/admin/mini-brain/llm-runtime",
    tags=["admin-mini-brain-llm-runtime"],
    dependencies=[Depends(require_admin)],
)


def service(settings) -> MiniBrainLlmRuntimeService:
    return MiniBrainLlmRuntimeService(settings)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    request: Request,
    response: Response,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    trace_id = request.headers.get("X-Trace-Id") or payload.trace_id or f"trc_{uuid4().hex[:16]}"
    response.headers["X-Trace-Id"] = trace_id
    res = service(settings).chat(
        session_id=payload.session_id,
        message=payload.message,
        admin_id=admin.admin.public_id,
        execution_mode=payload.execution_mode or "auto",
        provider_key=payload.provider_key,
        model_override=payload.model_override,
        trace_id=trace_id,
    )
    res["trace_id"] = trace_id
    return res


@router.post("/chat/stream")
async def chat_stream(
    payload: StreamChatRequest,
    request: Request,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    """Real Server-Sent Events (SSE) streaming endpoint for Admin Assistant chat.
    Emits start, metadata (model, citations), token, done, and error events.
    Guarantees distributed tracing (X-Trace-Id), backpressure handling, client disconnect cleanup, and single-turn memory persistence.
    """
    trace_id = request.headers.get("X-Trace-Id") or payload.trace_id or f"trc_{uuid4().hex[:16]}"
    svc = service(settings)

    async def event_generator():
        last_event_time = time.perf_counter()
        try:
            event_stream = svc.stream_chat(
                session_id=payload.session_id,
                message=payload.message,
                admin_id=admin.admin.public_id,
                execution_mode=payload.execution_mode or "auto",
                provider_key=payload.provider_key,
                model_override=payload.model_override,
                grounded=payload.grounded,
                retrieval_profile_public_id=payload.retrieval_profile_public_id,
                top_k=payload.top_k,
                trace_id=trace_id,
            )
            for item in event_stream:
                if await request.is_disconnected():
                    try:
                        with svc.repository.transaction() as conn:
                            svc.repository.create_event(
                                conn,
                                session_id=payload.session_id,
                                event_type="stream_aborted",
                                backend_type=None,
                                admin_id=admin.admin.public_id,
                                detail={"reason": "client_disconnected", "trace_id": trace_id},
                            )
                    except Exception:
                        pass
                    break

                now = time.perf_counter()
                if now - last_event_time >= 2.5:
                    yield ": keep-alive\n\n"
                    last_event_time = now

                event_name = item.get("event", "message")
                data_dict = item.get("data", {})
                if "trace_id" not in data_dict and trace_id:
                    data_dict["trace_id"] = trace_id
                data_json = json.dumps(data_dict, ensure_ascii=False)
                yield f"event: {event_name}\ndata: {data_json}\n\n"
                last_event_time = time.perf_counter()
        except Exception as exc:  # noqa: BLE001
            err_data = json.dumps({"code": "STREAM_INTERNAL_ERROR", "message": str(exc), "retryable": False, "trace_id": trace_id})
            yield f"event: error\ndata: {err_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Trace-Id": trace_id,
        },
    )


@router.post("/grounded-chat", response_model=GroundedChatResponse)
async def grounded_chat(
    payload: GroundedChatRequest,
    request: Request,
    response: Response,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    trace_id = request.headers.get("X-Trace-Id") or payload.trace_id or f"trc_{uuid4().hex[:16]}"
    response.headers["X-Trace-Id"] = trace_id
    res = service(settings).grounded_chat(
        session_id=payload.session_id,
        message=payload.message,
        retrieval_profile_public_id=payload.retrieval_profile_public_id,
        top_k=payload.top_k,
        admin_id=admin.admin.public_id,
        execution_mode=payload.execution_mode or "auto",
        provider_key=payload.provider_key,
        model_override=payload.model_override,
        trace_id=trace_id,
    )
    res["trace_id"] = trace_id
    return res



@router.get("/grounded-chat/default-retrieval-profile", response_model=DefaultRetrievalProfileResponse)
async def default_retrieval_profile(settings: SettingsDependency):
    return service(settings).default_retrieval_profile()


@router.post("/grounded-chat/default-retrieval-profile", response_model=DefaultRetrievalProfileResponse)
async def set_default_retrieval_profile(
    payload: SetDefaultRetrievalProfileRequest, settings: SettingsDependency, admin: CsrfDependency,
):
    return service(settings).set_default_retrieval_profile(
        payload.retrieval_profile_public_id, admin.admin.public_id,
    )


@router.post("/explain-page", response_model=ChatResponse)
async def explain_page(payload: ExplainPageRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).explain_dashboard_page(
        session_id=payload.session_id, page_id=payload.page_id, nav_key=payload.nav_key, admin_id=admin.admin.public_id,
    )


@router.post("/summarize-report", response_model=ChatResponse)
async def summarize_report(payload: SummarizeReportRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).summarize_phase_report(
        session_id=payload.session_id, report=payload.report, admin_id=admin.admin.public_id,
    )


@router.post("/summarize-regression", response_model=ChatResponse)
async def summarize_regression(payload: SummarizeRegressionRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).summarize_regression_results(
        session_id=payload.session_id, regression_result=payload.regression_result, admin_id=admin.admin.public_id,
    )


@router.post("/explain-error", response_model=ChatResponse)
async def explain_error(payload: ExplainErrorRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).explain_error_message(
        session_id=payload.session_id, error_message=payload.error_message, admin_id=admin.admin.public_id,
    )


@router.post("/next-actions", response_model=NextActionsResponse)
async def next_actions(payload: NextActionsRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).next_actions(
        session_id=payload.session_id, status_snapshot=payload.status_snapshot, admin_id=admin.admin.public_id,
    )


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    settings: SettingsDependency,
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return service(settings).list_sessions(status=status, limit=limit, offset=offset)


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str, settings: SettingsDependency):
    return service(settings).get_session(session_id)


@router.get("/sessions/{session_id}/messages", response_model=MessageListResponse)
async def list_messages(
    session_id: str, settings: SettingsDependency,
    limit: int = Query(default=100, ge=1, le=100), offset: int = Query(default=0, ge=0),
):
    return service(settings).list_messages(session_id, limit=limit, offset=offset)


@router.delete("/sessions/{session_id}", response_model=SessionResponse)
async def delete_session(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).delete_session(session_id, admin_id=admin.admin.public_id)


@router.get("/diagnostics", response_model=DiagnosticsResponse)
async def diagnostics(settings: SettingsDependency):
    return service(settings).diagnostics()


@router.get("/widget-health", response_model=WidgetHealthResponse)
async def widget_health(settings: SettingsDependency):
    return service(settings).widget_health()


__all__ = ["router"]
