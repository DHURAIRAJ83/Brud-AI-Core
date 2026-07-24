# Admin Chat Lab (Phase 15)

Bounded, admin-only, multi-turn testing sessions — never a public-chat
substitute, never exposed to non-admin users.

## Session lifecycle

`POST /assignments/{public_id}/sessions` requires scope
`admin_chat_lab` and status `active`; creates an `inference_sessions`
row with a configurable `max_turns` (default 10, 1–100) and loads the
assignment's release onto the resolved runtime instance if not already
loaded. Session statuses: `active`, `expired`, `closed`, `failed`.
`POST /sessions/{public_id}/messages` increments `turn_count` per call
and rejects (setting `status=expired`) once `turn_count >= max_turns`.
`POST /sessions/{public_id}/close` ends the session explicitly.

## Context handling

Each message is built via `core_model.inference_runtime.context_builder
.build_context()` with `truncation_policy="truncate_oldest_history"` —
the latest user message is always preserved; older turns are dropped
first if the bounded context would otherwise overflow. No assistant
response is ever injected into the context before generation.

## No background persistence beyond the configured scope

`inference_requests`/`inference_results` rows are recorded per message
(checksums only, per the project-wide no-raw-content discipline) tagged
with the session's internal ID — but no full transcript is stored, and
no user-account association exists (admin chat lab has no concept of an
external user at all).

## Safe fallback on runtime failure

If the resolved runtime instance's load or a mid-session generation
call fails, the session's message call fails closed — no automatic
retry, no silent substitution of an unrelated model, no bypass of the
release-eligibility checks that were already satisfied when the
assignment was approved.
