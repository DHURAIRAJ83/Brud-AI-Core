"""`PublicChatRoutingService` (Steps 19-20) -- the public-facing
orchestrator that replaces the `/api/chat` placeholder. It owns the
bounded pipeline (validate -> normalize -> language -> input safety ->
Phase 17 classification -> route availability -> route execution ->
evidence/output safety -> language policy -> structured response ->
audit) and contains zero duplicated model-inference, RAG-retrieval,
memory, citation, or language-classification logic -- every step below
calls an existing service or Phase 17 module. `ChatOrchestrationService`
is reused directly (never forked) via the three small additive
parameters Phase 18 added to `send_message()`.
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.database.connection import database_connection
from backend.database.repositories.base import RepositoryError, ValidationError
from backend.database.repositories.conversation_memory import ConversationMemoryRepository
from backend.database.repositories.inference_runtime import InferenceRuntimeRepository
from backend.database.repositories.model_release import ModelReleaseRepository
from backend.database.repositories.phase2 import AuditLogRepository
from backend.database.repositories.public_chat import PublicChatRoutingRepository
from backend.database.repositories.rag import RagRepository
from backend.models.conversation_memory import MemoryRetrieveRequest, MessageCreate, SessionCreate
from backend.models.domain import AuditEventCreate, AuditOutcome
from backend.models.public_chat import PublicChatRequest, PublicChatResponse, PublicCitation
from backend.services.chat_orchestration_service import ChatOrchestrationService
from backend.services.conversation_session_service import ConversationSessionService
from backend.services.deterministic_tool_execution_service import (
    DeterministicToolExecutionService,
)
from backend.services.deterministic_tool_registry import get_tool_descriptor
from backend.services.inference_runtime_service import InferenceRuntimeService
from backend.services.knowledge_gap_capability_linkage_service import (
    KnowledgeGapCapabilityLinkageService,
)
from backend.services.knowledge_gap_capture_service import (
    MAX_CLARIFICATION_ATTEMPTS,
    KnowledgeGapCaptureService,
)
from backend.services.knowledge_routing_classification_service import (
    KnowledgeRoutingClassificationService,
)
from backend.services.memory_service import MemoryService
from backend.services.model_assignment_service import ModelAssignmentService
from backend.services.public_citation_adapter import public_citations_for_response
from backend.services.public_memory_scope_resolver import PublicMemoryScopeResolver
from backend.services.public_model_assignment_resolver import PublicModelAssignmentResolver
from backend.services.public_rag_scope_resolver import PublicRagScopeResolver
from backend.services.rag_retrieval_service import RagRetrievalService
from backend.services.trusted_web_answer_service import TrustedWebAnswerService
from core_model.public_chat import FALLBACK_REASON_CODES
from core_model.public_chat.ambiguity_supplemental_patterns import (
    evaluate_supplemental_ambiguity,
)
from core_model.public_chat.clarification import clarifying_question
from core_model.public_chat.fallback_text import insufficient_text, refusal_text
from core_model.public_chat.input_safety import evaluate_input_safety
from core_model.public_chat.language_policy import resolve_answer_language
from core_model.public_chat.output_safety import evaluate_output_safety
from core_model.public_chat.route_availability import resolve_route_availability
from core_model.rag.language_routing import classify_language
from core_model.tool_gateway.input_extraction import extract_tool_input
from core_model.tool_gateway.mcp_contract import ToolInvocationRequest, ToolPermissionContext
from core_model.tool_gateway.tool_result_text import format_tool_result_text
from core_model.tool_gateway.tool_selection import select_tool_for_request
from core_model.web_search.query_classification import classify_web_category

logger = logging.getLogger(__name__)

_ACTOR_REFERENCE = "public_chat_system"

# Any reason code meaning "this needed current Web information and didn't
# get it" -- whether the route was never attempted (`trusted_web_unavailable`,
# Phase 18) or genuinely attempted and failed (the Phase 20 `web_*` codes) --
# surfaces the same public `freshness_status` hint, distinct from an
# unrelated `insufficient` (e.g. a disabled model or unsupported tool).
_WEB_NEEDED_REASON_CODES = frozenset(
    {
        "trusted_web_unavailable",
        "web_provider_unavailable",
        "web_quota_exceeded",
        "web_no_trusted_source",
        "web_evidence_insufficient",
        "web_fetch_blocked",
    }
)


class PublicChatRoutingService:
    def __init__(
        self,
        settings: Settings,
        *,
        trusted_web_service: TrustedWebAnswerService | None = None,
    ) -> None:
        """`trusted_web_service` is injectable purely for tests --
        mirroring `TrustedWebAnswerService`'s own injectable-transport
        pattern one layer up, so a deterministic fake can be substituted
        without a real network call. Production callers never pass it."""

        self.settings = settings
        db_path = settings.resolved_database_path
        self.repository = ConversationMemoryRepository(db_path)
        self.routing_repository = PublicChatRoutingRepository(db_path)
        inference_repository = InferenceRuntimeRepository(db_path)
        release_repository = ModelReleaseRepository(db_path)
        self.runtime_service = InferenceRuntimeService(
            inference_repository, release_repository, settings
        )
        self.assignment_service = ModelAssignmentService(
            inference_repository, release_repository, self.runtime_service, settings
        )
        self.session_service = ConversationSessionService(self.repository, settings)
        self.memory_service = MemoryService(self.repository, settings)
        self.rag_retrieval_service = RagRetrievalService(RagRepository(db_path), settings)
        self.orchestration = ChatOrchestrationService(
            self.repository,
            inference_repository,
            self.runtime_service,
            self.assignment_service,
            self.session_service,
            self.memory_service,
            self.rag_retrieval_service,
            settings,
        )
        self.rag_scope_resolver = PublicRagScopeResolver(db_path, settings)
        self.memory_scope_resolver = PublicMemoryScopeResolver(db_path, settings)
        self.model_assignment_resolver = PublicModelAssignmentResolver(db_path, settings)
        self.classification_service = KnowledgeRoutingClassificationService(settings)
        self.gap_capture_service = KnowledgeGapCaptureService(settings)
        self.gap_linkage_service = KnowledgeGapCapabilityLinkageService(settings)
        self.trusted_web_service = trusted_web_service or TrustedWebAnswerService(settings)
        self.tool_execution_service = DeterministicToolExecutionService(settings)
        self._audit = AuditLogRepository(db_path) if settings.audit_enabled else None
        self._db_path = db_path

    # -- public entry point -----------------------------------------------------------------

    def handle_message(self, payload: PublicChatRequest) -> PublicChatResponse:
        started = time.perf_counter()
        request_id = str(uuid4())
        text = payload.message
        input_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

        language = classify_language(text)
        detected_language = language["language_category"]
        override = payload.language_override if payload.language_override != "auto" else None
        lang_decision = resolve_answer_language(
            detected_language_category=detected_language, explicit_override=override
        )
        answer_language = lang_decision.answer_language

        safety_decision = evaluate_input_safety(text)
        if safety_decision.decision == "refuse":
            response = self._build_refusal_response(
                request_id=request_id,
                detected_language=detected_language,
                answer_language=answer_language,
                reason_codes=safety_decision.reason_codes,
            )
            self._record_event(
                request_id=request_id, input_hash=input_hash,
                recommended_route="refuse", resolved_route="refuse", route_status="executable",
                evidence_status="none", detected_language=detected_language,
                answer_language=answer_language, safety_status="refused",
                fallbacks_attempted=(), latency_ms=self._elapsed_ms(started),
                conversation_id=payload.conversation_id,
            )
            self._capture_gap(
                text=text, resolved_route="refuse", safety_status="refused",
                evidence_status="none", confidence_band="unknown", fallbacks_attempted=(),
                clarification_required=False, detected_language=detected_language,
            )
            return response

        try:
            classification = self.classification_service.classify_text(
                text, actor_reference=_ACTOR_REFERENCE, persist=False,
            )
        except Exception:
            logger.exception("public_chat_classification_failed")
            response = self._build_insufficient_response(
                request_id=request_id, detected_language=detected_language,
                answer_language=answer_language, resolved_route="insufficient",
                reason_codes=("classification_failed",),
                safety_status=self._safety_status(safety_decision.decision),
            )
            self._record_event(
                request_id=request_id, input_hash=input_hash,
                recommended_route="insufficient", resolved_route="insufficient",
                route_status="unavailable", evidence_status="none",
                detected_language=detected_language, answer_language=answer_language,
                safety_status=self._safety_status(safety_decision.decision),
                fallbacks_attempted=("classification_failed",),
                latency_ms=self._elapsed_ms(started), error_code="CHAT_INTERNAL_ERROR",
                conversation_id=payload.conversation_id,
            )
            self._capture_gap(
                text=text, resolved_route="insufficient",
                safety_status=self._safety_status(safety_decision.decision),
                evidence_status="none", confidence_band="unknown",
                fallbacks_attempted=("classification_failed",), clarification_required=False,
                detected_language=detected_language,
            )
            return response

        recommended_route = classification["execution_route"]

        # Phase 19 Step 31: a narrow, versioned supplemental ambiguity
        # check for the one mixed Tamil-English unclear-pronoun gap
        # found during Phase 18's live browser verification -- Phase
        # 17's own classification and policy are never modified; this
        # only overrides the *recommended* route for this one request
        # when Phase 17 did not already recommend `clarify` itself.
        if recommended_route != "clarify":
            supplemental_ambiguity = evaluate_supplemental_ambiguity(text)
            if supplemental_ambiguity.matched:
                recommended_route = "clarify"
                classification = {
                    **classification,
                    "execution_route": "clarify",
                    "ambiguity_reason_codes": (supplemental_ambiguity.reason_code,),
                }

        rag_scope_available = False
        rag_scope = None
        if recommended_route == "approved_rag":
            rag_scope = self.rag_scope_resolver.resolve()
            rag_scope_available = rag_scope is not None

        memory_policy_active = False
        memory_has_content = False
        if recommended_route == "memory" and payload.memory_consent:
            memory_scope = self.memory_scope_resolver.resolve()
            if memory_scope is not None:
                memory_policy_active = True
                if payload.conversation_id:
                    memory_has_content = self._memory_has_content(
                        retrieval_profile_public_id=memory_scope.retrieval_profile_public_id,
                        participant_scope_key=payload.conversation_id,
                        query=text,
                    )

        trusted_web_available = False
        if recommended_route == "trusted_web":
            trusted_web_available = self.trusted_web_service.is_available()

        selected_tool_name: str | None = None
        tool_available = False
        if recommended_route == "tool":
            selected_tool_name = select_tool_for_request(
                intent=classification.get("intent"), text=text
            )
            if selected_tool_name is not None:
                descriptor = get_tool_descriptor(selected_tool_name)
                tool_available = descriptor is not None and descriptor.public_enabled

        availability = resolve_route_availability(
            recommended_route=recommended_route,
            rag_scope_available=rag_scope_available,
            memory_consent_given=payload.memory_consent,
            memory_policy_active=memory_policy_active,
            memory_has_content=memory_has_content,
            trusted_web_available=trusted_web_available,
            tool_available=tool_available,
        )

        safety_status = self._safety_status(safety_decision.decision)

        unresolved_after_clarification = False
        if availability.resolved_route == "clarify":
            response = self._build_clarify_response(
                request_id=request_id, detected_language=detected_language,
                answer_language=answer_language,
                reason_codes=classification.get("ambiguity_reason_codes")
                or classification.get("all_reason_codes", ()),
                safety_status=safety_status,
            )
            if payload.conversation_id:
                prior_attempts = self.routing_repository.count_resolved_route_for_conversation(
                    payload.conversation_id, "clarify"
                )
                unresolved_after_clarification = prior_attempts >= MAX_CLARIFICATION_ATTEMPTS - 1
        elif availability.resolved_route == "refuse":
            response = self._build_refusal_response(
                request_id=request_id, detected_language=detected_language,
                answer_language=answer_language,
                reason_codes=classification.get("all_reason_codes", ()),
            )
            safety_status = "refused"
        elif availability.resolved_route == "insufficient":
            reason_codes = availability.reason_codes
            if recommended_route == "tool" and selected_tool_name is None:
                # A genuinely unsupported operation (e.g. `ask_code`,
                # which has no matching Phase 20 tool) is a distinct,
                # more honest reason than the generic "route disabled"
                # `tool_unavailable` -- Step 22's own requirement.
                reason_codes = ("tool_unsupported",)
            response = self._build_insufficient_response(
                request_id=request_id, detected_language=detected_language,
                answer_language=answer_language, resolved_route=recommended_route,
                reason_codes=reason_codes, safety_status=safety_status,
            )
        elif availability.resolved_route == "trusted_web":
            response = self._execute_trusted_web_route(
                text=text, request_id=request_id, detected_language=detected_language,
                answer_language=answer_language, safety_status=safety_status,
                classification=classification,
            )
        elif availability.resolved_route == "tool":
            response = self._execute_tool_route(
                text=text, request_id=request_id, detected_language=detected_language,
                answer_language=answer_language, safety_status=safety_status,
                tool_name=selected_tool_name, classification=classification,
            )
        else:
            response = self._execute_evidence_route(
                resolved_route=availability.resolved_route,
                payload=payload, text=text, request_id=request_id,
                detected_language=detected_language, answer_language=answer_language,
                rag_scope=rag_scope, safety_status=safety_status,
                classification=classification,
            )
            safety_status = response.safety_status

        self._record_event(
            request_id=request_id, input_hash=input_hash,
            recommended_route=recommended_route, resolved_route=response.route_used,
            route_status=availability.availability_status, evidence_status=response.evidence_status,
            detected_language=detected_language, answer_language=response.answer_language,
            safety_status=safety_status, fallbacks_attempted=tuple(response.fallbacks_attempted),
            latency_ms=self._elapsed_ms(started), conversation_id=response.conversation_id,
        )
        self._capture_gap(
            text=text, resolved_route=response.route_used, safety_status=safety_status,
            evidence_status=response.evidence_status, confidence_band=response.confidence_band,
            fallbacks_attempted=tuple(response.fallbacks_attempted),
            clarification_required=response.clarification_required,
            detected_language=detected_language,
            domain=classification.get("domain"), subdomain=classification.get("subdomain"),
            intent=classification.get("intent"), freshness=classification.get("freshness"),
            unresolved_after_clarification=unresolved_after_clarification,
            involves_memory=(response.route_used == "memory"),
        )
        return response

    def _capture_gap(
        self, *, text: str, resolved_route: str, safety_status: str, evidence_status: str,
        confidence_band: str, fallbacks_attempted: tuple[str, ...], clarification_required: bool,
        detected_language: str, domain: str | None = None, subdomain: str | None = None,
        intent: str | None = None, freshness: str | None = None,
        unresolved_after_clarification: bool = False, involves_memory: bool = False,
    ) -> None:
        """Fail-safe, best-effort knowledge-gap capture (Phase 19 Step
        14) -- never raises, never delays or alters the public response
        that was already built and recorded above this call."""

        if not self.settings.knowledge_gap_capture_enabled:
            return
        try:
            self.gap_capture_service.capture_safe(
                message=text, resolved_route=resolved_route, safety_status=safety_status,
                evidence_status=evidence_status, confidence_band=confidence_band,
                fallbacks_attempted=fallbacks_attempted,
                clarification_required=clarification_required,
                detected_language=detected_language, domain=domain, subdomain=subdomain,
                intent=intent, freshness=freshness,
                unresolved_after_clarification=unresolved_after_clarification,
                involves_memory=involves_memory,
            )
        except Exception:
            logger.exception("public_chat_gap_capture_integration_failed")

    def _link_capability_gap_resolution(
        self, *, resolved_route: str, text: str, detected_language: str,
        domain: str | None, intent: str | None, freshness: str | None,
        search_event_public_id: str | None = None, tool_execution_public_id: str | None = None,
    ) -> None:
        """Fail-safe, best-effort knowledge-gap capability-resolution
        linkage (Phase 20 Step 26) -- never raises, never alters the
        already-built public response. `KnowledgeGapCapabilityLinkageService`
        itself already catches its own errors and returns `None` on any
        failure or no-match; this is an additional outer guard, mirroring
        `_capture_gap`'s own double-wrapped defense-in-depth."""

        if not self.settings.knowledge_gap_capture_enabled:
            return
        try:
            self.gap_linkage_service.link_if_matched(
                resolved_route=resolved_route, message=text, detected_language=detected_language,
                domain=domain, intent=intent, freshness=freshness,
                search_event_public_id=search_event_public_id,
                tool_execution_public_id=tool_execution_public_id,
            )
        except Exception:
            logger.exception("public_chat_gap_capability_linkage_integration_failed")

    # -- route execution ----------------------------------------------------------------------

    def _execute_evidence_route(
        self, *, resolved_route: str, payload: PublicChatRequest, text: str, request_id: str,
        detected_language: str, answer_language: str, rag_scope, safety_status: str,
        classification: dict[str, Any],
    ) -> PublicChatResponse:
        assignment_public_id = self.model_assignment_resolver.resolve()
        if assignment_public_id is None:
            return self._build_insufficient_response(
                request_id=request_id, detected_language=detected_language,
                answer_language=answer_language, resolved_route=resolved_route,
                reason_codes=("model_assignment_unavailable",), safety_status=safety_status,
            )

        try:
            session_public_id, conversation_id = self._resolve_or_create_session(
                payload=payload, assignment_public_id=assignment_public_id, rag_scope=rag_scope,
            )
        except Exception:
            # Any unexpected failure here (including a lock-contention
            # OperationalError surfacing from framework-level audit
            # writes -- never just the ValidationError/RepositoryError
            # this codebase mostly raises) must still degrade to an
            # honest bounded response, never an internal-error leak to
            # a public caller (Step 23/24).
            logger.exception("public_chat_session_setup_failed")
            return self._build_insufficient_response(
                request_id=request_id, detected_language=detected_language,
                answer_language=answer_language, resolved_route=resolved_route,
                reason_codes=("model_assignment_unavailable",), safety_status=safety_status,
            )

        evidence_mode_by_route = {
            "core_model": "model_only", "approved_rag": "rag_only", "memory": "memory_only",
        }
        evidence_mode = evidence_mode_by_route[resolved_route]
        memory_profile_public_id = None
        if resolved_route == "memory":
            memory_scope = self.memory_scope_resolver.resolve()
            memory_profile_public_id = (
                memory_scope.retrieval_profile_public_id if memory_scope else None
            )

        try:
            result = self.orchestration.send_message(
                session_public_id,
                MessageCreate(
                    message=text,
                    explicit_language_request=payload.language_override
                    if payload.language_override != "auto" else None,
                    memory_retrieval_profile_public_id=memory_profile_public_id,
                ),
                _ACTOR_REFERENCE,
                required_scope="public_chat",
                evidence_mode=evidence_mode,
                rag_filters=rag_scope.filters if rag_scope else None,
            )
        except Exception:
            # Same defensive-degrade posture as session setup above --
            # never let an unexpected orchestration failure escape as a
            # raw internal error.
            logger.exception("public_chat_orchestration_failed")
            reason = (
                "rag_insufficient_evidence" if resolved_route == "approved_rag"
                else "model_assignment_unavailable"
            )
            return self._build_insufficient_response(
                request_id=request_id, detected_language=detected_language,
                answer_language=answer_language, resolved_route=resolved_route,
                reason_codes=(reason,), safety_status=safety_status,
            )

        answer_status = result["response"].get("answer_status")
        answer_text = result.get("answer_text")

        no_usable_answer_statuses = (
            "insufficient_evidence", "retrieval_failed", "generation_failed", "blocked_context",
        )
        if answer_text is None or answer_status in no_usable_answer_statuses:
            if resolved_route == "approved_rag":
                reason = "rag_insufficient_evidence"
            elif resolved_route == "memory":
                reason = "memory_unavailable"
            else:
                reason = "model_assignment_unavailable"
            return self._build_insufficient_response(
                request_id=request_id, detected_language=detected_language,
                answer_language=answer_language, resolved_route=resolved_route,
                reason_codes=(reason,), safety_status=safety_status,
                conversation_id=conversation_id,
            )

        output_decision = evaluate_output_safety(
            answer_text,
            prompt_leakage=bool(result["response"].get("prompt_leakage")),
            role_token_leakage=bool(result["response"].get("role_token_leakage")),
        )
        if not output_decision.passed:
            self._audit_event(
                action="output_safety_blocked", resource_public_id=request_id,
                metadata={"reasons": list(output_decision.blocked_reasons)},
            )
            return self._build_insufficient_response(
                request_id=request_id, detected_language=detected_language,
                answer_language=answer_language, resolved_route=resolved_route,
                reason_codes=("output_safety_blocked",), safety_status="output_blocked",
                conversation_id=conversation_id,
            )

        evidence_status = self._evidence_status(resolved_route, answer_status)
        citations: list[PublicCitation] = []
        source_types: list[str] = []
        memory_used = bool(result["response"].get("memory_used"))
        if resolved_route == "approved_rag":
            source_types = ["rag"]
            citations = self._public_citations(result["response"].get("public_id"))
        elif resolved_route == "memory":
            source_types = ["memory"]
        else:
            source_types = ["model"]

        confidence_band = self._confidence_band(resolved_route, evidence_status, "executable")

        return PublicChatResponse(
            reply=answer_text,
            detected_language=detected_language,
            answer_language=answer_language,
            route_used=resolved_route,
            route_reason_codes=list(classification.get("all_reason_codes", ())),
            evidence_status=evidence_status,
            confidence_band=confidence_band,
            source_types=source_types,
            citations=citations,
            memory_used=memory_used,
            clarification_required=False,
            insufficient_evidence=False,
            safety_status=safety_status,
            fallbacks_attempted=[],
            request_id=request_id,
            conversation_id=conversation_id,
        )

    def _execute_trusted_web_route(
        self, *, text: str, request_id: str, detected_language: str, answer_language: str,
        safety_status: str, classification: dict[str, Any],
    ) -> PublicChatResponse:
        """Phase 20 Step 14/25 -- current information is never silently
        routed to the core model here: any non-`success` outcome from
        `TrustedWebAnswerService.answer()` degrades to the same honest
        `insufficient` shape every other route uses, carrying the
        specific reason code (`web_provider_unavailable`,
        `web_quota_exceeded`, `web_no_trusted_source`,
        `web_evidence_insufficient`, `web_fetch_blocked`) rather than a
        stale model fallback."""

        freshness = classification.get("freshness") or "standard"
        web_category = classify_web_category(
            domain=classification.get("domain"),
            subdomain=classification.get("subdomain"),
            freshness=freshness,
        )
        result = self.trusted_web_service.answer(
            query_text=text, web_category=web_category, language=detected_language,
            answer_language=answer_language, freshness=freshness, request_id=request_id,
        )
        if result.status != "success" or result.reply_text is None:
            return self._build_insufficient_response(
                request_id=request_id, detected_language=detected_language,
                answer_language=answer_language, resolved_route="trusted_web",
                reason_codes=result.reason_codes, safety_status=safety_status,
            )

        citations = [PublicCitation(**citation) for citation in result.citations]
        evidence_status = "conflicting" if result.conflict_status not in (
            "no_conflict", "minor_difference"
        ) else "grounded"
        confidence_band = "medium" if evidence_status == "conflicting" else "high"

        self._link_capability_gap_resolution(
            resolved_route="trusted_web", text=text, detected_language=detected_language,
            domain=classification.get("domain"), intent=classification.get("intent"),
            freshness=freshness, search_event_public_id=result.search_event_public_id,
        )

        return PublicChatResponse(
            reply=result.reply_text,
            detected_language=detected_language, answer_language=answer_language,
            route_used="trusted_web", route_reason_codes=list(result.reason_codes),
            evidence_status=evidence_status, confidence_band=confidence_band,
            source_types=["web"], citations=citations, memory_used=False,
            clarification_required=False, insufficient_evidence=False,
            safety_status=safety_status, fallbacks_attempted=[], request_id=request_id,
            freshness_status=result.freshness_status, limitations=list(result.limitations),
        )

    def _execute_tool_route(
        self, *, text: str, request_id: str, detected_language: str, answer_language: str,
        safety_status: str, tool_name: str | None, classification: dict[str, Any],
    ) -> PublicChatResponse:
        """Phase 20 Step 21/22 -- the deterministic result is
        authoritative; only the surrounding reply text is templated
        (never the model), so the exact numeric result can never be
        altered downstream of `DeterministicToolExecutionService`."""

        assert tool_name is not None  # caller only reaches here when a tool was selected+available
        tool_input = extract_tool_input(tool_name, text)
        if tool_input is None:
            return self._build_insufficient_response(
                request_id=request_id, detected_language=detected_language,
                answer_language=answer_language, resolved_route="tool",
                reason_codes=("tool_input_invalid",), safety_status=safety_status,
            )

        result = self.tool_execution_service.execute(
            ToolInvocationRequest(
                tool_name=tool_name, input_payload=tool_input, request_id=request_id,
                is_public_request=True,
            ),
            ToolPermissionContext(
                is_public_request=True, is_admin_request=False,
                external_mcp_enabled=self.settings.external_mcp_enabled,
            ),
        )

        if result.status != "success" or result.output_payload is None:
            reason = {
                "input_invalid": "tool_input_invalid",
                "disabled": "tool_disabled",
                "unsupported": "tool_unsupported",
                "rate_limited": "tool_rate_limited",
                "timeout": "tool_timeout",
                "execution_failed": "tool_execution_failed",
            }.get(result.status, "tool_unsupported")
            return self._build_insufficient_response(
                request_id=request_id, detected_language=detected_language,
                answer_language=answer_language, resolved_route="tool",
                reason_codes=(reason,), safety_status=safety_status,
            )

        reply = format_tool_result_text(
            tool_name=tool_name, output_payload=result.output_payload,
            answer_language=answer_language,
        )

        self._link_capability_gap_resolution(
            resolved_route="tool", text=text, detected_language=detected_language,
            domain=classification.get("domain"), intent=classification.get("intent"),
            freshness=classification.get("freshness"),
            tool_execution_public_id=result.execution_public_id,
        )

        return PublicChatResponse(
            reply=reply, detected_language=detected_language, answer_language=answer_language,
            route_used="tool", route_reason_codes=[],
            evidence_status="deterministic", confidence_band="high",
            source_types=["tool"], citations=[], memory_used=False,
            clarification_required=False, insufficient_evidence=False,
            safety_status=safety_status, fallbacks_attempted=[], request_id=request_id,
            tool_name=result.tool_name, tool_version=result.tool_version,
            tool_status=result.status,
        )

    def _resolve_or_create_session(
        self, *, payload: PublicChatRequest, assignment_public_id: str, rag_scope,
    ) -> tuple[str, str]:
        if payload.conversation_id:
            with self.repository.transaction() as connection:
                existing = connection.execute(
                    "SELECT public_id, status FROM conversation_sessions WHERE public_id=?",
                    (payload.conversation_id,),
                ).fetchone()
            if existing is not None and existing["status"] == "active":
                return existing["public_id"], existing["public_id"]

        memory_policy_public_id = self._active_memory_policy_public_id()
        if memory_policy_public_id is None:
            raise ValidationError("no active memory policy available for public chat sessions")

        participant_scope_key = payload.conversation_id or str(uuid4())
        session = self.session_service.create_session(
            SessionCreate(
                session_mode="session_memory",
                memory_policy_public_id=memory_policy_public_id,
                participant_type="future_user_reference",
                participant_scope_key=participant_scope_key,
                model_assignment_public_id=assignment_public_id,
                rag_retrieval_profile_public_id=(
                    rag_scope.retrieval_profile_public_id if rag_scope else None
                ),
            ),
            _ACTOR_REFERENCE,
        )
        return session["public_id"], session["public_id"]

    def _active_memory_policy_public_id(self) -> str | None:
        with database_connection(self._db_path) as connection:
            row = connection.execute(
                "SELECT public_id FROM conversation_memory_policies "
                "WHERE lifecycle_status='active' ORDER BY id DESC LIMIT 1"
            ).fetchone()
            return row["public_id"] if row else None

    def _memory_has_content(
        self, *, retrieval_profile_public_id: str, participant_scope_key: str, query: str
    ) -> bool:
        try:
            result = self.memory_service.retrieve(
                MemoryRetrieveRequest(
                    retrieval_profile_public_id=retrieval_profile_public_id,
                    participant_scope_key=participant_scope_key,
                    query=query,
                ),
                _ACTOR_REFERENCE,
            )
            return bool(result.get("results"))
        except (ValidationError, RepositoryError):
            return False

    def _public_citations(self, grounded_response_public_id: str | None) -> list[PublicCitation]:
        if not grounded_response_public_id:
            return []
        with database_connection(self._db_path) as connection:
            rows = public_citations_for_response(connection, grounded_response_public_id)
        return [PublicCitation(**row) for row in rows]

    # -- non-executing routes -----------------------------------------------------------------

    def _build_clarify_response(
        self, *, request_id: str, detected_language: str, answer_language: str,
        reason_codes: tuple[str, ...], safety_status: str,
    ) -> PublicChatResponse:
        question = clarifying_question(
            reason_codes=tuple(reason_codes), answer_language=answer_language
        )
        return PublicChatResponse(
            reply=question, detected_language=detected_language, answer_language=answer_language,
            route_used="clarify", route_reason_codes=list(reason_codes), evidence_status="none",
            confidence_band="high", source_types=[], citations=[], memory_used=False,
            clarification_required=True, insufficient_evidence=False, safety_status=safety_status,
            fallbacks_attempted=[], request_id=request_id,
        )

    def _build_refusal_response(
        self, *, request_id: str, detected_language: str, answer_language: str,
        reason_codes: tuple[str, ...],
    ) -> PublicChatResponse:
        return PublicChatResponse(
            reply=refusal_text(answer_language=answer_language),
            detected_language=detected_language,
            answer_language=answer_language, route_used="refuse",
            route_reason_codes=list(reason_codes),
            evidence_status="none", confidence_band="high", source_types=[], citations=[],
            memory_used=False, clarification_required=False, insufficient_evidence=False,
            safety_status="refused", fallbacks_attempted=[], request_id=request_id,
        )

    def _build_insufficient_response(
        self, *, request_id: str, detected_language: str, answer_language: str, resolved_route: str,
        reason_codes: tuple[str, ...], safety_status: str, conversation_id: str | None = None,
    ) -> PublicChatResponse:
        fallbacks = [code for code in reason_codes if code in FALLBACK_REASON_CODES]
        web_unavailable = any(code in _WEB_NEEDED_REASON_CODES for code in reason_codes)
        freshness_status = "current_information_requires_web" if web_unavailable else None
        return PublicChatResponse(
            reply=insufficient_text(
                answer_language=answer_language, reason_codes=tuple(reason_codes)
            ),
            detected_language=detected_language, answer_language=answer_language,
            route_used="insufficient", route_reason_codes=list(reason_codes),
            evidence_status="insufficient",
            confidence_band="low" if reason_codes else "unknown", source_types=[], citations=[],
            memory_used=False, clarification_required=False, insufficient_evidence=True,
            safety_status=safety_status, fallbacks_attempted=fallbacks, request_id=request_id,
            conversation_id=conversation_id, freshness_status=freshness_status,
        )

    # -- helpers --------------------------------------------------------------------------------

    @staticmethod
    def _safety_status(decision: str) -> str:
        return {
            "allow": "safe", "allow_with_caution": "caution",
            "needs_review": "review_flagged", "refuse": "refused",
        }[decision]

    @staticmethod
    def _evidence_status(resolved_route: str, answer_status: str | None) -> str:
        if resolved_route == "core_model":
            return "model_only"
        if answer_status == "completed":
            return "grounded"
        if answer_status == "completed_with_warning":
            return "partially_grounded"
        return "insufficient"

    @staticmethod
    def _confidence_band(
        resolved_route: str, evidence_status: str, availability_status: str
    ) -> str:
        if availability_status != "executable":
            return "unknown"
        if evidence_status == "grounded":
            return "high"
        if evidence_status in ("model_only", "partially_grounded"):
            return "medium"
        if evidence_status in ("insufficient", "conflicting", "none"):
            return "low"
        return "unknown"

    @staticmethod
    def _elapsed_ms(started: float) -> int:
        return int((time.perf_counter() - started) * 1000)

    def _record_event(self, **values: Any) -> None:
        try:
            self.routing_repository.record_event(values)
        except Exception:
            logger.exception("public_chat_routing_event_write_failed")

    def _audit_event(
        self, *, action: str, resource_public_id: str, metadata: dict[str, Any]
    ) -> None:
        if self._audit is None:
            return
        try:
            self._audit.append(
                AuditEventCreate(
                    event_type=f"public_chat_{action}", actor_type="system",
                    actor_reference=_ACTOR_REFERENCE, action=action,
                    resource_type="public_chat_routing_event",
                    resource_public_id=resource_public_id,
                    outcome=AuditOutcome.SUCCESS, metadata=metadata,
                )
            )
        except Exception:
            logger.exception("public_chat_audit_write_failed", extra={"action": action})


__all__ = ["PublicChatRoutingService"]
