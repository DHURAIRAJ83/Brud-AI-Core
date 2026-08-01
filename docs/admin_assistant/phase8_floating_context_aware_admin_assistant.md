# Phase 8 — Floating Context-Aware Admin Assistant AI

Status: complete (with disclosed, deliberate scope limitations — see
section 7). Schema version 28 -> 29 (migration
`029_admin_assistant_phase8_floating_context_aware_assistant`). See
[phase8_floating_context_aware_admin_assistant_plan.md](phase8_floating_context_aware_admin_assistant_plan.md)
for the full pre-implementation baseline audit and architecture
rationale.

An incremental enhancement of the existing Admin Assistant
(`admin_approvals` + `AdminAssistantService` + `AdminAssistantPage.jsx`,
Phase 2/22) — never a second chatbot, never a replacement dashboard. A
new floating launcher + chat card is mounted once inside
`DashboardLayout.jsx` and talks to an extended version of the same
governed backend. `AdminAssistantPage.jsx` is untouched and remains the
full-page, form-based "advanced/manual" path; both surfaces operate on
the same `admin_approvals` rows.

## 1. Architecture

**One extended governed-proposal backend, one new floating frontend,
zero new competing systems.**

- **Dashboard/action registries** (`core_model/admin_assistant/`):
  `dashboard_registry.py` is the single source of truth for all 27
  reachable dashboard pages (title/purpose/tabs/safety-note, bilingual
  EN/TA, `implemented` flag honestly `False` for the three real
  placeholder pages — Chat Testing, Audit Logs, Settings). `action_registry.py`
  is the strict allowlist of proposable actions (risk level, payload
  shape, bilingual confirmation copy). `lifecycle.py` derives Phase 8's
  richer conceptual proposal lifecycle (`awaiting_confirmation,
  confirmed, executing, completed, failed, cancelled, expired,
  rejected`) from the existing `status`/`execution_status`/`expires_at`
  columns at read time — nothing new is stored, so it can never drift.
  `intent.py` is a small, bounded, bilingual keyword lexicon that
  deterministically classifies a message into `greeting, help,
  pending_work, navigation, open_ended` — never an LLM call.
- **Proposal lifecycle**: reuses `admin_approvals`/`AdminAssistantService`
  entirely. Four additive columns (`expires_at`, `risk_level`,
  `preview_json`, `stale_check_json`) carry richer per-proposal state.
  `review(decision='approved')` *is* the confirm step, now re-checking
  a fresh fingerprint of the target against the one captured at
  propose time and refusing to proceed if it has changed (Flow N —
  stale-state rejection). A new `cancel()` finally activates the
  long-unused `cancelled` status. A lazy, request-triggered expiry
  check (`AdminApprovalRepository._expire_if_due`) activates `expired`
  — never a background sweep. Three action types are wired to real
  executors spanning three risk tiers: `dataset_record_review` (low,
  pre-existing), `dataset_source_update` (moderate, pre-existing), and
  the new `governance_target_approval_override` (high, requires a
  reason, wired to Phase 6's `GovernanceApprovalService.override()`) —
  proving the full propose -> preview -> confirm-with-stale-check ->
  execute -> verify -> audit pattern end-to-end against a real,
  consequential service. Execution re-reads the target's current state
  afterward and records it in the audit event as `verified_state`
  (post-execution verification).
- **Read-only tools** (`backend/services/admin_assistant_tools.py`):
  14 thin, uniform wrappers spanning all 6 modes (guide/data/
  governance/rag/model/system) around **existing** Phase 2-15 services
  (`AdminAssistantService`, `GovernanceApprovalService`,
  `GovernanceReviewService`, `GovernedBuildService`,
  `LineageGraphService`, `SourceRegistryService`,
  `RagIngestionService`, `ModelEvaluationService`,
  `ModelReleaseService`, `BaseModelReadinessService`,
  `AuditLogRepository`) — never a new data-access layer, never raw
  SQL. Every call is logged as an `admin_assistant_tool_invocations`
  row and every result is passed through `redact_secrets()`.
- **Chat orchestration** (`backend/services/admin_assistant_chat_service.py`):
  every read-only capability (page help, pending-work summary,
  navigation) is answered by the deterministic path first — intent
  classification plus a read-only tool call, no LLM required. Only a
  genuinely `open_ended` message attempts an LLM call. **Correction
  from the plan doc's baseline research**: `model_assignments
  .assignment_key='admin_assistant'` turned out to be dead
  infrastructure (an early Phase 1/2 table tied to the legacy
  `model_registry`/`model_versions` catalog, with no execution path to
  the real Phase 15 inference runtime). The chat service instead
  reuses the `admin_diagnostic` scope of the real, working
  `ModelAssignmentService`/`InferenceRuntimeService` pair — the same
  scope `rag_generation_service.py` already reuses for a different
  admin-facing feature, so this is a repeated pattern, not a new one.
  `core_model.conversation.response_policy.decide_response_status()`
  is reused verbatim for the final status; `generation_failed` maps to
  the literal fallback message "AI response generation is unavailable
  right now. Dashboard guidance and live status remain available." —
  the assistant is never fully disabled.
- **Language**: `core_model.rag.language_routing.classify_language()`
  (Phase 16's existing, bounded Tanglish lexicon + script-ratio
  classifier) is reused verbatim — Tamil, English, Tanglish, and
  mixed are all handled without inventing a second classifier.
- **Conversation storage**: reuses Phase 17's `conversation_sessions`/
  `conversation_turns` via a new `admin_assistant:<admin_public_id>`
  `participant_scope_key` convention, but **only when an active memory
  policy already exists** — the assistant never auto-creates one (that
  stays an explicit admin decision on the Conversation & Memory page),
  so it works identically on a fresh database with zero policies
  configured; it simply doesn't persist turn history across sessions
  until an admin sets one up.
- **New tables** (migration 029, all additive):
  `admin_assistant_context_snapshots` (append-only — one row per
  bounded page-context snapshot sent by the frontend),
  `admin_assistant_tool_invocations` (mutable status/result until
  completion, then delete-blocked), `admin_assistant_feedback`
  (append-only).
- **Frontend**: `apps/admin-dashboard/src/components/admin-assistant/
  AdminAssistantWidget.jsx`, mounted once inside `DashboardLayout.jsx`
  after the existing mobile overlay. Floating launcher (bottom-right,
  never rendered on the login screen since `DashboardLayout` itself
  never renders pre-auth) -> compact card with mode filter chips,
  suggested questions, message history, per-message navigation/
  feedback actions, minimize/restore/close, `Escape`-to-close with
  focus-return to the launcher, and a `Tab` focus wrap while open — the
  first component in this codebase to need real keyboard/focus-trap
  handling, implemented with plain `useEffect`/refs, no new dependency.

## 2. Backend API surface (`/api/admin/assistant/*`)

All under the existing `require_admin` + CSRF-protected router.

| Endpoint | Purpose |
|---|---|
| `GET /overview` | Existing dashboard-summary read (unchanged). |
| `GET /actions` | Existing `action_types` list, additively extended with full per-action registry metadata under a new `actions` key. |
| `GET /pages` | New — the full 27-page dashboard registry. |
| `GET /health` | New — real, read-only `llm_available` diagnostic. |
| `POST /chat` | New — the floating assistant's single conversational entrypoint. |
| `POST /feedback` | New — records helpful/not_helpful/incorrect_guidance/action_failed. |
| `POST/GET /proposals`, `GET /proposals/{id}` | Existing (unchanged). |
| `POST /proposals/{id}/review` | Existing, extended with stale-state rejection. |
| `POST /proposals/{id}/execute` | Existing, extended with post-execution verification. |
| `POST /proposals/{id}/cancel` | New — activates the `cancelled` status. |

## 3. What the assistant will and will not do

- Answers page help, pending-work summaries, and navigation requests
  entirely deterministically from real backend data and the dashboard
  registry — never fabricated status, counts, or capabilities.
- Attempts a real LLM reply only for open-ended questions, using the
  real inference runtime; on any failure it says so plainly rather
  than hallucinating.
- Can propose the one fully-wired high-risk action
  (`governance_target_approval_override`) through the existing
  propose -> Admin Review -> execute pipeline (via `AdminAssistantPage.jsx`
  or the API directly) with a mandatory reason, a generated preview, a
  stale-state re-check at confirmation, and post-execution
  verification — all audited.
- Never mutates anything on its own, never writes raw SQL, never
  starts or resumes training (the `train`/`pretrain` substring block
  is preserved and re-exported from the action registry), never
  silently approves/rejects/deletes/archives/publishes.

## 4. Testing

- `tests/core_model/test_admin_assistant_registries.py` (12),
  `test_admin_assistant_intent.py` (9) — pure policy modules.
- `tests/database/test_phase29_migration.py` (7) — migration.
- `tests/backend/test_admin_assistant_tools.py` (19),
  `test_admin_assistant_lifecycle.py` (19),
  `test_admin_assistant_chat_service.py` (10),
  `test_admin_assistant_context_repository.py` (5),
  `test_admin_assistant_api_phase8.py` (10) — new backend coverage.
- `apps/admin-dashboard/src/components/admin-assistant/
  AdminAssistantWidget.test.jsx` (9) — new frontend coverage;
  `DataOverviewPage.test.jsx` extended for the new metric/action.
- Full regression: 1132 backend/core_model/database tests and 91
  frontend tests, all passing, run in disk-safe batches (this
  environment's `/tmp` tmpfs cannot hold the full ~1100-test suite's
  SQLite/WAL temp files in one uninterrupted pass — confirmed by
  identical `disk is full` failures appearing only late in single
  full-suite runs and disappearing entirely once split; not a code
  regression).
- Manual browser verification (Playwright against the real dev
  server + real backend): launcher absent on the login screen and
  present after login; open/minimize/restore/close; `Escape`
  closes and returns focus to the launcher (a real focus-timing bug
  was found here — see section 6); page-context-correct help replies
  across an implemented page (Model Registry) and an honestly-reported
  placeholder page (Chat Testing); real pending-work summary;
  real navigation action; Tamil and Tanglish replies; the honest
  LLM-unavailable fallback; feedback capture; and a full audit-trail
  check directly against the live database confirming every
  interaction above was recorded.

## 5. Documentation for admins (user guide)

**Where it is**: a rounded "Assistant" button, bottom-right, on every
dashboard page once logged in.

**Opening it**: click the button. It opens as a small card; click the
`_` button to minimize (it keeps your conversation), the restore icon
to bring it back, `×` or `Escape` to close.

**What to ask it**:
- *"How do I use this page?"* — explains whatever page you're
  currently on, including whether it's finished yet.
- *"What's pending?"* / *"What needs my attention?"* — a live summary
  of pending dataset reviews and Admin Assistant proposals awaiting
  your review.
- *"Take me to Builds & Pipelines"* (or any page name) — offers a
  button that jumps you there.
- Anything else — it will try to answer using the real AI model if one
  is configured and running; if not, it says so plainly instead of
  guessing.

**Language**: ask in Tamil, English, or Tanglish (romanized Tamil) —
it detects which one you used and answers in kind.

**Mode chips** (Guide/Data/Governance/RAG/Model/System) are just
filters over the one assistant — they don't switch to a different bot.

**Feedback**: every assistant reply has "Helpful"/"Not helpful"
buttons — this is recorded and never blocks the conversation.

**Proposing an action**: the floating assistant currently helps you
find and understand pending proposals and navigate to them; creating a
new proposal (e.g. approving a record, overriding a governance
decision) still happens on the full **Admin Assistant** page in the
sidebar, which shows the same proposals with a complete form,
preview, and Admin Review workflow.

## 6. Errors found and fixed during this phase

1. **Silent stale-column typo** in the dashboard registry (a leftover
   `ta_key := "ta"` walrus expression from an in-progress edit) —
   caught immediately by the registry's own `ruff check` before any
   test ran.
2. **`AdminApprovalRepository.cancel()`/`update_review()` fetched only
   `status`/`expires_at` columns but then called `_expire_if_due()`,
   which reads `row["public_id"]`** — a real `KeyError` on the very
   first lazy-expiry check. Caught by `test_expired_proposal_cannot_be_approved`
   before manual verification; fixed by fetching the full row.
3. **`GovernedBuildService.list()` does not take `limit`/`offset`**
   (it takes `page`/`page_size`) — the `list_governed_builds` read-only
   tool called it with the wrong keyword arguments, a real `TypeError`
   at call time. Caught by `test_list_governed_builds_empty`.
4. **`GovernanceApprovalService.status()` never raises `NotFoundError`**
   for an entity with no governance activity (it's a total function
   returning `not_requested` for every target use) — the
   `get_governance_entity_status` tool's `except NotFoundError` branch
   was dead code; caught by a failing test assertion and simplified.
5. **`intent.py`'s first implementation used token-set intersection**,
   which silently failed on Tamil agglutinative suffixes (e.g.
   "நிலுவையில்" never matched the lexicon entry "நிலுவை") and could
   never match multi-word phrases like "take me"/"show me" since they
   were stored as single lexicon entries but tokens are
   whitespace-split. Caught by three failing unit tests before any
   integration work; fixed by switching to substring-in-message
   matching plus a short-message heuristic for bare page-name mentions.
6. **A real page-context race condition**, found only by manual
   browser verification (not by any automated test, since the mocked
   frontend tests resolve promises synchronously): the widget's async
   `GET /pages` fetch (triggered on open) had not yet resolved by the
   time a suggested-question button was clicked immediately after
   opening, so the chat request was sent with the wrong (default)
   `page_id` — an admin viewing "Datasets" received a help reply about
   "Overview". Fixed by gating the suggestion buttons and the message
   input on a `pagesLoaded` flag, with a plain "Loading dashboard
   context…" notice in between; a new automated test
   (`does not allow sending before the page registry has loaded`)
   locks this in.
7. **A real focus-management bug**: `Escape` and the Close button
   called `launcherRef.current?.focus()` synchronously inside their
   own handler, but the launcher `<button>` only exists in the DOM
   while the card is *closed* — at the moment `setOpen(false)` runs,
   React has not yet re-rendered, so the ref was still `null` and
   focus silently fell back to `<body>`. Confirmed both in a jsdom
   unit test and against the real running app via Playwright. Fixed
   by moving the focus call into a `useEffect` keyed on `open`, guarded
   by a `hasOpenedRef` so it never steals focus on first mount.

## 7. Limitations / explicitly deferred

- Per the task's own explicit instruction ("do not invent roles unless
  required"), **no tiered admin permission system was built** — every
  authenticated admin has full permission, exactly matching every
  other existing route in this codebase today. The action registry's
  `permission` field documents intent only.
- Only three action types are wired to real executors (spanning
  low/moderate/high risk); the `critical` risk tier is defined but has
  no registered action yet. The registry and execution pipeline are
  generic and extensible — wiring more of the task's example action
  names (`approve_manual_record`, `resolve_duplicate_group`,
  `create_training_handoff`, ...) is mechanical repetition of the same
  pattern and is left as flagged future work rather than attempted at
  lower quality under time pressure.
- The floating widget itself does not contain a free-form action-
  proposal form; it discovers and links to pending proposals and to
  the existing full-page Admin Assistant form, which already has the
  complete propose/preview/confirm/execute UI.
- No autonomous background agents, no automatic project-completion
  loops, no automatic provider-limit resume, no automatic training/
  RAG-activation/model-release/publishing, no external web browsing,
  no legal advice, no AI-generated records without review, no
  automatic translation/Tanglish generation, no semantic-embedding
  duplicate detection, no voice/vision input, no public-facing
  assistant, no unrestricted shell/raw-SQL tools — all per the task's
  explicit out-of-scope list.

**Do not begin any Phase 9 or unrelated enhancement.**
