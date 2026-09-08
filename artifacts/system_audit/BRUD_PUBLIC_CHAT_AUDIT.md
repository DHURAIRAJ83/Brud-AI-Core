# BRUD AI — PUBLIC CHAT AUDIT (WS05)
**Audit Date:** 2026-09-07

---

## EXECUTION GRAPH

```
Public User (Browser)
    ↓ POST /chat
backend/api/routes/chat.py
    ↓ check_rate_limit()
    ↓ PublicChatRequest validation
    ↓ evaluate_public_capability_gate() [Phase 18 observation]
    ↓
PublicChatRoutingService.handle_message()
    ↓
[Route Selection via route_availability]
    ├─ CORE_MODEL route → InferenceRuntimeService
    ├─ RAG route → RagRetrievalService + InferenceRuntimeService
    ├─ MEMORY route → MemoryService
    ├─ TRUSTED_WEB route → TrustedWebAnswerService
    ├─ TOOL route → DeterministicToolExecutionService
    └─ FALLBACK → insufficient_text / refusal_text
    ↓
PublicChatResponse (with citations, route_used, evidence_status)
    ↓
Browser
```

---

## COMPONENT INVENTORY

| Component | File | Size | Status |
|-----------|------|------|--------|
| Route | `backend/api/routes/chat.py` | 9 KB | ACTIVE |
| Routing Service | `backend/services/public_chat_routing_service.py` | 43 KB | ACTIVE |
| Rate Limiter | `backend/services/public_chat_rate_limiter.py` | 1.5 KB | ACTIVE |
| Model Resolver | `backend/services/public_model_assignment_resolver.py` | 1.8 KB | ACTIVE |
| RAG Resolver | `backend/services/public_rag_scope_resolver.py` | 3.5 KB | ACTIVE |
| Memory Resolver | `backend/services/public_memory_scope_resolver.py` | 1.9 KB | ACTIVE |
| Citation Adapter | `backend/services/public_citation_adapter.py` | 2.9 KB | ACTIVE |
| Commercial Preflight | `backend/services/public_commercial_preflight_service.py` | 3.2 KB | ACTIVE |
| Chat Orchestration | `backend/services/chat_orchestration_service.py` | 33 KB | ACTIVE |

---

## CORE MODEL MODULES (public_chat)

| Module | File | Status |
|--------|------|--------|
| Route Availability | `core_model/public_chat/route_availability.py` | ACTIVE |
| Input Safety | `core_model/public_chat/input_safety.py` | ACTIVE |
| Output Safety | `core_model/public_chat/output_safety.py` | ACTIVE |
| Language Policy | `core_model/public_chat/language_policy.py` | ACTIVE |
| Clarification | `core_model/public_chat/clarification.py` | ACTIVE |
| Fallback Text | `core_model/public_chat/fallback_text.py` | ACTIVE |
| Help FAQ | `core_model/public_chat/help_faq.py` | ACTIVE |
| Capability Gate | `core_model/capabilities/public_capability_gate.py` | ACTIVE |
| Request Trace | `core_model/capabilities/public_request_trace.py` | ACTIVE |
| Runtime Policy | `core_model/capabilities/public_runtime_policy.py` | ACTIVE |

---

## LANGUAGE HANDLING

| Feature | Implementation | Status |
|---------|----------------|--------|
| Language Detection | `core_model/rag/language_routing.classify_language()` | ACTIVE |
| Tamil Support | `core_model/public_chat/language_policy.py` | ACTIVE |
| Tanglish Detection | `gate.nlp_result.is_tanglish` | ACTIVE |
| Language Continuity | `core_model/conversation/language_continuity.py` | ACTIVE |
| Answer Language Resolution | `resolve_answer_language()` | ACTIVE |

---

## CHAT ORCHESTRATION (Phase 17)

`ChatOrchestrationService` handles:
- Session management (ConversationSessionService)
- Memory retrieval (MemoryService)
- RAG retrieval (RagRetrievalService)
- Context budget (core_model/conversation/context_budget.py)
- Injection guard (core_model/conversation/injection_guard.py)
- Model inference (InferenceRuntimeService)
- Response status (core_model/conversation/response_policy.py)

---

## RATE LIMITING

- Per-IP rate limiting via `check_rate_limit()`
- Config: `public_chat_rate_limit_max_requests` + `public_chat_rate_limit_window_seconds`
- In-memory sliding window (no Redis required)
- **Status:** ACTIVE

---

## KNOWLEDGE GAP OBSERVATION (Phase 19)

After every response, `classify_knowledge_gap()` is called:
- Pure observation layer
- Does NOT alter response
- Logs gap to knowledge_gap tables
- **Status:** ACTIVE (observation only)

---

## PUBLIC CHAT ADMIN ROUTES

| Route | File | Status |
|-------|------|--------|
| GET /admin/public-chat-routing | `routes/public_chat_admin.py` | ACTIVE |
| POST /mini-brain/public-chat-runtime/* | `routes/mini_brain_public_chat_runtime.py` | ACTIVE |

---

## DUPLICATE ANALYSIS

| Component | Duplicate? | Notes |
|-----------|-----------|-------|
| ChatOrchestrationService | NO | Single orchestrator |
| PublicChatRoutingService | NO | Wraps ChatOrchestration, single caller |
| Language classification | NO | Single `classify_language()` from core_model/rag |
| Route availability | NO | Single `resolve_route_availability()` |
| Input/output safety | NO | Single implementations |

---

## FINDINGS

1. **COMPLETE:** Full public chat pipeline implemented
2. **COMPLETE:** Language handling (Tamil/English/Tanglish)
3. **COMPLETE:** Rate limiting active
4. **COMPLETE:** Safety gates (input + output)
5. **COMPLETE:** Knowledge gap observation
6. **NO DUPLICATE ChatEngines** — single authoritative path
7. **PARTIAL:** Streaming not detected — responses appear synchronous

---
*WS05 Complete*
