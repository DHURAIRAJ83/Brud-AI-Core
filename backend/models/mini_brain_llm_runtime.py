"""MB-28: Real Mini Brain LLM Runtime & Admin Assistant Intelligence
Layer API schemas.

No field in any response model here is secret-shaped -- this phase
never stores or returns provider secrets itself (it reads masked
provider config only, via MB-27's own service). `DiagnosticsResponse.
configured_model_path` is always the filename only (see
`core_model.mini_brain.llm_runtime.runtime_diagnostics_builder.
mask_model_path()`), never a full absolute path.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from backend.core.validation import DomainModel

CAPABILITIES = Literal[
    "chat", "explain_page", "summarize_report", "summarize_regression",
    "explain_error", "next_actions", "step_guide", "checklist", "clarify",
]


class ChatRequest(DomainModel):
    session_id: str | None = None
    message: str = Field(min_length=1, max_length=8000)
    execution_mode: Literal["auto", "local", "provider"] | None = "auto"
    provider_key: str | None = None
    model_override: str | None = None
    trace_id: str | None = None


class GroundedChatRequest(DomainModel):
    message: str = Field(min_length=1, max_length=8000)
    session_id: str | None = None
    retrieval_profile_public_id: str | None = None
    top_k: int = Field(default=4, ge=1, le=8)
    execution_mode: Literal["auto", "local", "provider"] | None = "auto"
    provider_key: str | None = None
    model_override: str | None = None
    trace_id: str | None = None


class StreamChatRequest(DomainModel):
    message: str = Field(min_length=1, max_length=8000)
    session_id: str | None = None
    execution_mode: Literal["auto", "local", "provider"] | None = "auto"
    provider_key: str | None = None
    model_override: str | None = None
    grounded: bool = False
    retrieval_profile_public_id: str | None = None
    top_k: int = Field(default=4, ge=1, le=8)
    trace_id: str | None = None



class ExplainPageRequest(DomainModel):
    session_id: str | None = None
    page_id: str | None = None
    nav_key: str | None = None


class SummarizeReportRequest(DomainModel):
    session_id: str | None = None
    report: dict = Field(default_factory=dict)


class SummarizeRegressionRequest(DomainModel):
    session_id: str | None = None
    regression_result: dict = Field(default_factory=dict)


class ExplainErrorRequest(DomainModel):
    session_id: str | None = None
    error_message: str = Field(min_length=1, max_length=4000)


class NextActionsRequest(DomainModel):
    session_id: str | None = None
    status_snapshot: dict = Field(default_factory=dict)


class MessageResponse(DomainModel):
    public_id: str
    session_id: str
    role: str
    capability: str
    sanitized_text: str
    backend_type: str | None = None
    tool_call: dict | None = None
    truncated: bool
    token_estimate: int | None = None
    created_at: str


class SessionResponse(DomainModel):
    public_id: str
    admin_public_id: str
    title: str | None = None
    stage: str
    status: str
    backend_type: str | None = None
    external_provider_key: str | None = None
    total_messages: int
    last_message_at: str | None = None
    created_at: str
    updated_at: str


class ChatResponse(DomainModel):
    session: SessionResponse
    reply: MessageResponse
    backend_type: str
    error_message: str | None = None
    trace_id: str | None = None


class GroundedCitation(DomainModel):
    source_public_id: str
    source_version_public_id: str
    source_name: str = ""
    rank: int
    score: float
    text_preview: str


class GroundedChatResponse(DomainModel):
    session: SessionResponse
    reply: MessageResponse
    backend_type: str
    error_message: str | None = None
    citations: list[GroundedCitation] = Field(default_factory=list)
    trace_id: str | None = None


class NextActionsResponse(DomainModel):
    session: SessionResponse
    reply: MessageResponse
    actions: list[dict]
    backend_type: str
    error_message: str | None = None


class SessionListResponse(DomainModel):
    items: list[SessionResponse]


class MessageListResponse(DomainModel):
    items: list[MessageResponse]


class DefaultRetrievalProfileResponse(DomainModel):
    retrieval_profile_public_id: str | None = None
    name: str | None = None


class SetDefaultRetrievalProfileRequest(DomainModel):
    retrieval_profile_public_id: str = Field(min_length=1)


class WidgetHealthResponse(DomainModel):
    loaded: bool
    backend_type: str
    current_model: str | None = None
    available: bool
    error_message: str | None = None


class DiagnosticsResponse(DomainModel):
    local_available: bool
    local_model_loaded: bool
    configured_model_path: str | None = None
    llama_cpp_installed: bool
    external_fallback_enabled: bool
    external_provider_key: str | None = None
    active_session_count: int
    total_messages: int
    cache_metrics: dict | None = None
    resilience_metrics: dict | None = None
    provider_probes: dict | None = None
