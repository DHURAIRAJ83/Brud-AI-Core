# Phase 17 Conversation Memory Architecture Overview

Conversation memory, user sessions, privacy controls, and grounded
chat orchestration, admin-only, built entirely on top of existing
Phase 1-16 infrastructure. No new inference runtime, no new model
loader, no new vector-index implementation, no public-facing
activation.

Core principle: memory must not mean "store everything forever."
Memory means purpose-bound, consent-aware, inspectable, correctable,
deletable, and bounded.

## Pipeline

```
session (mode + policy) -> turn (role-validated, optionally persisted)
  -> summary (deterministic extract, validated before use)
  -> memory proposal (category/purpose/safety checked)
       -> consent gate / confirmation gate -> active | awaiting_confirmation | proposed
  -> memory retrieval (keyword + vector, participant-scoped, active-only)
  -> chat orchestration: memory retrieval + RAG retrieval (separate, self-committing calls)
       -> injection guard over every context item
       -> context budget (mandatory items first, optional items greedy-packed)
       -> existing InferenceRuntimeService.run_generation()
       -> response policy -> answer status -> citations (memory + RAG, separately)
```

## Package layout

- `core_model/conversation/` — 18 pure-function modules, no I/O, no
  `Settings` dependency, unit-tested in
  `tests/core_model/test_phase17_conversation_memory.py`.
- `backend/models/conversation_memory.py` — Pydantic request/response
  schemas.
- `backend/database/repositories/conversation_memory.py` — the
  26-table repository, `public_row()`/`INTERNAL`-stripping pattern
  identical to every prior phase's repository.
- `backend/services/conversation_session_service.py` — policies,
  sessions, turns, summaries.
- `backend/services/memory_service.py` — consent, memory items,
  versioning, retrieval profiles, retrieval (keyword + embedding).
- `backend/services/chat_orchestration_service.py` — combines
  conversation state, memory, and RAG evidence into one bounded
  context and reuses the Phase 15 runtime for generation.
- `backend/services/memory_evaluation_service.py` — evaluation
  suites/fixtures/runs/metrics and the reproducibility manifest.
- `backend/api/routes/conversation_memory.py` — routes under
  `/api/admin/conversation-memory`, every mutation behind
  `require_admin` + CSRF.
- `backend/conversation_memory_cli.py` — 15 operator subcommands.
- `apps/admin-dashboard/src/pages/ConversationMemoryPage.jsx` —
  14-tab admin UI.

## Reuse, never duplication

- Retrieval scoring reuses Phase 16's
  `core_model.rag.embedding.compute_embedding`/`pack_vector`/
  `unpack_vector` and `core_model.rag.vector_index.score_vectors`
  unchanged. A dedicated `memory_local_embedding` v1 row
  (`local_custom_embedding`, 64 dimensions) is find-or-created
  directly in Phase 16's own `rag_embedding_models` table the first
  time an embedding is needed — never a second embedding model
  registry.
- Grounded chat reuses Phase 16's `RagRetrievalService.retrieve()`
  unchanged for RAG evidence, and Phase 15's
  `InferenceRuntimeService`/`ModelAssignmentService` unchanged for
  generation.
- `core_model/conversation/evaluation.py`, `manifest.py`,
  `language_continuity.py`, and `injection_guard.py` all re-export or
  directly reuse the corresponding Phase 16 `core_model/rag/` module,
  adding only conversation-memory-specific categories where genuinely
  new (e.g. `change_memory_policy`, `delete_logs`,
  `cross_participant_retrieval` injection patterns).

## What Phase 17 deliberately does not do

- No automatic public chatbot activation. `POST /api/chat` is
  unchanged and still returns `{"model": "placeholder"}` after every
  conversation-memory operation exercised in this phase's tests and
  manual verification.
- No unbounded user profiling, no hidden behavioral tracking, no
  automatic long-term storage of every message, no advertising
  profiles, no cross-user memory, no external vector databases, no web
  search, no external model providers, no tool calling, no autonomous
  agents, no RLHF/DPO/reward modeling, no quantization/GGUF export, no
  production deployment.
- No second inference runtime, model loader, or vector-index
  implementation — confirmed directly in the service code and in
  `docs/conversation_memory_retrieval.md`.

See `docs/database_schema_v17.md` for the schema, and the
per-subsystem docs for detail.

## Phase 18 addendum

Phase 18's feedback pipeline can reference a conversation turn or a
memory-orchestration response as a feedback subject
(`conversation_response`/`memory_orchestration_response` subject
types), but only ever via a checksum-and-public-ID snapshot taken at
feedback-submission time — it never reads or duplicates raw
conversation/memory content, and it never writes back into
conversation-memory tables. See `docs/feedback_architecture.md`.
