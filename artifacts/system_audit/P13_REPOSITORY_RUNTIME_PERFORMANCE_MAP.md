# PHASE 13 — REPOSITORY RUNTIME PERFORMANCE MAP
## Brud AI Mini Brain / Admin Assistant Runtime

**Date**: 2026-09-04  
**Scope**: Production Runtime Performance, Context Cache & SSE Streaming (P13.1)  
**Status**: ACTIVE AUDIT & ARCHITECTURAL BASELINE

---

### 1. Executive Summary & Objectives

Phase 13 establishes production-grade runtime performance for Brud AI's Mini Brain / Admin Assistant while maintaining 100% adherence to all Phase 11 and Phase 12 invariants (Canonical Separation, Context Truth Chain, Fail-Closed Governance, Training Gates, Zero-Mock Production, and Secret Redaction).

The two primary technical targets are:
1. **Bounded, Correctness-Aware Context Cache**: Eliminate the ~1072ms repeated 11-subsystem DB aggregation latency for administrative context, dropping warm context lookups to < 5ms while providing deterministic, event-driven invalidation upon state mutations.
2. **True Server-Sent Events (SSE) Streaming**: Provide token-by-token progressive responses to the Admin Chat UI (`ChatPanel.jsx` / `AdminAssistantWidget.jsx`) from native streaming adapters (Local `llama-cpp-python` and External OpenAI/Ollama/OpenRouter providers) without synthetic token splitting or fake streaming, buffering final responses in memory to persist exactly one assistant message per turn.

---

### 2. Current Request Lifecycle & Latency Bottlenecks

#### 2.1 Trace: End-to-End Chat Flow (Phase 12 Baseline)
```
User In ChatPanel.jsx
  │
  ▼
HTTP POST /api/admin/mini-brain/llm-runtime/chat
  │
  ├─► [1] Auth & RBAC (Admin, CSRF header check)
  │
  ├─► [2] MiniBrainDashboardContextService.get_system_context()
  │        ├─ Queries models, providers, datasets, training_jobs,
  │        │  evaluations, rag_collections, continuous_learning,
  │        │  memory_turns, audit_logs, governance_proposals, system_health
  │        └─ Latency: 1,000ms – 1,150ms (SQLite query contention across unindexed tables)
  │
  ├─► [3] MiniBrainRAGRetrievalService.retrieve_relevant_context(query)
  │        └─ Latency: 15ms – 40ms
  │
  ├─► [4] PromptBuilder.build_grounded_admin_prompt(...)
  │        └─ Assembles context snapshot, RAG chunks, memory turns, prompt rules
  │
  ├─► [5] MiniBrainLLMRouter.dispatch(...)
  │        ├─ LlamaCppMiniBrainAdapter or ExternalProviderMiniBrainAdapter
  │        └─ Model Generation Latency: 800ms – 2,500ms (blocking full completion)
  │
  ├─► [6] Secret Redaction & Sanitization (`redact_secrets()`)
  │
  ├─► [7] Persistence: MiniBrainMemoryService.save_turn() (User + Assistant turn)
  │
  ▼
JSON Response { "response": "...", "citations": [...], "diagnostics": {...} }
Total Turnaround: 2.0s – 4.0s (Admin UI waits with spinner until 100% complete)
```

#### 2.2 Latency Distribution (P12 Measured Averages)
| Pipeline Step | Latency (ms) | % of Total | Bottleneck Description |
|---|---|---|---|
| **Context Aggregation** | **1072 ms** | **45.6%** | Repeated queries across 11 SQLite subsystem tables on *every single message* |
| **RAG Retrieval** | 28 ms | 1.2% | Fast in-memory / lightweight SQLite vector lookup |
| **Prompt Assembly** | 2 ms | 0.1% | String formatting and token budgeting |
| **LLM Inference (TTFB)** | 750 ms | 31.9% | Blocked waiting for model generation |
| **LLM Generation** | 480 ms | 20.4% | Token generation time |
| **Persistence & Audit** | 18 ms | 0.8% | SQLite insert into memory_turns and audit_logs |
| **Total Response Time** | **~2350 ms** | **100%** | **User experiences 2.3s of complete silence** |

---

### 3. Context Aggregation Deep Dive

In `backend/services/mini_brain_dashboard_context_service.py`, `get_system_context(force_refresh=False)` aggregates:
1. `models`: Active model, candidate models, parameters, quantization
2. `providers`: Local vs Provider status, health checks
3. `datasets`: Available dataset counts, active training datasets
4. `training`: Training status, job state, lock status (`SignedTrainingAuthorizationToken = ABSENT`)
5. `evaluations`: Latest benchmark score, regression status
6. `rag`: Active RAG collection, embedding models, document counts
7. `continuous_learning`: Buffer size, feedback samples
8. `memory`: Memory turn counts, active session stats
9. `governance`: Pending proposals, active authority mode (`ADVISORY_ONLY`)
10. `audit`: Recent administrative event logs
11. `system_health`: CPU/memory/storage telemetry

**Problem**: Even during rapid multi-turn chats within 5 seconds, all 11 subsystems are queried synchronously from SQLite. This causes database lock contention when concurrent users or streaming requests arrive.

---

### 4. Proposed P13 Architecture

#### 4.1 Bounded Context Cache (`BoundedContextCache`)
- **Location**: Integrated directly in `MiniBrainDashboardContextService`.
- **TTL**: Configurable (default `3` to `5` seconds via `settings.MINI_BRAIN_CONTEXT_CACHE_TTL_SECONDS`).
- **Thread Safety**: Protected with `threading.RLock()` and a single-flight mutex (`_flight_lock`) so 10 concurrent requests result in 1 context build and 9 waiters.
- **Security**: Snapshot serialized and scanned for secrets (`redact_secrets()`); no raw credentials or ORM objects cached.
- **Invalidation Bus**: Explicit `.invalidate_cache(reason=...)` callable from:
  - Model activation / deactivation
  - Provider configuration changes
  - Proposal creation / approval / rejection
  - Dataset upload / deletion
  - Training status updates
  - Evaluation completions
- **Observability**: Metrics tracked: `cache_hit`, `cache_miss`, `cache_expired`, `cache_invalidated`, `rebuild_count`, `context_generation_latency_ms`, `cache_age_ms`.

#### 4.2 SSE Streaming Architecture
- **Endpoint**: `POST /api/admin/mini-brain/llm-runtime/chat/stream`
- **Security & RBAC**: Exact same admin authorization, CSRF token verification, and rate limiting as `/chat`.
- **Adapters**:
  - `LlamaCppMiniBrainAdapter`: Yields chunks from `create_chat_completion(..., stream=True)`.
  - `ExternalProviderMiniBrainAdapter`: Uses `httpx.AsyncClient.stream("POST", ..., json={"stream": True})` yielding raw tokens.
  - Test/Fallback: If an adapter does not support streaming, it yields a single truthful completion event—no artificial synthetic token slicing.
- **Event Framing**:
  ```
  event: start
  data: {"request_id": "...", "session_id": "..."}

  event: metadata
  data: {"citations": [...], "model": "...", "mode": "..."}

  event: token
  data: {"text": "Hello"}

  event: done
  data: {"request_id": "...", "usage": {...}, "latency_ms": 1240}
  ```
- **Cancellation & Backpressure**: Async generator detects client disconnect via `request.is_disconnected()`, terminating adapter stream immediately and releasing DB locks.
- **Persistence Invariant**: Individual tokens are never persisted to SQLite. Tokens are buffered in memory; on stream completion, the full response is scrubbed via `redact_secrets()` and persisted exactly once as an assistant turn in `mini_brain_memory`.

---

### 5. Frontend Streaming Architecture (Zero Redesign)

- In `apps/admin-dashboard/src/services/api.js`:
  - Add `lrChatStream(payload, onEvent, signal)` using `fetch` with `ReadableStream` decoding UTF-8 chunks and parsing SSE event lines.
- In `ChatPanel.jsx`:
  - Retain all visual styles, buttons, tabs, context inspector, and layout.
  - When user sends message:
    1. Render User message in UI.
    2. Add placeholder Assistant message with `isStreaming: true`.
    3. On `metadata`: attach citations.
    4. On `token`: append `text` directly to the active assistant message.
    5. On `done` / `error`: set `isStreaming: false`.
    6. If SSE stream fails or server returns fallback directive, transparently retry via non-streaming `lrChat`.

---

### 6. Architectural Invariants Compliance Checklist
- [x] **G1 — Canonical Runtime Separation**: Chat routes to `MiniBrainLlmRuntimeService`; Governance proposals route to `AdminAssistantService.propose()`.
- [x] **G2 — Context Truth Chain**: Database remains authoritative; cache is strictly a TTL-bounded optimization layer with immediate mutation invalidation.
- [x] **G3 — Governance**: `authority_mode = ADVISORY_ONLY`, `SignedTrainingAuthorizationToken = ABSENT`, Maker != Checker enforced.
- [x] **G4 — Zero Mock Production**: No mock adapters reachable in production paths; truthful streaming only.
- [x] **G5 — Truthful Failure**: Failures emit explicit error events; zero hallucinations.
- [x] **G6 — Secret Protection**: Redaction filter applied to context cache serialization, SSE token streams, and memory persistence.
