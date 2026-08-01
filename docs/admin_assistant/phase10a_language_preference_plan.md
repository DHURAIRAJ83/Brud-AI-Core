# Phase 10A Plan — Tamil, English, Tanglish & Auto Response Language Preference

Written before implementation, per this phase's Step 1. See
[phase10a_admin_assistant_language_preference.md](phase10a_admin_assistant_language_preference.md)
for the final, as-built report (status, deviations, test counts,
manual verification results, known limitations).

## 1. Systems reused (confirmed by direct inspection)

- **Admin identity**: `admin_accounts` (schema.py:288) — one row per admin, no
  existing preference-style column. `AdminRepository`
  (`backend/database/repositories/admin.py`) already owns every
  admin-scoped mutation (create, status, password reset, session,
  logout) and has its own lightweight internal `_audit()` helper that
  writes directly to `audit_logs`. **Decision**: extend this repository
  with `get_response_language`/`set_response_language` rather than
  create a competing preferences table or service — the task's own
  instruction ("prefer the existing Admin settings/preferences table if
  one safely supports this field") points here once `app_settings` is
  ruled out (see below).
- **`app_settings`** (schema.py:6): a single global key-value table, not
  scoped per admin. Does not safely support a per-admin field — ruled
  out.
- **No dashboard "Settings" page exists** in `apps/admin-dashboard/src/pages/`
  (confirmed by directory listing) — Step 11 of the task ("if the
  Dashboard already has an Admin settings page...") therefore does not
  apply; no new settings page will be created, matching "do not add an
  unrelated duplicate settings page."
- **Chat orchestration**: `backend/services/admin_assistant_chat_service.py`
  (`AdminAssistantChatService.send_message`) is the **one** place every
  piece of Assistant prose is generated for the floating widget —
  greeting, help, pending-work, navigation, provider lookup, dataset-
  discovery guidance, and the LLM fallback all flow through it. The
  task's long list of response categories ("provider explanations",
  "dataset-discovery reports", "RAG guidance", "training-readiness
  guidance", "model evaluation guidance", etc.) are not separate code
  paths — they are simply different *topics* an admin's message can be
  about, answered by the same deterministic branches or the same LLM
  call. Fixing language resolution and localization once, centrally,
  in this file therefore covers all of them structurally.
- **Full Admin Assistant page**: `apps/admin-dashboard/src/pages/AdminAssistantPage.jsx`
  is **not a chat surface** — it has no message input. It shows
  (a) a "Guidance" tab rendering `AdminAssistantService.dashboard_overview()`'s
  hardcoded-English `guidance` string list, and (b) proposal
  create/review/execute using `ActionDefinition.summary`/
  `confirmation_text` (already bilingual `{en, ta}` dicts from
  `core_model/admin_assistant/action_registry.py`). This phase adds a
  language selector to this page too (Step 10), reusing the same
  preference source, and adds a *computed* localized rendering
  alongside the existing English-only `guidance` list and the existing
  raw bilingual action dicts — **without changing either of those
  existing contracts**, so nothing that already depends on them
  (including existing tests) breaks.
- **Language classifier**: `core_model.rag.language_routing.classify_language()`
  — already returns exactly the categories this phase needs
  (`ta`/`en`/`tgl`/`mixed`/`unknown`), via deterministic script-ratio
  analysis plus a bounded Tanglish lexicon. **Reused unchanged.**
- **Post-response validation**: `core_model.instruction_tuning.language_checks.requested_language_respected()`
  already exists (built for a Phase 11 evaluation concern) and does
  *exactly* what this phase's Step 6 asks for — checks whether a piece
  of generated text's script ratios match an expected language
  category. **Reused unchanged** for LLM output validation, avoiding a
  second competing implementation.
- **Existing action/proposal pipeline**: `AdminAssistantService` (propose
  → preview → confirm-with-stale-check → execute → verify → audit),
  `ACTION_DEFINITIONS`/`ACTION_EXECUTORS`, `AuditLogRepository`. **Reused
  unchanged** — language preference never touches risk level, payload,
  fingerprinting, or execution.
- **API router**: `backend/api/routes/admin_assistant.py`, prefix
  `/api/admin/assistant` (not `/api/admin/admin-assistant` as the
  task's example suggests — the existing, already-shipped prefix is
  reused instead of introducing a second, inconsistent one; the new
  routes are simply `GET/PATCH /api/admin/assistant/preferences`).
- **Frontend API client**: `apps/admin-dashboard/src/services/api.js`'s
  existing `AA = '/api/admin/assistant'` constant and `assistantHealth`/
  `assistantPages`/`sendAssistantChatMessage` naming convention.

## 2. Schema decision

Forward-only additive migration, schema version 31 → 32
(`032_admin_assistant_response_language_preference`):

```sql
ALTER TABLE admin_accounts ADD COLUMN admin_assistant_response_language
    TEXT NOT NULL DEFAULT 'auto'
    CHECK (admin_assistant_response_language IN ('tamil','english','tanglish','auto'));
```

Confirmed compatible: SQLite (3.46, this environment) supports
`ALTER TABLE ADD COLUMN` with an inline `CHECK` constraint that
references only the new column (verified directly against a scratch
in-memory database before writing this plan). This mirrors the
existing `ALTER TABLE dataset_versions ADD COLUMN ... DEFAULT ...`
precedent from an earlier migration (schema.py:554-559) — no new
table, no new repository, one column on the table that already
represents "one row per admin." Every existing row gets `'auto'`
automatically (SQLite backfills the `DEFAULT` for `NOT NULL ADD COLUMN`),
satisfying "nullable legacy rows safely resolve to auto" without the
column ever actually being nullable.

Enum values chosen to match the API contract in the task's own
examples (`tamil`/`english`/`tanglish`/`auto`) rather than the
classifier's internal short codes (`ta`/`en`/`tgl`) — the bridge
between the two vocabularies is one explicit, tested function (mirrors
the `LANGUAGE_CATEGORY_TO_REQUIREMENT_LANGUAGE` precedent from Phase
10's `core_model/data_discovery`), never a merged enum.

## 3. Language-resolution pipeline

New pure module `core_model/admin_assistant/language_preference.py`:

```python
RESPONSE_LANGUAGES = ("tamil", "english", "tanglish", "auto")
RESOLUTION_SOURCES = (
    "request_override", "saved_admin_preference", "session_preference",
    "auto_detection", "default",
)

def resolve_response_language(
    *, request_override, saved_preference, session_preference, message_text,
) -> ResolvedLanguage:
    ...
```

Exact priority order, per the task's own specification:
`request_override -> saved_admin_preference -> session_preference ->
auto_language_detection -> tamil_default`. Implementation notes:

- `request_override` is accepted only from an explicit, separate
  preview-style caller argument (never silently promoted to the saved
  preference) — used by a `POST /preferences/preview` style call and
  by tests, never by ordinary chat traffic.
- `saved_admin_preference` is the `admin_accounts.admin_assistant_response_language`
  column, read via `AdminRepository.get_response_language()`.
- `session_preference` only applies when no saved preference row value
  is present — in practice this never happens once the column has a
  `NOT NULL DEFAULT 'auto'`, so this slot is wired for forward
  compatibility (a future non-persistent per-session override) but is
  inert today; documented as such rather than faked.
- Whenever the *resolved* mode is `auto` (whether from the saved
  preference literally being `auto`, or the default), `classify_language(message_text)`
  runs and its `language_category` maps through
  `LANGUAGE_CATEGORY_TO_RESPONSE_LANGUAGE` (`ta`→tamil, `en`→english,
  `tgl`→tanglish, `mixed`→ the *dominant* script's language via
  `tamil_script_ratio` vs `latin_script_ratio` comparison, falling back
  to tanglish over english when Tanglish lexicon hits are present,
  `unknown`→tamil). This satisfies "a saved explicit language
  preference must always override automatic language detection" (a
  non-auto saved preference never even reaches the classifier) while
  keeping auto mode fully dynamic per message.
- Returns the exact structured result shape from the task:
  `{configured_mode, resolved_language, source, detected_input_language}`.

## 4. Deterministic response localization strategy

New package `core_model/admin_assistant/localization/`:

- `response_language.py` — `resolve_response_language()` (section 3) +
  `to_short_code(resolved_language)` (tamil→ta, english→en,
  tanglish→tgl) for callers that need the classifier's vocabulary.
- `message_catalog.py` — a small, explicit dict of the *finite* set of
  Admin-Assistant-specific fixed strings this phase must localize that
  do **not** already exist as bilingual `{en, ta}` dicts elsewhere
  (greeting variants already exist in `admin_assistant_chat_service.py`
  and are extended in place; this catalog covers the handful of new
  fixed strings this phase itself introduces — e.g. "preference saved",
  "invalid language mode" — plus the finite set of known Admin-
  Assistant proposal-lifecycle messages: "stale proposal — state
  changed since this proposal was created", "this action requires a
  reason", "unknown action_type"). Each entry is `{en, ta}`; Tanglish is
  always *rendered*, never hand-written a third time (see below).
- `tanglish_renderer.py` — `to_tanglish(tamil_text: str) -> str`: a
  **deterministic, rule-based Tamil-Unicode → Latin phonetic
  transliterator**, applied only to Tamil-script runs of the text
  (found via the same `TAMIL_PATTERN` regex `core_model.instruction_tuning.language_checks`
  already imports from `core_model.training.dataset_profile`); every
  non-Tamil-script run (English words, `{format_placeholders}`, digits,
  punctuation, identifiers) passes through completely untouched.

  **Why this is not the "mechanical, bad" transliteration the task
  warns against**: inspecting this codebase's actual bilingual strings
  (Phase 8/9/10's `action_registry.py`, `dashboard_registry.py`,
  `admin_assistant_chat_service.py`) shows every "ta" string already
  keeps technical vocabulary in English/Latin script inline — e.g.
  `"இது provider {target_public_id}-க்கு ஒரு {credential_type}
  credential reference-ஐ கட்டமைக்கும்"` already writes "provider",
  "credential reference" in Latin script. Because the renderer only
  touches Tamil-script runs, technical terms that are *already* Latin
  script in the source are automatically preserved verbatim — exactly
  the task's "preserve technical vocabulary in English" rule — without
  a term-exclusion list to maintain. This also means every existing
  `{en, ta}` bilingual dict across the whole codebase (dashboard pages,
  actions, help registry, chat replies) gets a working Tanglish
  rendering for free, with zero additional hand-written strings and
  zero risk of drifting from the Tamil original.

  Documented, honest limitation: this produces a *formal phonetic*
  transliteration (e.g. "irukkum", "vேṇṭum"-family spellings normalized
  to plain ASCII like "venum") rather than hand-tuned colloquial
  spelling ("ku" vs "kku", "illa" vs "illai"). It is deterministic,
  readable, and testable, but will not always match the exact spelling
  a native speaker would type. Called out explicitly in "known
  limitations" rather than silently passed off as equivalent to
  hand-written Tanglish.

- A generic `localize(bilingual: dict[str, str], resolved_language: str) -> str`
  helper: returns `bilingual["en"]` for english, `bilingual["ta"]` for
  tamil (falling back to "en" if "ta" missing), `to_tanglish(bilingual["ta"])`
  for tanglish (falling back to `bilingual["en"]` if no "ta" key
  exists at all, since Tanglish is derived from Tamil, not English).

Structured/machine fields (enum values, IDs, JSON keys) are never
passed through `localize()` — only the existing bilingual
human-readable `title`/`purpose`/`safety_note`/`summary`/
`confirmation_text`/message strings are.

## 5. LLM prompt strategy

`_generate_llm_reply()` gains a `resolved_language: str` parameter.
`SYSTEM_INSTRUCTIONS` is extended with one of three concrete,
resolved-language instruction blocks (never "respond in the admin's
language" left ambiguous, and never `auto` passed to the model — auto
is always resolved to a concrete language *before* this call, per
section 3). After generation, `requested_language_respected()` runs
against the short-code form of the resolved language; on a `warning`
verdict the service retries once with a strengthened instruction
("Your previous reply was not in <language>. Reply only in <language>
this time."), and on a second failure falls back to the existing
deterministic `GENERATION_UNAVAILABLE_MESSAGE` (localized), consistent
with "the assistant is never fully disabled."

## 6. Frontend integration

- Floating widget (`AdminAssistantWidget.jsx`): a new `<select>`
  language row next to the existing mode-filter row, loaded from
  `GET /api/admin/assistant/preferences` on open, saved via
  `PATCH .../preferences` on change (optimistic local state + rollback
  on failure), sent as the resolved context for subsequent
  `sendAssistantChatMessage` calls (the backend still authoritatively
  resolves language server-side from the saved preference — the
  frontend never invents a client-only override).
- Full page (`AdminAssistantPage.jsx`): the same selector, same API,
  in a new small header row above the existing tabs — changing it here
  updates the same saved preference the widget reads, so the two
  views never compete (single source of truth: the database column,
  no client-side cache treated as authoritative, per the task's
  explicit "no localStorage-only storage" rule... actually restated:
  "frontend caching may be used only as a non-authoritative
  convenience" — a `sessionStorage`/component-state cache is fine
  purely to avoid a UI flash, always re-verified against the API
  response).
- No separate Settings page (see section 1).

## 7. Compatibility risks

- `dashboard_overview()`'s `guidance` list and `ActionDefinition.summary`/
  `confirmation_text` dicts are read by existing tests expecting
  English/bilingual content — **not modified**; new localized-rendering
  functions are added alongside them instead (section 4).
- `admin_assistant_chat_service.py`'s existing `_reply_*` methods
  currently accept a raw `language: str` in `{"ta","en"}` (defaulting
  unknown/"tgl"/"mixed" silently to "en"). Extending them to accept
  `{"ta","en","tgl"}` is additive (new branch), not a signature-breaking
  change — existing callers passing "ta"/"en" keep working identically.
- `admin_assistant_response_language` is a brand-new column with a
  `NOT NULL DEFAULT` — every existing row (including seeded/verifier
  admins from Phases 3-10) resolves safely to `'auto'` on migration.

## 8. Security considerations

- Preference read/write requires the existing `require_admin`/`CsrfDependency`
  — no new auth surface.
- No new data exposed: the preferences endpoint returns only
  `{response_language, updated_at}`, never other `admin_accounts`
  columns (password_hash, session data).
- Audit entries record only the enum transition
  (`old_response_language`/`new_response_language`/`admin_id`/
  `changed_at`/`change_source`) — never full chat message content,
  per the task's explicit instruction.
- The Tanglish renderer only ever transforms text this codebase itself
  already produced (existing "ta" bilingual strings, or LLM output
  already constrained by the existing prompt-injection defenses) — it
  is not fed arbitrary untrusted external text.

## 9. Testing plan

- Migration/persistence: schema upgrade, allowed-values CHECK,
  invalid-enum rejection, existing-admin default, per-admin isolation,
  persistence across a fresh `AdminRepository` instance (simulating
  logout/login).
- Resolution: all 5 priority levels, auto-detection for ta/en/tgl/mixed/unknown
  inputs, explicit override never silently persisted.
- Classifier bridge: `LANGUAGE_CATEGORY_TO_RESPONSE_LANGUAGE` mapping,
  mixed-input dominant-language selection, unknown→tamil fallback.
- Tanglish renderer: known Tamil words/sentences → readable Latin
  output; embedded English/placeholders/IDs pass through byte-for-byte
  unchanged; round-trip idempotence on already-Latin text.
- Deterministic chat replies: one test per mode × one existing
  deterministic branch (greeting/help/pending_work/navigation/provider
  lookup/dataset-discovery guidance), asserting the resolved language
  is honored regardless of input-message language, and that a
  non-auto saved preference overrides the input language.
- Preservation: a dedicated test asserts a fixed set of
  machine-readable tokens (provider codes, dataset IDs, `PHASE_10_COMPLETE_WITH_LIMITATIONS`-style
  constants, paths, enums) survive `to_tanglish()` unchanged.
- LLM path: resolved language injected into the prompt; auto resolved
  before the call; a deliberately-wrong-language mock response
  triggers the retry-then-fallback path; zero-assignment deterministic
  path still works.
- API: auth required, CSRF required for PATCH, valid/invalid enum,
  audit row written, per-admin isolation (two admins never see each
  other's preference).
- Frontend: selector present in both widget and full page, loads
  saved value, save failure surfaces an error without losing the
  previous selection, keyboard/ARIA reachable, absent on the login
  screen, 390px layout intact.

## 10. Explicit Phase 11 deferral

No licence verification, no dataset download/import/quarantine/RAG
sandbox, no training approval/execution, no model release, no new
translation provider or LLM provider, no new identity/settings/
conversation-store system, no voice or public-chatbot language
settings, no full-dashboard UI translation, no retroactive translation
of historical chat turns. This phase only adds a persistent Admin
response-language preference and applies it to the existing Admin
Assistant's own output.

**Do not proceed to Phase 11 in this session.**
