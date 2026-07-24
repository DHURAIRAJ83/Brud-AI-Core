# Admin RAG Chat Lab

Reuses Phase 15's `inference_sessions` table unchanged — no new session
schema. `scope` is stored as the free-text label `"admin_rag_lab"` (the
column has no CHECK constraint), and `rag_grounded_requests.session_id`
is a hard foreign key to `inference_sessions(id)`.

## Fresh retrieval every turn

`RagGenerationService.post_message()` calls `retrieve()` and then
`_generate_and_persist()` from scratch for every turn — there is no
carried-forward evidence or session-level memory of prior retrieval
results. Each turn is a fully independent grounded-answer call that
happens to share a session ID for grouping and turn-count enforcement
(`max_turns`, default 10; a session that reaches its limit is marked
`expired` and rejects further messages).

## No automatic public assignment

Creating a chat-lab session requires an already-active
`admin_diagnostic`-scope assignment (the same reused scope RAG
generation always uses — see `docs/database_schema_v16.md`). There is no
code path in this phase that promotes a chat-lab session, its
assignment, or any RAG configuration to the public chatbot scope.
`POST /api/chat` remains the unchanged Phase 1 placeholder throughout,
verified directly after a full session lifecycle in both the automated
test suite and manual verification.

## Verified in manual verification

A 3-turn session (Pongal / Deepavali / Tamil New Year questions) was
opened, messaged three times, and closed successfully
(`closed_status == "closed"`); each turn independently returned
`insufficient_evidence` under the tiny CPU test profile's context
budget (see `docs/rag_context_budget_and_prompt.md`) — the safe
no-answer path, not a crash or a fabricated answer.
