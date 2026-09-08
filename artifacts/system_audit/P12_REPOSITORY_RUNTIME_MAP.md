# P12.1 — Complete Repository Runtime Map

**System**: Brud AI Mini Brain / Admin Assistant Intelligence Layer  
**Audit Stage**: Phase 12 Operational Hardening & Real-World Validation  
**Date**: September 4, 2026  
**Status**: 🟢 **VERIFIED CANONICAL ARCHITECTURE**  

---

## 1. End-to-End Request Call Graph

```
[Admin User in Browser]
       │
       ▼
[Frontend Component]
   - apps/admin-dashboard/src/components/chat/ChatPanel.jsx
   - apps/admin-dashboard/src/components/admin-assistant/AdminAssistantWidget.jsx
       │
       │ HTTP POST /api/admin/mini-brain/llm-runtime/chat
       │ Headers: x-admin-id: <admin_uuid>, x-csrf-token: <token>
       ▼
[FastAPI Router Layer]
   - backend/api/routes/mini_brain_llm_runtime.py
       │
       │ Depends(require_admin), CsrfDependency, SettingsDependency
       ▼
[MiniBrainLlmRuntimeService]
   - backend/services/mini_brain_llm_runtime_service.py
       │
       ├─► [Input Sanitization & Secret Scrubbing]
       │      - core_model/mini_brain/llm_runtime/message_sanitizer.py
       │      - backend/core/json_utils.py (redact_secrets)
       │
       ├─► [Session Ensure & Deduplication Guard]
       │      - backend/database/repositories/mini_brain_llm_runtime.py
       │
       ├─► [Admin Action Intent Matching (Advisory Only)]
       │      - core_model/admin_assistant/chat_action_bridge.py
       │      - If matched: backend/services/admin_assistant_service.py (propose)
       │
       ├─► [Live Dashboard Context Aggregation (11 Subsystems)]
       │      - backend/services/mini_brain_dashboard_context_service.py
       │
       ├─► [RAG Retrieval (When Grounded Chat / KB Enabled)]
       │      - backend/services/rag_retrieval_service.py
       │      - backend/database/repositories/rag.py
       │
       ├─► [Conversation Memory & History]
       │      - backend/database/repositories/mini_brain_llm_runtime.py
       │
       ├─► [Prompt Builder]
       │      - core_model/mini_brain/llm_runtime/prompt_builder.py
       │      - System Prompt + Precedence + 11 Subsystem Block + Citations + History + User Message
       │
       ▼
[Model Router & Provider Adapters]
   - backend/services/mini_brain_llm_adapter.py
   - backend/services/provider_fallback_policy.py
       │
       ├─► Local Adapter: LlamaCppMiniBrainAdapter (qwen2.5-1.5b-instruct-q4_k_m.gguf)
       ├─► Local Ollama: ExternalProviderMiniBrainAdapter (http://localhost:11434/v1)
       └─► Cloud Providers: OpenRouter, OpenAI, Anthropic, Gemini
       │
       ▼
[Response Validation & Sanitization]
       │ - Latency & token count calculation
       │ - Secret redaction of output
       ▼
[Audit Logging & Memory Persistence]
       │ - SQLite database transaction
       │ - table: mini_brain_llm_messages
       │ - table: mini_brain_llm_events
       │ - table: mini_brain_llm_memories
       ▼
[API JSON Response]
       │
       ▼
[Frontend UI Render]
   - Markdown rendered safely
   - Citations parsed and displayed
   - Tool proposal banners (if action proposed)
```

---

## 2. Component Inventory & File Map

| Layer | Canonical File Path | Primary Class / Function | Purpose / Contract |
|---|---|---|---|
| **Frontend Chat UI** | `apps/admin-dashboard/src/components/chat/ChatPanel.jsx` | `ChatPanel()` | Admin chat interface with model/provider selector and KB toggle |
| **Frontend Widget** | `apps/admin-dashboard/src/components/admin-assistant/AdminAssistantWidget.jsx` | `AdminAssistantWidget()` | Floating persistent admin assistant widget |
| **API Routes** | `backend/api/routes/mini_brain_llm_runtime.py` | `router` (`/admin/mini-brain/llm-runtime`) | Endpoints: `/chat`, `/grounded-chat`, `/widget-health`, `/diagnostics`, `/sessions` |
| **Auth & CSRF** | `backend/api/auth.py` | `require_admin`, `CsrfDependency` | Enforces admin identity and protects against cross-site attacks |
| **Runtime Service** | `backend/services/mini_brain_llm_runtime_service.py` | `MiniBrainLlmRuntimeService` | Core orchestrator for chat, sessions, grounding, and memory |
| **Dashboard Context** | `backend/services/mini_brain_dashboard_context_service.py` | `MiniBrainDashboardContextService` | Aggregates 11 live subsystems state without credentials |
| **RAG Retrieval** | `backend/services/rag_retrieval_service.py` | `RagRetrievalService` | Hybrid BM25/vector search across active knowledge spaces |
| **Prompt Builder** | `core_model/mini_brain/llm_runtime/prompt_builder.py` | `build_prompt`, `build_grounded_messages` | Injects system governance, dashboard context, citations, and memory |
| **Adapters & Router** | `backend/services/mini_brain_llm_adapter.py` | `LlamaCppMiniBrainAdapter`, `ExternalProviderMiniBrainAdapter` | Executes model inference locally (GGUF, Ollama) or via API |
| **Action Bridge** | `core_model/admin_assistant/chat_action_bridge.py` | `match_actionable_intent` | Maps admin intent to proposal; blocks autonomous execution |
| **Governance Engine** | `backend/services/admin_assistant_service.py` | `AdminAssistantService` | Manages 48 governed actions via `propose()`, `review()`, `execute()` |
| **Database Repos** | `backend/database/repositories/mini_brain_llm_runtime.py` | `MiniBrainLlmRuntimeRepository` | SQLite persistence for sessions, messages, events, and memories |

---

## 3. Subsystem Context Mapping (11 Subsystems)

The `MiniBrainDashboardContextService.get_system_context()` queries live tables and services:

1. **System Health**: `MiniBrainHealthService.snapshot()` -> overall health, backend type, loaded model id.
2. **Providers**: `MiniBrainProviderSettingsService.list_settings()` -> enabled vs configured providers (zero secrets).
3. **Models**: `MiniBrainLlmRuntimeService.diagnostics()` -> active model name, local availability, fallback status.
4. **Datasets**: `CorpusRepository.list_dataset_versions()` -> version count, latest version tag.
5. **Training**: `PretrainingRepository.list_runs()` -> total runs, latest run status, `training_gate_locked = True`.
6. **Evaluation**: `ModelEvaluationRepository.list_evaluation_runs()` -> total evals, latest benchmark score.
7. **RAG**: `RagRepository.list_knowledge_spaces()` & settings table -> active space count, default retrieval profile.
8. **Memory**: `MiniBrainLlmRuntimeRepository.count_sessions()` -> active session count, total stored messages.
9. **Governance**: `AdminAssistantService.list_proposals(status='pending')` -> pending count, `authority_mode = 'ADVISORY_ONLY'`.
10. **Recent Events**: `AuditLogRepository.list_events(limit=5)` -> recent administrative actions with timestamps.
11. **Recommendations**: Dynamic rule engine -> hints for missing provider API keys, unassigned RAG profiles, or pending reviews.

---

## 4. Governance & Action Lifecycle (48 Tools)

```
[Admin Asks: "Restart inference service" / "Import dataset"]
                     │
                     ▼
       [Intent Detection: match_actionable_intent()]
                     │
         Is action in blocked substrings?
         (e.g., "train", "pretrain", "promote")
            ├──► YES: Block direct intent, treat as advisory discussion
            └──► NO: Classify action type & risk level
                     │
                     ▼
          [PROPOSE: AdminAssistantService.propose()]
                     │
            - Status: PENDING
            - Payload & stale check fingerprint captured
            - Event logged in SQLite audit table
            - Chat returns proposal card to Admin
                     │
                     ▼
          [REVIEW: AdminAssistantService.review()]
                     │
            - Reviewer != Proposer (Maker != Checker enforced)
            - State re-fingerprinted against target
            - If valid: Status -> APPROVED
                     │
                     ▼
          [EXECUTE: AdminAssistantService.execute()]
                     │
            - Executed only after formal approval
            - Event logged: AuditOutcome.SUCCESS
```

---

## 5. Security & Isolation Boundaries

1. **Production Zero-Mock Invariant**:
   - `MockMiniBrainAdapter` is strictly isolated within unit test fixtures and cannot be instantiated by the production server startup path.
2. **Secret Scrubbing**:
   - `backend.core.json_utils.redact_secrets()` strips sensitive patterns (`sk-...`, Bearer tokens, passwords) before SQL persistence.
3. **Training Isolation**:
   - `SignedTrainingAuthorizationToken` absence renders training, activation, and promotion endpoints hard-locked (fail-closed).
