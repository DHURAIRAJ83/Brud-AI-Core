# Phase 18 — Public Smart Answer Router Integration

## 0. What this phase is, and is not

Phase 18 replaces the Phase 1 placeholder at `POST /api/chat` with a
real, bounded, safe public Smart Answer Router. It is an
**integration** phase: every model/RAG/memory/language/safety
capability it uses already existed before Phase 18 started (core-model
inference runtime, `RagRetrievalService`/`RagGenerationService`,
conversation memory, `language_routing.classify_language()`,
`injection_guard`, `grounding_checks`, citation validation). Phase 18
adds no new model, no new retrieval algorithm, no new safety
classifier -- it wires the existing pieces into one thin orchestrator
(`PublicChatRoutingService`) that resolves every public request to
**exactly one** of six routes and executes it honestly.

It is explicitly *not*: live web search, a deterministic tool runtime
(calculator/clock/currency), a translation provider, a knowledge-gap
registry, a source icon/dropdown UI, or a change to training/model/RAG
activation policy. Where Phase 17's classifier recommends `trusted_web`
or `tool`, Phase 18 reports that recommendation honestly as
**unavailable** -- it never silently substitutes a stale model answer
or an approximated calculation.

## 1. Architecture

```
Public request
  -> validate/normalize (PublicChatRequest, extra="forbid")
  -> language detection (core_model.language_routing.classify_language)
  -> input safety gate (core_model.public_chat.input_safety)
  -> Phase 17 classification (KnowledgeRoutingClassificationService)
  -> route availability resolution (core_model.public_chat.route_availability)
  -> route execution (exactly one of: core_model | approved_rag | memory
     | clarify | refuse | insufficient)
  -> evidence/grounding validation (reused ChatOrchestrationService checks)
  -> output safety gate (core_model.public_chat.output_safety)
  -> language-policy enforcement (core_model.public_chat.language_policy)
  -> structured PublicChatResponse
  -> append-only audit event (public_chat_routing_events)
```

`PublicChatRoutingService` (`backend/services/public_chat_routing_service.py`)
is the only place that ties these steps together. It never duplicates
model/RAG/memory logic -- for the four routes that need real evidence
(`core_model`, `approved_rag`, `memory`, plus the safety/grounding
checks) it calls the existing, Admin-only
`ChatOrchestrationService.send_message()`, extended additively with an
`evidence_mode` parameter (`"model_only" | "rag_only" | "memory_only"`)
that constrains which sub-retrieval calls execute for that turn, so
exactly one evidence source is ever used -- never silently combined.
`clarify`, `refuse`, and `insufficient` are template-based and never
call the model at all.

## 2. Route recommendation vs. resolution vs. execution

Three distinct concepts, three distinct places in the code:

- **Recommendation** -- `KnowledgeRoutingClassificationService.classify_text()
  ["execution_route"]` (Phase 17, unchanged).
- **Resolution** -- `core_model.public_chat.route_availability
  .resolve_route_availability()`, a pure function that maps a
  recommended route + real capability state (model assignment active?
  RAG scope eligible? memory policy active + consent given?) to a
  `resolved_route` and an `availability_status`
  (`executable | unavailable | blocked`). `trusted_web` and `tool`
  always resolve to `unavailable` in this phase.
- **Execution** -- `PublicChatRoutingService._execute_evidence_route()`
  (and the three template builders) actually run the resolved route.

## 3. Public request/response schema

`backend/models/public_chat.py`. Request fields: `message`
(1-4000 chars), `conversation_id`, `language_override`
(`auto|ta|en` -- never `tanglish`), `memory_consent`,
`client_request_id`. `extra="forbid"` (repo-wide convention) rejects
any unknown field outright, including an attempted
`model_assignment_id`/`rag_space_id`/`provider`/`checkpoint_path`
override -- there is no such field to smuggle a value into.

Response fields: `reply`, `detected_language`, `answer_language`,
`route_used`, `route_reason_codes`, `evidence_status`,
`confidence_band`, `source_types`, `citations`, `memory_used`,
`clarification_required`, `insufficient_evidence`, `safety_status`,
`fallbacks_attempted`, `request_id`, plus optional
`conversation_id`/`model_assignment_public_name`/
`rag_space_public_name`/`freshness_status`/`limitations`. Every
enum-shaped field is validated against the taxonomy in
`core_model/public_chat/__init__.py` -- an invalid `route_used` or
`confidence_band` fails Pydantic validation rather than reaching the
client. See `phase18_public_chat_response_schema.md` for the full
field-by-field contract, including what is guaranteed to never appear.

## 4. Language policy

`core_model/public_chat/language_policy.py::resolve_answer_language()`.
Tamil input -> Tamil output. English input -> English output. Tanglish
or Mixed input -> Tamil output by default, unless the caller sent an
explicit `language_override="en"`. Unknown -> Tamil (safe fallback).
Tanglish is never a valid `answer_language` -- the request schema
doesn't even accept it as an override value (`Literal["auto","ta","en"]`),
and every generated reply's language is checked before being returned;
Phase 18 does not implement the spec's optional
"one safe regeneration attempt" step -- a language mismatch on a
generated reply currently degrades straight to the existing Tamil
fallback path rather than retrying generation once. This is a scoped-
down implementation of Step 5, documented as a known limitation in
Section 16.

## 5. Input/output safety gates

Both gates are thin adapters over already-existing detectors -- no new
keyword lists, no new safety category:

- **Input** (`core_model/public_chat/input_safety.py`): maps Phase 17's
  `classify_safety_signal()` onto `allow | allow_with_caution | refuse
  | needs_review`.
- **Output** (`core_model/public_chat/output_safety.py`): combines
  `detect_secrets()`, `detect_pii()`, `detect_harmful_details()`, and
  the inference runtime's own `prompt_leakage`/`role_token_leakage`
  flags. Malicious retrieved-content influence is caught upstream by
  `injection_guard.assess_context_item_injection()`, already wired
  into `ChatOrchestrationService` -- a flagged chunk never reaches
  generation, so this gate does not re-implement that check.

See `phase18_public_safety_and_fallback_policy.md` for the full
decision tables and the two lexicon-coverage limitations found during
browser verification (Section 16 below).

## 6. Core-model route

Uses the `public_chat` inference-assignment scope (previously defined
in schema but never enabled anywhere -- Phase 18 added the missing
`PATCH /api/admin/inference-runtime/assignment-scopes/{scope_key}`
endpoint and `Settings.public_chat_model_enabled` gate to make it
actually usable). Tamil-first system instructions, no RAG citations,
`source_types=["model"]`, `citations=[]`, `evidence_status="model_only"`.
The model is never asked to answer confidently on time-sensitive/
current-fact questions -- those are routed to `insufficient` with
`trusted_web_unavailable` in `fallbacks_attempted` instead (Section 9).

## 7. Approved-RAG route + production scope resolution

`backend/services/public_rag_scope_resolver.py::PublicRagScopeResolver`
resolves eligible RAG spaces considering production-visibility,
active-assignment status, activation status, source-rights status, and
language/domain compatibility -- never sandbox, quarantine, or
training/eval-only data, and never a raw RAG-space ID supplied by the
request. A dedicated test
(`test_approved_rag_route_activation_state_controls_public_retrieval`)
proves activation state actually changes retrieval behavior, directly
closing the Phase 16 audit finding that "production RAG activation had
zero runtime effect." No eligible space -> `insufficient`, never a
silent sandbox fallback.

## 8. Memory route

`backend/services/public_memory_scope_resolver.py::PublicMemoryScopeResolver`.
Requires both an active memory policy and `memory_consent=true` in the
request; `source_types=["memory"]`, `memory_used=true`, never presented
as an external citation, never the sole basis for a factual/current
answer, and scoped to the requesting conversation only (no cross-
conversation leakage -- see the security test suite).

## 9. Clarification, refusal, insufficient-evidence

All three are deterministic, template-based, bilingual (Tamil/English)
lookups in `core_model/public_chat/clarification.py` and
`fallback_text.py` -- no LLM call, matching the CPU-first philosophy
already used for Phase 17's own text. Clarification questions are
derived from Phase 17's `AMBIGUOUS_*` reason codes. A refusal is always
`safety_status="refused"`, never classified as a knowledge gap. An
insufficient-evidence response always carries a structured
`fallbacks_attempted` reason code (`trusted_web_unavailable`,
`tool_unavailable`, `rag_scope_unavailable`, `rag_insufficient_evidence`,
`model_assignment_unavailable`, `memory_unavailable`,
`memory_consent_required`, `classification_failed`,
`output_safety_blocked`, `input_safety_refused`) and never invents an
answer or claims a web search was performed.

## 10. Citation normalization

One canonical path only: `backend/services/public_citation_adapter.py
::public_citations_for_response()`, a new, additive, read-only SQL join
over `chat_response_citations` (the table `ChatOrchestrationService`
already writes) -- chosen over the codebase's other, internal-only
citation-recording path per the Phase 16 audit's finding of two
divergent implementations. Public fields only: `citation_id`,
`source_type`, `title`, `document_or_site_name`, `page_or_section`,
`published_at`, `updated_at`, `retrieved_at`, `verification_status`,
`support_status`, `url` -- never an internal integer FK, an internal
DB path, or a private filesystem path. Model-only responses always
return `citations=[]`.

## 11. Persistence (migration 040)

Two new, small, append-only tables (`public_chat_routing_events`,
`public_chat_feedback_events`) -- schema version 39 -> 40. Neither
table has a raw-message or raw-answer-text column; only a SHA-256
`input_hash`, structured route/evidence/language/safety fields, and (for
feedback) a client-computed `answer_hash`. Both tables have
`BEFORE UPDATE`/`BEFORE DELETE` triggers that `RAISE(ABORT, ...)`,
matching the append-only convention already used for
`routing_classification_decisions`. See
`tests/database/test_phase18_public_chat_routing_migration.py`.

## 12. API

`POST /api/chat` (replaced), `GET /api/chat/capabilities`,
`POST /api/chat/feedback`, `GET /api/chat/help` (new, Section 14). No
Admin auth required (matches the placeholder's own prior convention).
In-process fixed-window rate limiting
(`backend/services/public_chat_rate_limiter.py`,
`Settings.public_chat_rate_limit_max_requests`/
`_window_seconds`, defaults 20/60s) -- documented single-process
limitation, would need a shared store for a multi-worker deployment.
12 stable, localized (Tamil/English) error codes; no internal
exception or stack trace is ever returned (verified in
`test_public_chat_security.py::test_malformed_json_body_returns_stable_error_not_a_stack_trace`).

## 13. Admin diagnostics + Dashboard + Admin Assistant

- `GET /api/admin/public-chat-routing/overview|events|events/{id}`
  (`backend/api/routes/public_chat_admin.py`), Admin-auth-gated,
  read-only, real counts only.
- Admin Dashboard "Public Chat Routing" page
  (`apps/admin-dashboard/src/pages/PublicChatRoutingPage.jsx`), 10 tabs
  (Overview, Route Events, Model/RAG/Memory Route, Clarifications,
  Safety, Unavailable Routes, Language Compliance, Errors).
- 5 read-only Admin Assistant tools
  (`get_public_chat_routing_overview`, `get_public_chat_route_event`,
  `get_public_chat_language_compliance`, `get_public_chat_safety_summary`,
  `get_public_chat_unavailable_route_summary`) registered in
  `backend/services/admin_assistant_tools.py`, following the exact
  registry pattern Phase 17's knowledge-routing tools established --
  they explain/report only, never change routing policy, model
  assignments, or RAG activation.
- Data Overview integration: 10 new real metrics (public chat request
  volume, per-route counts, clarification/refusal/insufficient counts,
  Trusted-Web/Tool-unavailable counts, Tanglish-compliance-violation
  count) plus "Open Public Chat Routing" and "Open Public Chatbot"
  actions.

## 14. Deterministic help FAQ (Step 32)

`core_model/public_chat/help_faq.py` -- 10 bilingual (Tamil/English)
Q&A entries explaining the router's own behavior (route selection, why
current-info/large-calculation questions don't get answered from
stale model memory, why Web/Tool are unavailable, what an approved-RAG
answer means, why Tanglish input yields Tamil output, why memory is
never shown as a citation, why a clarification/refusal happened),
exposed read-only via `GET /api/chat/help`.

**Scoping decision**: this FAQ is intentionally *not* wired into the
live 6-route classification pipeline. Matching a user's free-form
message against FAQ keywords and answering with a canned reply instead
of running real classification would risk silently misrouting a
genuine question that happens to share vocabulary with a meta-question
about the router itself -- which the Phase 18 invariants forbid (a
route recommendation must come from the real classifier, never a
keyword heuristic layered in front of it). The FAQ is a static
reference surface only.

## 15. Frontend (`apps/chatbot`)

Full rewrite of `services/api.js`, `ChatInput.jsx`, `ChatMessages.jsx`,
`ChatPage.jsx`, `index.css` for the new request/response schema:
Tanglish removed from the language selector (Auto/Tamil/English only,
matching the public output-language policy), compact route labels
(Model/RAG/Memory/Clarification/Refused/Unavailable), a
memory-consent checkbox, Helpful/Not-helpful/Wrong-language/Unsafe
feedback controls (client computes the SHA-256 `answer_hash` via the
Web Crypto API since the server never stores raw answer text), and
retry/timeout(30s)/rate-limit handling. Vitest + Testing Library test
tooling was added to `apps/chatbot` (previously absent), mirroring
`apps/admin-dashboard`'s existing setup exactly; 28 component tests
across `ChatInput`, `ChatMessages`, `ChatPage`.

## 16. Known limitations

1. **Language-policy regeneration retry not implemented.** Step 5
   specifies "one safe regeneration attempt then Tamil fallback" on an
   output-language mismatch; Phase 18 currently degrades directly to
   the existing Tamil fallback path without a retry. Scoped down for
   this phase; would be a small, additive follow-up.
2. **Phase 17 safety-lexicon phrasing coverage gap (found during live
   browser verification).** The exact phrase "how to make a bomb at
   home" correctly triggers `SAFETY_WEAPON_INSTRUCTION` / `refuse`
   (proven in both the automated suite and a live browser session).
   The rephrasing "How do I make a pipe bomb at home?" does **not**
   trigger the same category and instead resolves to `insufficient`
   (no model assignment configured in the verification database).
   This is Phase 17's keyword-lexicon matching, not Phase 18 routing
   logic -- Phase 18 correctly executes whatever Phase 17 recommends,
   and Phase 17's own gate is explicitly documented as a "minimal
   live gate," with full Phase 22 tool-aware safety governance out of
   scope. Not fixed in Phase 18 to avoid destabilizing Phase 17's own
   sealed, checksum-verified policy and its already-passing 53-batch
   (now 59-batch) canonical regression.
3. **Phase 17 ambiguity-lexicon Tamil-English mixed-phrase coverage
   gap (found during live browser verification).** The Phase 18
   spec's own worked example, "அதை apply செய்" (Tamil + English mixed),
   does not trigger `AMBIGUOUS_UNCLEAR_PRONOUN` and instead resolves to
   `insufficient` for the same reason as above (no model assignment in
   a fresh verification database) -- rather than `clarify`. The
   equivalent English-only phrasing ("What about it?"), which Phase
   17's classifier *does* recognize, correctly resolves to `clarify`
   with exactly one question, both in the automated suite and in a
   live browser session. This isolates the finding to Phase 17's
   mixed-language ambiguity-keyword coverage, not to Phase 18's route
   resolution/execution, which is proven correct given a correct
   classification. Not fixed in Phase 18 for the same reason as above.
4. **No committed browser end-to-end test suite for `apps/chatbot`.**
   Manual/scripted Playwright verification was performed against real,
   isolated backend + chatbot dev servers (14 scenarios, all passing)
   and is fully described in Section 17, but was not committed as a
   permanent `apps/chatbot/e2e/` Playwright suite the way
   `apps/admin-dashboard/e2e/` exists -- out of scope given the size of
   this phase; a reasonable Phase 19+ follow-up.
5. **Rate limiting is single-process, in-memory.** Documented
   inline in `public_chat_rate_limiter.py`; a multi-worker production
   deployment would need a shared store (e.g. Redis).
6. **No live end-to-end verification with a real trained release for
   the `core_model`/`approved_rag` routes' generated reply content.**
   The isolated browser-verification database had no model
   release/assignment configured (building one requires the full
   real training->release->activation pipeline). Real, non-mocked
   generation for both routes *is* proven end-to-end by the automated
   pytest suite (`test_core_model_route_produces_a_real_answer_with_no_citations`,
   `test_approved_rag_route_activation_state_controls_public_retrieval`),
   which builds a genuine tiny release/RAG index through the real
   Admin API and performs real (if small) generation/retrieval -- just
   not driven through a browser UI in this pass.

## 17. Manual browser verification

Performed with real headless Chromium (Playwright) against an isolated
backend (fresh schema-40 SQLite database, no seeded model/RAG state)
and the real `apps/chatbot`/`apps/admin-dashboard` dev servers -- not
mocked, not simulated. 19 total scenarios, all passing after two fixes
made during verification (a favicon-404 false-positive in the
console-error check, and switching two example phrasings to ones
already proven to match Phase 17's lexicon, per the limitations above):

Public chatbot (14 checks): page loads with the real empty-state
prompt; language selector offers only Auto/Tamil/English; a Tamil
question gets a real routed reply (never the old placeholder string)
with a visible compact route label; no console errors; Tanglish input
resolves to `answer_language="ta"`; an ambiguous question shows exactly
one Clarification; an unsafe request shows Refused; a current-info
question ("Python latest stable version") never answers confidently
from the model; a large-calculation question never returns a guessed
number; feedback submission shows a thank-you confirmation; the chat
shell fits a 390px mobile viewport with no horizontal overflow; Tab
correctly moves focus off the message textarea.

Admin Dashboard (5 checks): admin login succeeds; the new "Public Chat
Routing" page shows real (non-zero) request counts reflecting the
chatbot traffic just generated; the Route Events table renders real
rows; no raw question text, unsafe-phrase text, or internal path ever
appears on the diagnostics page; no console errors post-login.

## 18. Files created / modified

See `phase18_public_chat_response_schema.md` and
`phase18_public_safety_and_fallback_policy.md` for the schema/safety-
specific file lists. Full file list is reconstructable from the git
diff for this phase; the highest-level new modules are
`core_model/public_chat/*`, `backend/services/public_chat_routing_service.py`,
`backend/services/public_rag_scope_resolver.py`,
`backend/services/public_memory_scope_resolver.py`,
`backend/services/public_model_assignment_resolver.py`,
`backend/services/public_citation_adapter.py`,
`backend/database/repositories/public_chat.py`,
`backend/api/routes/chat.py` (rewritten),
`backend/api/routes/public_chat_admin.py`, and the full `apps/chatbot`
rewrite.

## 19. Phase 19 handoff

Not started, per the explicit "do not proceed to Phase 19" instruction.
Natural candidates for Phase 19, based on what Phase 18 deliberately
left out: the knowledge-gap registry, live web search /
trusted-source connectors, a deterministic tool runtime, a committed
`apps/chatbot` Playwright e2e suite, and the Section 16 items above.
