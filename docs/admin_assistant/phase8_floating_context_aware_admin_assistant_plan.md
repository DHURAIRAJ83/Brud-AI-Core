# Phase 8 Plan — Floating Context-Aware Admin Assistant AI

Written before implementation, per this phase's Step 1. Synthesizes
three parallel baseline-research passes: (a) the existing Admin
Assistant system, (b) existing provider routing/conversation memory/
chat, (c) existing frontend shell/modal/accessibility conventions.

## 1. Existing systems (confirmed by direct inspection)

### 1.1 The existing Admin Assistant is a deterministic, form-based
governed-proposal system — not a chatbot

Migration 022 (`022_phase22_admin_assistant_execution_tracking`) adds
**no new tables** — only 5 additive columns (`summary`,
`execution_status`, `executed_at`, `execution_result_json`,
`executor_public_id`) onto the pre-existing Phase 2 `admin_approvals`
table (`id, public_id, action_type, target_type, target_public_id,
request_payload_json, status, requested_by, reviewed_by,
review_comment, created_at, reviewed_at`).

`AdminApprovalStatus`: `pending, approved, rejected, cancelled,
expired` (**`cancelled`/`expired` are modeled in the CHECK constraint
but no code path has ever set them** — a real, pre-existing gap this
phase closes). `ExecutionStatus`: `not_applicable, pending, succeeded,
failed`.

`backend/services/admin_assistant_service.py::AdminAssistantService`:
`dashboard_overview()` (one hardcoded multi-table count query),
`propose()`/`list_proposals()`/`get_proposal()`/`review()`/`execute()`.
The entire action registry today is a 2-entry Python dict,
`ACTION_EXECUTORS = {"dataset_record_review": ..., "dataset_source_update":
...}` — no risk level, no permission field, no preview/confirmation-text
field. `propose()`/`execute()` both defensively reject any action_type
containing `"train"`/`"pretrain"` substrings even if one were
mistakenly registered. Exactly-once execution is enforced at the
repository layer (`update_execution()` requires `execution_status`
was `'pending'`).

`backend/api/routes/admin_assistant.py`: 6 endpoints (`GET .../overview`,
`GET .../actions`, `POST/GET .../proposals`, `GET .../proposals/{id}`,
`POST .../proposals/{id}/review`, `POST .../proposals/{id}/execute`) —
**no `/cancel` endpoint exists today.**

`apps/admin-dashboard/src/pages/AdminAssistantPage.jsx` (203 lines) is
a **full page**, not floating — a top-level nav item (outside the Data
group, between "Chat Testing" and "Audit Logs"), 3 tabs (`Guidance`,
`Propose an Action`, `Proposals & Admin Review`), entirely form-based
(free-text `target_type`/`target_public_id`, a raw JSON textarea for
`request_payload`, raw `<pre>` dumps for review). No chat UI, no
page-context awareness, no language handling, no navigation buttons.

**This existing page and its backend are never removed, renamed, or
disabled by this phase.** Phase 8 adds a *new*, additive, richer
interaction surface (a floating chat widget) that talks to an
*extended* version of this same backend system — the same
`admin_approvals` table, the same propose→review→execute lifecycle,
richer metadata layered on top. `AdminAssistantPage.jsx` remains the
"advanced/manual" form-based path; the floating widget is the new
conversational path; both operate on the same underlying proposals.

### 1.2 Provider routing is internal-model-assignment, not multi-vendor

There is no external multi-vendor LLM router in this codebase — Brud
AI serves its own trained model. "Provider routing" means
`ModelAssignmentService` assigning a model release + inference runtime
profile to a closed-enum **scope**
(`inference_assignment_scopes.scope_key IN ('admin_diagnostic',
'admin_chat_lab', 'internal_canary', 'public_chat')`) or, for
generation-role assignment, `model_assignments.assignment_key IN
(public_chat, admin_chat_test, admin_assistant, tanglish_normalizer,
embedding, fallback)`.

**Critically, `'admin_assistant'` is already a valid
`assignment_key` value in the existing schema's CHECK constraint** —
the schema already anticipated an LLM-backed admin assistant role;
no service has ever read/written that assignment row until now. Phase
8 consumes it via the exact same pattern `chat_orchestration_service.py`
already uses (`ModelAssignmentService` lookup by `assignment_key` ->
`InferenceRuntimeService.run_generation()`), never inventing a new
router.

`core_model/conversation/response_policy.py::decide_response_status()`
is the exact deterministic-fallback template to reuse: a pure function
returning one of 9 statuses (`completed, completed_with_warning,
insufficient_evidence, memory_conflict, consent_required,
retrieval_failed, generation_failed, blocked_context, session_closed`)
from boolean flags in strict priority order. Phase 8's "AI response
generation is unavailable" message is exactly the existing
`generation_failed` status, reused verbatim rather than reinvented.

### 1.3 Conversation memory (Phase 17) is reusable as-is

`conversation_sessions` (`participant_scope_key` TEXT — already a
free-text convention like `"admin:<admin_public_id>"`;
`session_mode`, `language_preference`, `status`),
`conversation_turns` (`role`, `stored_content`, `redaction_status`,
`UNIQUE(session_id, sequence_number)`), `memory_items` (`category`,
`creation_source`, `confidence_type`). Phase 8 reuses these tables
directly for its own conversation storage via a new
`participant_scope_key` convention
(`"admin_assistant:<admin_public_id>"`) — never a second conversation-
storage system. Proposal execution always re-reads current entity
state rather than trusting memory (Step 28's explicit requirement).

### 1.4 No tiered permission system exists

No `Role`/`Permission` class anywhere — every existing admin route
(including every one built in Phases 2-7) enforces a single flat
"admin" concept via `require_admin`. Per Step 25's own explicit
instruction ("Only if equivalent roles already exist... Do not invent
roles unless required and implemented through a new migration with
clear compatibility"), **this phase does not invent a role hierarchy**.
Every authenticated admin has full permission, exactly matching every
existing route's real behavior today. The action registry's
`permission` field documents *intent* (useful once real tiering ships
in a future phase) but enforcement today is "any authenticated admin,
checked server-side" — never only in the frontend, satisfying rule 13
without fabricating roles that don't exist.

### 1.5 Frontend mount point, redaction, accessibility

`DashboardLayout.jsx` only ever renders once `auth.admin` is truthy
(`App.jsx` returns `<LoginPage>` early otherwise) — a widget mounted as
a new sibling inside `DashboardLayout`'s returned tree automatically
never appears on the login screen, no extra guard needed, and receives
the current `admin` prop for free (no React Context exists anywhere in
this app; `admin` flows down as a plain prop from `App.jsx`).

No modal/popover/floating-panel component exists anywhere to reuse —
built fresh, matching existing design tokens (`#65d5a7` accent,
`#10192b`/`#18243a` navy, white card/`14px` radius/`box-shadow`,
breakpoints `800px`/`700px`) and exceeding the sidebar's `z-index: 3`.
`backend/core/json_utils.py::redact_secrets()` is the existing,
already-reused-elsewhere redaction primitive for tool output
sanitization. Accessibility conventions to match: `aria-label` on
icon-only buttons, `aria-expanded`/`aria-controls` on collapsible
groups, `aria-current="page"` on active nav — no existing keyboard/
focus-trap code exists anywhere, so the floating card is the first
component in this codebase to need real `Escape`-to-close and
focus-return handling; implemented simply, not with a new dependency.

## 2. Architecture decision

**One extended governed-proposal backend, one new floating frontend,
zero new competing systems.**

- **Proposal lifecycle**: reuses `admin_approvals` and
  `AdminAssistantService` entirely — no new proposal/execution table.
  Richer preview/expiry/stale-detection data is added via a small set
  of new, additive columns (`expires_at`, `risk_level`, `preview_json`,
  `stale_check_json`) rather than a separate `admin_assistant_action_previews`
  table (avoiding rule 4's "do not duplicate existing proposal... tables").
  Phase 8's richer conceptual lifecycle (`draft, preview_ready,
  awaiting_confirmation, confirmed, executing, completed, failed,
  cancelled, expired, rejected`) is a **derived, presentation-layer
  state** computed from the existing `status` + `execution_status` +
  `expires_at` columns — never a new stored enum, never touching the
  existing CHECK constraint (which would require an invasive table
  rebuild of a foundational Phase 2 table). The existing `review()`
  method *is* the "confirm" step (`decision='approved'`), extended with
  stale-state/blocker re-checks before it's allowed to proceed; a new
  `cancel()` method finally activates the long-unused `'cancelled'`
  status; an expiry check activates `'expired'`.
- **Conversation storage**: reuses Phase 17's `conversation_sessions`/
  `conversation_turns`/`memory_items` via a new `participant_scope_key`
  convention — no new conversation table.
- **Provider routing**: reuses `ModelAssignmentService` with the
  already-schema-anticipated `assignment_key='admin_assistant'`,
  calling `InferenceRuntimeService.run_generation()` exactly as
  `ChatOrchestrationService` already does; falls back to
  `decide_response_status()`'s `generation_failed` status, verbatim,
  when unavailable.
- **New, genuinely justified tables** (migration 029): dashboard
  *context* has no existing equivalent (`admin_assistant_context_snapshots`),
  tool-call logging has no existing equivalent
  (`admin_assistant_tool_invocations`), and structured feedback has no
  existing equivalent (`admin_assistant_feedback`).
- **Dashboard/action registries**: new, pure Python structured modules
  (mirroring every prior phase's `core_model/*` pure-policy convention)
  — the LLM is never the source of truth for what a page does or what
  action IDs exist; it only narrates from registry data the server
  already validated.
- **Read-only tools**: thin, uniform wrappers around **existing**
  Phase 2-7 services (`GovernanceApprovalService`, `GovernedBuildService`,
  `LineageGraphService`, `SourceRegistryService`, document/RAG/
  pretraining-readiness/model-evaluation/model-release services) —
  never a new data-access layer, never raw SQL.
- **Frontend**: a new `components/admin-assistant/` tree mounted once
  in `DashboardLayout.jsx`, reusing the existing `admin` prop, existing
  `api.js` conventions, and existing design tokens. `AdminAssistantPage.jsx`
  is untouched.

## 3. Proposed schema (migration 029)

All additive; no existing table's columns, CHECK constraints, or
triggers change except the 4 new columns added to `admin_approvals`
(itself additive — existing rows get sensible defaults, existing
readers of that table are unaffected since they only ever read columns
they already know about).

| Change | Purpose |
|---|---|
| `admin_approvals.expires_at` (nullable TEXT) | When a proposal preview goes stale and must be re-generated. |
| `admin_approvals.risk_level` (TEXT, default `'moderate'`) | `low/moderate/high/critical`, from the action registry at proposal time. |
| `admin_approvals.preview_json` (TEXT, default `'{}'`) | Current-state summary, proposed-state summary, warnings, blocking conditions, required confirmation text — generated once at propose time, re-validated (not re-generated) at confirm time. |
| `admin_approvals.stale_check_json` (TEXT, default `'{}'`) | A fingerprint of the target entity's revision/status captured at proposal time, re-compared at confirm time to detect concurrent mutation (Step 10, Flow N). |
| `admin_assistant_context_snapshots` | One row per bounded page-context snapshot the frontend sent, sanitized, linked to a conversation. |
| `admin_assistant_tool_invocations` | One row per read-only tool call: tool name, mode, sanitized input/result summaries, status, timing. |
| `admin_assistant_feedback` | Helpful/not-helpful/incorrect/action-failed, linked to conversation/message/page/action/registry version. |

## 4. Compatibility risks

- **Risk**: adding columns to `admin_approvals` could break the
  existing `AdminAssistantService`/`AdminAssistantPage.jsx` if they
  ever `SELECT *` and assume a fixed column count.
  **Mitigation**: both already read named columns via `public_row()`-
  style dict access, never positional; the existing test suite
  (`test_admin_assistant_api.py`) is re-run unchanged after the
  migration to confirm zero regression.
- **Risk**: reusing `admin_approvals.status`'s existing 5-value CHECK
  for a richer conceptual lifecycle could confuse a reviewer expecting
  a real `preview_ready`/`awaiting_confirmation` stored value.
  **Mitigation**: the derived-state mapping is documented explicitly
  (section 2 above) and exposed via a pure, tested mapping function
  rather than left implicit.
- **Risk**: `assignment_key='admin_assistant'` has never been read by
  any service — a first real consumer could surface a latent gap in
  `ModelAssignmentService`/`InferenceRuntimeService` (e.g. no release
  ever assigned to that key in a fresh database).
  **Mitigation**: the chat orchestration path treats "no assignment
  configured for `admin_assistant`" as an ordinary `generation_failed`-
  equivalent condition, falling back to the deterministic guide —
  never a 500 error, matching rule 17 ("deterministic guide/status
  features must continue to work").

## 5. Frontend architecture

`apps/admin-dashboard/src/components/admin-assistant/` — a floating
launcher + card, mounted once as a sibling inside `DashboardLayout.jsx`'s
returned tree (after the existing mobile-overlay button), receiving
`admin` as a prop exactly like `Topbar`/`Sidebar` already do. No new
component is created solely to match the task's suggested file list
where the repository's own conventions call for fewer, denser files
(matching `GovernancePage.jsx`/`BuildsPipelinesPage.jsx`'s established
"one file, several function components" style) — used where it doesn't
reduce clarity, but message/proposal/confirmation rendering is split
into focused components since that surface is genuinely complex and
reused across every mode.

## 6. Fallback behavior

Every read-only capability (page help, pending-work summary, error
explanation, navigation) is answered by the **deterministic path
first** — pure functions over registry + real tool data, no LLM call
required at all for these. Only free-form/open-ended questions attempt
an LLM call via `assignment_key='admin_assistant'`; on any failure
(no assignment configured, timeout, provider error) the response falls
back to the same deterministic guide plus the literal message: "AI
response generation is unavailable. Dashboard guidance and live status
remain available." The assistant is never fully disabled.

## 7. Explicitly deferred (this phase)

Per the task's own out-of-scope list: autonomous background agents,
automatic project-completion loops, automatic provider-limit
resume, automatic training/RAG-activation/model-release/publishing,
external web browsing, legal advice, AI-generated records without
review, automatic translation/Tanglish generation, semantic embedding
duplicate detection, voice/vision input, a public-facing assistant,
unrestricted shell/raw-SQL tools. Also deferred, as an explicit,
proportionate scope decision given this phase's already-large surface:
wiring every single example action name listed in the task (e.g. every
one of `approve_manual_record`, `resolve_duplicate_group`,
`create_training_handoff`, ...) — the action registry and execution
pipeline are built generically and fully extensible, and a
representative, real, end-to-end high-risk action
(`approve_target_use`, via the existing Phase 6
`GovernanceApprovalService`) is wired completely end-to-end (propose →
preview → confirm with stale-check → execute → verify → audit) to
prove the pattern; adding the remaining example actions is
mechanical repetition of that same wiring and is flagged as future
work rather than silently attempted at lower quality under time
pressure.
