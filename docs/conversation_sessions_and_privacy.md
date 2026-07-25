# Conversation Sessions and Privacy Modes

## Session modes

`SESSION_MODES = (stateless, session_memory, consented_memory, private_no_persist)`

`private_no_persist` is the default (`BRUD_MEMORY_DEFAULT_SESSION_MODE`).
Effective capabilities per mode are resolved by
`core_model.conversation.session_policy.resolve_effective_capabilities()`
against the session's `conversation_memory_policies` row:

| mode | short-term context | summary | long-term memory |
|---|---|---|---|
| `private_no_persist` | in-memory only, never written to disk | never | never |
| `stateless` | none carried between turns | never | never |
| `session_memory` | yes, persisted for session lifetime | yes | never |
| `consented_memory` | yes | yes | only with active consent |

## Turn persistence

`conversation_turns.stored_content` is written only in
`session_memory`/`consented_memory` modes. In `private_no_persist` and
`stateless` modes, `ConversationSessionService._purge_private_session_content()`
runs on every turn write inside the same transaction, so
`stored_content` is `NULL` even immediately after the message is
processed — never persisted and later deleted, never persisted at
all. Verified directly in manual verification Path A: after a full
message round-trip in `private_no_persist` mode, `GET
.../turns` returns `stored_content: null` for every row, `GET
.../summaries` returns `[]`, and `GET /memory-items?participant_scope_key=...`
returns `[]`.

## Session lifecycle

`status` CHECK: `draft, active, paused, expired, closed, failed,
archived`. Transitions are enforced by
`ConversationSessionService._transition()`. Once a session is
`closed` or `expired`, `POST .../messages` and any turn-creating
operation is rejected (verified in manual verification Path B: a
message sent after `expire` returns HTTP 422).

## Consent-gated long-term memory

`consented_memory` sessions may retrieve/write long-term memory only
when `capabilities["allow_long_term_memory"]` is true, which itself
requires the policy's `allow_long_term_memory=true` AND (for
`explicit_user_request`/`system_derived` memory) an active
`memory_consents` row scoped to the same `participant_scope_key`. See
`docs/memory_consent.md`.

## Summaries

`conversation_summaries` is the mutable pointer row; each validation
or regeneration creates a new append-only
`conversation_summary_versions` row rather than editing the existing
text. `SUMMARY_STATUSES = (draft, validated, accepted, rejected,
superseded)`. Summaries generated with `deterministic_extract` never
invent facts not present in the turns they summarize — validated by
`core_model.conversation.summary_validation`.
