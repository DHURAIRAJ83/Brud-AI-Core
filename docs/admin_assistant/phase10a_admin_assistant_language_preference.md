# Phase 10A — Tamil, English, Tanglish & Auto Response Language Preference

Status: complete. Schema version 31 -> 32 (migration
`032_admin_assistant_response_language_preference`). See
[phase10a_language_preference_plan.md](phase10a_language_preference_plan.md)
for the full pre-implementation baseline audit and architecture
rationale.

A persistent, per-admin Admin Assistant response-language preference
(`tamil`/`english`/`tanglish`/`auto`) applied across every existing
deterministic reply path, the LLM-backed path, and both UI surfaces
(the floating widget and the full Admin Assistant page) -- without
creating a second Assistant, a translation provider, a new identity/
settings/conversation-store system, or a competing language
classifier.

## 1. Architecture

- **Persistence**: one additive column,
  `admin_accounts.admin_assistant_response_language` (`NOT NULL DEFAULT
  'auto'`, `CHECK` constrained to the 4 allowed values), added via
  `ALTER TABLE` in migration 032. No new table -- `admin_accounts`
  already is "one row per admin"; `app_settings` (the only existing
  settings table) is a global key-value store with no per-admin
  scoping and was ruled out. `AdminRepository.get_response_language`/
  `set_response_language` (new methods on the existing repository)
  read/write it, and `set_response_language` writes its own audit row
  via the file's existing internal `_audit()` helper.
- **Resolution** (`core_model/admin_assistant/language_preference.py`,
  pure): `resolve_response_language()` implements the exact priority
  chain `request_override -> saved_admin_preference ->
  session_preference -> auto_language_detection -> tamil_default`,
  returning `{configured_mode, resolved_language, source,
  detected_input_language}`. Reuses
  `core_model.rag.language_routing.classify_language()` completely
  unchanged; the only new logic is the bridge from its short output
  categories (`ta`/`en`/`tgl`/`mixed`/`unknown`) to this phase's
  full-word vocabulary, including a `dominant_language_for_mixed()`
  script-ratio comparison and the "unknown input -> Tamil" fallback.
  `AdminAssistantLanguageService`
  (`backend/services/admin_assistant_language_service.py`) is the one
  impure wrapper every caller goes through -- `get_preference`,
  `set_preference`, `resolve(admin_id, message_text, request_override)`,
  and a non-persistent `preview()`.
- **Localization** (`core_model/admin_assistant/localization/`):
  - `tanglish_renderer.to_tanglish()` -- a deterministic, rule-based
    Tamil-Unicode -> Latin-script phonetic transliterator, including a
    real Tamil sandhi rule (intervocalic/post-nasal voicing of stop
    consonants, e.g. க/ச/ட/த/ப -> g/j/d/dh/b, staying unvoiced when
    geminated). Only Tamil-*script* runs are transformed; every other
    run (English words, `{format_placeholders}`, digits, IDs,
    punctuation) passes through byte-for-byte unchanged.
  - `message_catalog.localize(bilingual, resolved_language)` -- the
    one generic function every existing `{en, ta}` bilingual dict in
    this codebase (dashboard pages, action definitions, chat replies)
    is rendered through. Tanglish is always *derived* from the "ta"
    value via `to_tanglish()`, never a hand-written third copy --
    this is why Tanglish support appeared "for free" across dozens of
    already-existing strings with zero risk of drifting from the
    Tamil original.
  - `message_catalog.MESSAGE_CATALOG` -- the small, finite set of
    fixed strings Phase 10A itself introduces (preference-saved
    confirmation, invalid-language rejection, the LLM retry
    instruction, and a few known proposal-lifecycle messages) that did
    not already exist as a bilingual pair elsewhere.
  - `message_catalog.pending_work_lines(summary, resolved_language)`
    -- re-derives the "what needs attention" lines from
    `AdminAssistantService.dashboard_overview()`'s raw `summary`
    counts (never from its `guidance` field, which stays an unchanged,
    English-only contract other callers/tests already depend on).
    Shared by the floating widget's chat reply and the full page's
    Guidance tab so both render identical localized text.

## 2. Deterministic response paths (Step 12)

`AdminAssistantChatService.send_message()` resolves language exactly
once per message (`self._language_service.resolve(...)`) and passes
the concrete `resolved_language` (never `"auto"`) into every reply
builder: `_reply_greeting`, `_reply_help`, `_reply_pending_work`,
`_reply_navigation`, `_reply_provider_lookup`,
`_reply_dataset_discovery_guidance`, and the LLM fallback message.
Because dataset-discovery guidance, provider explanations, and
pending-work summaries all flow through this one chat entrypoint
(there is no separate code path per "topic"), fixing resolution and
localization here structurally covers every category the task listed.

One deliberate exception: `_reply_navigation` always embeds the
literal, untranslated `page.nav_key` (e.g. "Dataset Discovery") in its
message, in every response language -- full dashboard-UI translation
is out of scope for this phase, so an admin in Tanglish/Tamil mode
must still be told the *exact* on-screen button label they can find
and click, not a transliteration of it.

`GET /api/admin/assistant/overview` additively returns
`localized_guidance` (from `pending_work_lines`) and `resolved_language`
alongside the original, unchanged `guidance`/`summary` fields, so the
full Admin Assistant page's Guidance tab can render properly localized
text without needing a chat round-trip.

## 3. LLM-backed response enforcement (Step 6)

`_generate_llm_reply()` takes a required `resolved_language` (never
`"auto"` -- a `KeyError` if it ever is, since `LLM_LANGUAGE_INSTRUCTIONS`
has exactly 3 keys). It appends one concrete instruction block
(`LLM_LANGUAGE_INSTRUCTIONS[resolved_language]`) to the existing
`SYSTEM_INSTRUCTIONS_BASE`, then validates the model's own output with
the already-existing, reused
`core_model.instruction_tuning.language_checks.requested_language_respected()`
(built for a Phase 11 evaluation concern, never re-implemented here).
On a mismatch it retries once with a strengthened instruction
(`catalog_message("llm_reply_language_mismatch_retry", ...)`); a
second mismatch, or any generation failure, returns `None`, and the
caller falls back to the localized `GENERATION_UNAVAILABLE_MESSAGE` --
the assistant is never fully disabled, and it never silently hands
back a reply in the wrong language.

## 4. Preservation rules

Every technical/machine-readable token this task lists (provider
names, dataset names, licence names, model/checkpoint/proposal IDs,
API enums, paths, commands, URLs, versions, checksums, error codes)
survives `to_tanglish()` unchanged, proven by a parametrized test
against 8 real example tokens
(`PHASE_10_COMPLETE_WITH_LIMITATIONS`, `training_approved`,
`licence_unknown`, `checkpoint-v12`, `Hugging Face`, `Apache-2.0`,
`/api/admin/dataset-discovery`, `schema_version`) embedded inside a
Tamil sentence. This works structurally, not via a maintained
exclusion list: the renderer only ever transforms Tamil-*script*
characters, and every one of those tokens is already Latin-script in
the source data.

## 5. Backend APIs

All under the existing `/api/admin/assistant` router (not a new
`/api/admin/admin-assistant` prefix -- the already-shipped router is
reused instead of introducing a second, inconsistent one):

- `GET /preferences` -- the requesting admin's own saved preference.
- `PATCH /preferences` -- CSRF-protected; validates against the same
  4-value enum the database CHECK constraint enforces; audited.
- `POST /preferences/preview` -- CSRF-protected, non-persistent;
  resolves what language *would* apply for a given message/override
  without reading or writing the saved preference.
- `POST /chat` gained an optional `response_language_override` field
  (preview/testing only, per the task's own rule -- never silently
  persisted).
- `GET /overview` gained additive `localized_guidance`/
  `resolved_language` fields.

## 6. Frontend

- `AdminAssistantWidget.jsx`: a "Reply language" `<select>` (தமிழ் /
  English / Tanglish / Auto) next to the existing mode-filter row,
  fetched once per open, saved optimistically with rollback-and-error
  on failure.
- `AdminAssistantPage.jsx`: the identical selector in a new header
  row, reading/writing the exact same backend-stored preference (no
  competing copy); the Guidance tab renders `localized_guidance` when
  present, falling back to the original `guidance` list.
- No new Settings page: none exists in this dashboard today, and
  adding one would violate the task's own "no unrelated duplicate
  settings page" rule.

## 7. Audit

Every preference change is recorded on the existing `audit_logs` table
(`event_type = "admin_assistant_response_language_changed"`,
`old_response_language`, `new_response_language`, `change_source`,
actor = the admin's own public_id) -- never full chat message content.

## 8. Tests

- `tests/database/test_phase32_migration.py` (5) -- schema upgrade,
  CHECK enforcement, per-admin defaults.
- `tests/core_model/test_admin_assistant_language_preference.py` (15)
  -- resolution priority, auto-detection for every category, mixed
  dominance, unknown fallback.
- `tests/core_model/test_admin_assistant_localization.py` (22) --
  Tanglish renderer correctness, machine-token preservation,
  `localize()`/catalog behavior.
- `tests/core_model/test_admin_assistant_registries.py` (+1) --
  admin_assistant page help documents the 4 modes.
- `tests/backend/test_admin_assistant_language_service.py` (9) --
  service-level get/set/resolve/preview, audit write, per-admin
  isolation.
- `tests/backend/test_admin_assistant_language_preference_api.py` (11)
  -- auth/CSRF, valid/invalid enum, isolation, preview never persists,
  `/overview` and `/chat` carry the new fields.
- `tests/backend/test_admin_assistant_llm_language_enforcement.py` (7)
  -- prompt injection, retry-on-mismatch, fallback-to-None,
  Tanglish-output acceptance, `"auto"` structurally rejected.
- `tests/backend/test_admin_assistant_language_deterministic_responses.py`
  (11) -- the task's own explicit end-to-end scenarios: Tamil
  preference + English input -> Tamil; English preference + Tamil
  input -> English; Tanglish preference + Tamil input -> Tanglish;
  Auto follows the message; localized page help, navigation
  (nav_key preserved), provider lookup (provider name preserved),
  dataset-discovery guidance, and the LLM-unavailable fallback.
- `tests/backend/test_admin_assistant_chat_service.py` -- existing 12
  tests unaffected (fixture updated to create a real `admin_accounts`
  row, since `resolve()` now genuinely needs one); +2 new
  dataset-discovery-intent tests already existed from Phase 10.
- Frontend: `AdminAssistantWidget.test.jsx` (+3), new
  `AdminAssistantPage.test.jsx` (5, this page had no prior test file).

**Totals**: 80 new backend+core_model tests (5+15+22+1+9+11+7+11 across
the files above) plus the existing chat-service suite's fixture
update. 8 new/updated frontend tests. Combined targeted regression
across every Phase 10A file plus the full `tests/database/`+
`tests/core_model/` suites: 185 + 854 passed. Live database:
`user_version: 32`, `integrity_check: ok`.

## 9. Manual browser verification (Flows A-F)

Run against the real dev server with a dedicated `phase10a-verifier`
admin account, via Playwright:

- **Flow A (Tamil)**: select தமிழ், ask in English, reply contains
  Tamil script; preference persists across a hard refresh.
- **Flow B (English)**: select English, ask in Tamil, reply contains
  no Tamil script.
- **Flow C (Tanglish)**: select Tanglish, ask in Tamil, reply is
  Latin-script only.
- **Flow D (Auto)**: Tamil input -> Tamil reply, English input ->
  English reply, without changing the saved "Auto" setting.
- **Flow E (governed action)**: Tanglish mode, ask about the
  AI4Bharat provider -- reply is Latin-script Tanglish with the
  provider name and every enum value (`unverified`, `draft`, `mixed`)
  preserved exactly.
- **Flow F (deterministic fallback)**: with no LLM assignment
  configured in this sandbox (the real, standing condition of this
  dev environment), every open-ended question naturally exercises the
  localized `GENERATION_UNAVAILABLE_MESSAGE` fallback in all three
  concrete languages -- confirmed working throughout Flows A-C.

Also verified: the full Admin Assistant page's selector and localized
Guidance tab render correctly (screenshotted); the floating widget and
full page read the identical saved preference (changing it on one
updates what the other shows on next open); the login screen never
renders the Assistant launcher; 390px mobile layout keeps the selector
visible and within the viewport; no unexpected console errors (the
only console entries are the pre-existing, expected `/auth/me` 401
session probe that fires on every fresh page load, present since
Phase 1's login flow and unrelated to this phase).

## 10. Known limitations

- The Tanglish renderer produces a *formal phonetic* transliteration
  (including one real Tamil sandhi rule -- intervocalic/post-nasal
  stop-consonant voicing) rather than hand-tuned colloquial spelling;
  it will not always match the exact spelling a native speaker would
  type by hand (e.g. "ku" vs "kku", formal "aa" vs colloquial "a"
  word-finally).
- Proposal-lifecycle validation/stale-state error messages raised
  directly by `AdminAssistantService` (outside the chat surface --
  e.g. a stale-proposal rejection returned by the REST API's generic
  error handler) remain English-only; only errors actually surfaced
  *through* a chat reply are localized. A message catalog for these
  (`proposal_stale`, `proposal_requires_reason`, `unknown_action_type`)
  already exists and is ready for a future phase to wire in if the
  Propose/Review UI itself is localized.
- `requested_language_respected()`'s script-ratio check can, in
  principle, misjudge a reply that is almost entirely preserved
  technical identifiers with very little actual prose; this is an
  accepted, documented characteristic of the reused Phase 11 function,
  not new logic this phase added.

## 11. Explicit Phase 11 deferral

No licence verification, dataset download/import/quarantine/RAG
sandbox, training approval/execution, model release, new translation
or LLM provider, new identity/settings/conversation-store system,
voice or public-chatbot language settings, full dashboard UI
translation, or retroactive translation of historical chat turns.

**Do not proceed to Phase 11 in this session.**
