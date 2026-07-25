# Chat Orchestration Architecture

`ChatOrchestrationService` is the admin-only "Grounded Conversation
Lab" backend — it is not, and must never become, the public chatbot.

## Flow (`send_message()`)

1. Verify the session is `active` and its `model_assignment` is a
   valid, active `admin_diagnostic`-scope assignment (reuses Phase 15
   `InferenceRuntimeService`/`ModelAssignmentService` unchanged, via
   the same `ensure_instance_loaded()` entrypoint Phase 16 added).
2. Persist the user's turn (`ConversationSessionService.create_turn()`),
   respecting the session mode's persistence rule.
3. Decide response language continuity
   (`core_model.conversation.language_continuity.decide_language()`,
   reusing Phase 16's `classify_language` unchanged).
4. Retrieve memory (`MemoryService.retrieve()`) and RAG evidence
   (`RagRetrievalService.retrieve()`) as two separate, self-committing
   calls, each recorded in its own append-only run table — done
   *before* orchestration opens its own transaction, mirroring the
   Phase 15/16 cross-transaction-visibility lesson.
5. Assemble bounded context (`docs/context_orchestration.md`), running
   the injection guard over every item.
6. Generate via the existing `InferenceRuntimeService.run_generation()`
   — never a second runtime.
7. Decide the final response status
   (`core_model.conversation.response_policy.decide_response_status()`)
   and persist `chat_orchestration_runs`/`chat_grounded_responses`/
   `chat_response_citations`/`chat_orchestration_issues` exactly once,
   only now that the final status is known — the design choice that
   keeps these tables genuinely append-only (see
   `docs/database_schema_v17.md`).

## Response statuses

Nine statuses, decided by
`core_model.conversation.response_policy.decide_response_status()`:
`completed, completed_with_warning, insufficient_evidence,
memory_conflict, consent_required, retrieval_failed,
generation_failed, blocked_context, session_closed`. A response must
never claim a memory is verified when it was only inferred
(`memory_disclosure()` only reports memory usage/purpose when memory
was actually used), and missing consent must never be silently
bypassed (`consent_required` is checked before evidence is even
considered sufficient).

## Session close/expiry stops writes

Once a session transitions to `closed`, `expired`, `failed`, or
`archived`, `send_message()`'s own status check
(`session["status"] != "active"`) rejects further messages with HTTP
422 before any turn is created or any retrieval runs — verified
directly in the automated test suite and in manual verification Path
B.

## Public chatbot unchanged

`POST /api/chat` is never touched by this service. It continues to
return `{"model": "placeholder"}` regardless of how many orchestration
runs, sessions, or memory operations have been exercised — confirmed
directly in every relevant automated test and in manual verification.
