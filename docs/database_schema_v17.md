# Database Schema v17 — Conversation Memory

Migration `017_phase17_conversation_memory`, schema version 16 → 17,
independent of migration 016 (verified directly:
`test_migration_016_is_unchanged_in_isolation`). Adds 26 tables: 9
mutable, 17 append-only.

## Tables

Mutable (9):

- `conversation_memory_policies` — the purpose/consent/retention rules
  a session operates under. `lifecycle_status` CHECK
  `draft|validated|active|deprecated|archived`.
- `conversation_sessions` — `session_mode` CHECK
  `stateless|session_memory|consented_memory|private_no_persist`,
  `status` CHECK 7 values, `participant_scope_key TEXT NOT NULL` (see
  below), optional `model_assignment_id` / `rag_retrieval_profile_id`.
- `conversation_session_participants` — secondary observer/participant
  tracking only; never the source of truth for memory ownership.
- `conversation_summaries` — the mutable pointer row; its
  `current_version_id` FK points at an append-only
  `conversation_summary_versions` row.
- `memory_consents` — `status` CHECK
  `pending|active|expired|revoked|rejected`, `participant_scope_key`.
- `memory_items` — `category` CHECK exactly 8 values (structurally
  excludes the forbidden/sensitive categories), `status` CHECK 9
  values, `participant_scope_key`.
- `memory_retrieval_profiles` — keyword/vector/recency weights,
  category/purpose allow-lists, score threshold, conflict policy.
- `memory_evaluation_suites` — named/versioned fixture collections.
- `memory_evaluation_runs` — **deviation**: classified mutable, not
  append-only, for the same reason as Phase 16's
  `rag_embedding_runs`/`rag_evaluation_runs` — a genuine two-phase
  create-then-execute API flow (`POST .../runs` creates a `draft` row,
  `POST .../runs/{id}/execute` updates it to a terminal status) is
  incompatible with an append-only trigger. Learned from Phase 16's
  `rag_grounded_requests` bug and applied proactively here.

Append-only (17): `conversation_turns`, `conversation_turn_events`,
`conversation_summary_versions`, `memory_item_versions`,
`memory_item_events`, `memory_embeddings`, `memory_retrieval_runs`,
`memory_retrieval_results`, `chat_context_assemblies`,
`chat_context_items`, `chat_orchestration_runs`,
`chat_grounded_responses`, `chat_response_citations`,
`chat_orchestration_issues`, `memory_evaluation_fixtures`,
`memory_evaluation_metrics`, `conversation_memory_manifests`.

`chat_orchestration_runs` and `chat_grounded_responses` stay genuinely
append-only by construction, not by a later fix: both are inserted
exactly once, at the very end of
`ChatOrchestrationService.send_message()`'s synchronous flow, only
after the final status is already known.

## The `participant_scope_key` decision

`conversation_sessions`, `memory_consents`, and `memory_items` all use
a plain `participant_scope_key TEXT NOT NULL` column (e.g.
`"admin:<admin_public_id>"`) instead of a foreign key to
`conversation_session_participants`. Two reasons: a FK-based design
would be circular (a session's owning-participant row would itself
need to reference the session), and a simple string-match boundary is
the safer, more auditable choice for the single most security-critical
check this phase depends on — "one participant's memory is never
retrieved by another." `conversation_session_participants` remains a
secondary table for observer/additional participants; it is never
consulted for ownership or access filtering.

## Other notable constraints

- `memory_items.category` CHECK lists exactly the 8 allowed
  categories — forbidden/sensitive categories (password, api_key,
  medical_diagnosis, etc.) can never be assigned even by a bug,
  because the database itself rejects the row.
- `memory_embeddings` has no `is_active` column. Eligibility is always
  derived by joining to `memory_items.status='active'` at query time,
  which is what keeps the table genuinely append-only (mirrors Phase
  16's `rag_chunk_embeddings`).
- `conversation_turns.stored_content` is nullable — `NULL` in
  `private_no_persist`/`stateless` modes, populated only in
  `session_memory`/`consented_memory` modes.

## Real dev DB upgrade

```
python -m backend.database.migrations upgrade
schema_version: 17
integrity_check: ok
```

Post-upgrade: `PRAGMA user_version` = 17, `PRAGMA integrity_check` =
`ok`, `PRAGMA foreign_key_check` = 0 rows.
