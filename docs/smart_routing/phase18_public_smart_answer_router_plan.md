# Phase 18 — Public Smart Answer Router: Plan

Written before any Phase 18 code, per the task's own requirement. This
phase replaces the `/api/chat` placeholder with a real, bounded, safe
public router that reuses the existing (currently Admin-only) model,
RAG, memory, and language infrastructure. It never forks a competing
orchestration engine.

## 0. Baseline inspected (four parallel research passes, direct code reads)

- `backend/services/chat_orchestration_service.py` (full, 659 lines) —
  `ChatOrchestrationService.send_message()` is a single combined
  "assemble RAG + memory + conversation-history + summary evidence,
  then generate" turn processor. It is **hard-locked** to
  `RAG_SCOPE = "admin_diagnostic"` (module constant, line 49) via
  `_verify_assignment()` (line 81), requires a pre-existing
  `session_public_id` from `ConversationSessionService`, and threads
  `admin_id: str` through every call purely for audit/turn attribution
  (no authorization check happens on that value inside the service
  itself — the admin-auth boundary is enforced at the API-route layer
  via `Depends(require_admin)`, not inside this service).
- `backend/services/rag_generation_service.py` — a **separate**
  generation path (used by RAG Sandbox / admin RAG testing), also
  hard-locked to the same `RAG_SCOPE` constant. `ChatOrchestrationService`
  does **not** call this service — it calls `InferenceRuntimeService.
  run_generation()` directly. Phase 18 therefore never needs to touch
  `rag_generation_service.py` at all.
- `backend/services/model_assignment_service.py` — a `public_chat`
  assignment scope **already exists as a fully-built concept**
  (`docs/model_assignment_scopes.md`), gated by a real
  `_public_activation_gate()` (lines 434-492) inside `activate_assignment()`
  covering eligibility, canary metrics, required approvals, and
  explicit confirmation. Phase 18 does not need to build this gate —
  only resolve an assignment that already passed it
  (`scope_key == "public_chat"`, `status == "active"`). Confirmed live
  in the dev DB: `inference_assignment_scopes` already has a
  `public_chat` row (id 4), but **zero assignments currently use it** —
  no admin has activated one yet. `ensure_instance_loaded()` (line 573)
  is scope-agnostic and safe to call for any active assignment.
- `core_model/conversation/__init__.py` — `SESSION_MODES = ("stateless",
  "session_memory", "consented_memory", "private_no_persist")`,
  `PARTICIPANT_TYPES = ("admin", "internal_test_user",
  "future_user_reference")`. `"future_user_reference"` is reused as-is
  for public participants — no new taxonomy value needed.
- `core_model/conversation/language_continuity.py` (full) —
  `decide_language()` picks a language *category* only (explicit
  request → confirmed preference → detection → recent-turn fallback);
  it does **not** implement "Tanglish → Tamil output" itself. That
  business rule is a Phase 18 policy layer on top of its result.
- `core_model/knowledge_routing/safety_signal.py` (Phase 17, this
  session) — `classify_safety_signal()` already returns
  `safe|sensitive_but_allowed|requires_policy_review|likely_disallowed|unknown`
  with reason codes and matched categories covering every category
  Step 6 lists. **Reused verbatim** as the input safety gate — no new
  classifier is built.
- `core_model/model_evaluation/refusal_checks.py` (full) — output-side
  `detect_refusal()`, `detect_harmful_details()` (matches procedural-harm
  step-by-step/ingredient patterns), `detect_safe_redirection()`,
  `detect_excessive_moralizing()`. Reused for the output safety gate's
  "unsafe operational detail" check.
- `core_model/rag/access_filter.py` — `apply_access_filters()` /
  `RetrievalFilters` already support `approval_statuses`/
  `licence_statuses` allow-lists at the **per-call** level via
  `RetrieveRequest.filters` (a `RetrievalFiltersPayload`, already a
  first-class parameter `ChatOrchestrationService` passes through
  untouched today). This means the public RAG path can force
  "approved sources, non-blocked licence only" **without any service
  modification** — just by constructing a restrictive
  `RetrievalFiltersPayload` and threading it through (one new optional
  parameter on `send_message()`, see §2).
- `production_rag_release_candidates` (schema.py:9472) — live-production
  signal is `status='activated' AND production_visible=1`; its
  `retrieval_profile_id` is exactly what a public retrieval call needs.
  Confirmed empty in the dev DB today (no admin has activated a
  production RAG candidate yet).
- Citation construction: two implementations exist, confirmed by
  direct read (`rag_generation_service.py:400-436` →
  `rag_answer_citations`; `chat_orchestration_service.py:556-587` →
  `chat_response_citations`). Both repositories' `public_row()` strip
  internal integer FKs (`chunk_id`, `source_id`, `rag_chunk_id`,
  `memory_item_id`) **without resolving them to a title/URL first** —
  neither implementation alone produces the public-safe citation shape
  Step 11 requires. `chat_response_citations` (used by
  `ChatOrchestrationService`, the service Phase 18 must reuse) is the
  canonical path; Phase 18 adds one new thin read adapter that joins
  `rag_chunks → rag_source_versions → rag_knowledge_sources` for
  title/type **before** the internal IDs would otherwise be dropped.
  Neither existing `record_citation()` implementation is touched.
- `core_model/feedback/__init__.py` — `FEEDBACK_TYPES` already includes
  `thumbs_up`, `thumbs_down`, `language_report`, `safety_report` —
  covers all four required public feedback controls with zero schema
  change.
- `backend/api/routes/chat.py` (full, quoted) — genuinely the only
  fully public (no `Depends(require_admin)`) real route besides
  `auth.py`/`health.py`. `apps/chatbot` (separate from
  `apps/admin-dashboard`) already exists with a `ChatInput.jsx`
  language selector offering Auto/Tamil/English/**Tanglish** — the
  Tanglish *output* option must be removed per Step 27's own rule.
  `apps/chatbot` has **no test tooling** (no vitest) — added in this
  phase.
- No HTTP-level rate-limiting middleware exists anywhere in the repo —
  built from scratch, in-process, CPU-first.
- `backend/core/exceptions.py`'s `BrudError` (custom `status_code`/
  `code`) is the correct mechanism for the Step 23 stable named error
  codes.

## 1. The one deliberate, additive, backward-compatible service change

Rules 4-5 require reusing `ChatOrchestrationService`, never forking it.
But `send_message()` as written cannot serve public traffic: it always
combines RAG + memory + conversation-history evidence in one call
(no per-route "only RAG" / "only model" mode), and its
`no_evidence_available` gate assumes either evidence or prior
conversation history always exists — untrue for a public user's first
turn with a plain model-answerable question.

**Decision:** add exactly three new keyword parameters to
`ChatOrchestrationService.send_message()`, every one defaulting to
today's exact behavior so every existing Admin call site (Chat Lab,
diagnostics, and their tests) is provably unaffected:

```python
def send_message(
    self, session_public_id, payload, admin_id, *,
    required_scope: str = RAG_SCOPE,                     # "admin_diagnostic"
    evidence_mode: str = "auto",                          # "auto" | "model_only" | "rag_only" | "memory_only"
    rag_filters: RetrievalFiltersPayload | None = None,   # None -> RetrievalFiltersPayload() (today's behavior)
) -> dict[str, Any]:
```

- `required_scope` is passed straight into `_verify_assignment()`
  instead of the module constant. Phase 18 passes `"public_chat"`.
- `evidence_mode` gates which retrieval calls execute *before*
  `_assemble_and_generate` even runs (`model_only` skips both RAG and
  memory retrieval; `rag_only` skips memory; `memory_only` skips RAG;
  `auto` is unchanged), and gates the `no_evidence_available` check
  (bypassed entirely for `model_only`, since a model-only answer is
  never expected to have supplied evidence).
- `rag_filters` is threaded into the existing `RetrieveRequest.filters`
  parameter instead of a hardcoded empty `RetrievalFiltersPayload()`.

This is the **only** change to existing Admin-facing code in this
phase. It is proven backward-compatible by re-running the full,
unmodified existing chat-orchestration test suite after the change
(Step 40) and by one new explicit test asserting default-parameter
calls are byte-identical in behavior to pre-change calls.

## 2. Public router architecture

```
Public Chat Request
  -> request validation (bounded DomainModel, extra="forbid")
  -> input normalization (text_normalization.normalize_text)
  -> language classification (language_routing.classify_language + language_continuity.decide_language)
  -> minimal input safety gate (knowledge_routing.safety_signal.classify_safety_signal)
  -> Phase 17 knowledge-routing classification (KnowledgeRoutingClassificationService, persist=False)
  -> PublicRouteAvailabilityService (recommended_route -> resolved_route/status/reason_codes)
  -> route execution (exactly one of: core_model | approved_rag | memory | clarify | refuse | insufficient)
       -> core_model/approved_rag/memory all funnel through ChatOrchestrationService.send_message()
          with evidence_mode set to match the resolved route -- never "auto"
  -> evidence/grounding validation (already inside send_message(); Phase 18 reads response_status/citations)
  -> minimal output safety gate (refusal_checks + leakage flags already returned by run_generation())
  -> public language policy (Tanglish input -> Tamil output; output-language guard)
  -> structured response normalization (public-safe fields only)
  -> audit (PublicChatRoutingRepository event row + AuditLogRepository, no raw text)
```

`PublicChatRoutingService` (new, thin) owns this flow. It contains
zero duplicated model-inference, RAG-retrieval, memory, citation, or
language-classification logic — every step above calls an existing
service or Phase 17 module.

## 3. Executable-route table

| Recommended (Phase 17) | Resolved this phase | How |
|---|---|---|
| `core_model` | `core_model` | `send_message(evidence_mode="model_only")` |
| `approved_rag` | `approved_rag` if an eligible production RAG space exists, else `insufficient` | `PublicRagScopeResolver` + `send_message(evidence_mode="rag_only", rag_filters=approved_only)` |
| `memory` | `memory` if consent + existing scoped memory, else `clarify`/`insufficient` | `send_message(evidence_mode="memory_only")` |
| `clarify` | `clarify` | no execution — returns Phase 17's clarification signal directly |
| `refuse` | `refuse` | no execution — safety refusal in answer language |
| `insufficient` | `insufficient` | no execution |
| `trusted_web` | `insufficient` (`fallbacks_attempted=["trusted_web_unavailable"]`) | no execution, ever |
| `tool` | `insufficient` (`fallbacks_attempted=["tool_unavailable"]`) | no execution, ever |

`PublicRouteAvailabilityService` is the single place this mapping is
expressed, as an ordered decision function (mirrors Phase 17's own
route-recommender precedence-chain style) — never a silent substitution.

## 4. Minimal live safety design

**Input gate** (before any route executes): `classify_safety_signal(text)`
→ mapped `safe→allow`, `sensitive_but_allowed→allow_with_caution`,
`requires_policy_review→needs_review`, `likely_disallowed→refuse`,
`unknown→allow_with_caution` (conservative default — an unmatched
input is never blocked outright, matching Phase 17's own "unknown is
not evidence of anything" philosophy). `refuse` short-circuits straight
to the refusal route before classification/routing even runs.
`needs_review` proceeds but is flagged in response metadata and
audited; it does not block by itself in this minimal gate (full
Phase 22 governance will add human-review queuing later).

**Output gate** (after generation, before returning): reuses
`InferenceRuntimeService.run_generation()`'s own already-computed
`role_token_leakage`/`prompt_leakage`/`unicode_valid` flags (no new
leak-detection code needed) plus `refusal_checks.detect_harmful_details()`
on the generated text for the "unsafe operational detail" check. Any
failure replaces the answer with a safe bounded fallback and audits the
reason; the unsafe raw text is never persisted.

This is explicitly documented as a **minimal** gate — full Phase 22
tool-aware safety governance is out of scope.

## 5. Public language policy

Tamil→Tamil, English→English, Tanglish→Tamil (default), mixed→Tamil
(default unless an explicit supported override selects English).
Implemented as one pure function,
`public_language_policy.resolve_answer_language()`, layered on top of
`language_continuity.decide_language()`'s category output — never
inside that shared function, so Admin Assistant's own language policy
(which allows Tanglish) stays completely isolated (Rule: Admin
Assistant language policy ≠ public chatbot language policy).

**Output-language guard**: after generation, if the answer text itself
is classified as Tanglish (`classify_language()` on the generated
text), attempt exactly one safe regeneration with an explicit
Tamil-script instruction; if still invalid, substitute the Tamil
fallback response and record a `language_policy_violation` audit
event. No external translation provider is used anywhere.

## 6. RAG production-space selection

`PublicRagScopeResolver.resolve() -> ResolvedRagScope | None`. Queries
`production_rag_release_candidates` for `status='activated' AND
production_visible=1`, joins to its `retrieval_profile_id` →
`rag_retrieval_profiles.public_id` (must be `status='active'`), and
constructs a restrictive `RetrievalFiltersPayload(approval_statuses=
["approved"], licence_statuses=["open", "unknown"])` (excludes
`restricted` and `blocked` — a deliberately conservative default,
documented explicitly; `restricted` sources are not public-safe by
default in this phase). Returns `None` (→ `insufficient`, no sandbox
fallback) if no such candidate exists. A dedicated test proves
activating/deactivating a production candidate changes what public
retrieval can see — directly resolving Phase 16's "production
activation has zero runtime effect" finding.

## 7. Memory scope policy

Public memory participants use `participant_type="future_user_reference"`
(existing enum value, no schema change) keyed by a server-issued,
unguessable `conversation_id` (used as `participant_scope_key` — never
client-suppliable as a raw ID beyond continuing a previously-issued
one). The `memory` route requires `memory_consent=true` on the request
**and** an already-active `conversation_memory_policies` row (none
exists in the dev DB today — provisioning one is a normal Admin
governance action, not something this phase auto-creates; if absent,
the route honestly resolves to `insufficient`). No public turn is
auto-mined into a memory item in this phase beyond an explicit,
bounded language-preference write on override selection — full memory
proposal/extraction from arbitrary public chat content is out of scope
(would require content judgment calls beyond this phase's remit).
Cross-user isolation is inherited for free from `MemoryService`'s
existing exact-`participant_scope_key` filtering — no new isolation
logic needed.

## 8. Response metadata schema

See `docs/smart_routing/phase18_public_chat_response_schema.md`
(written alongside implementation, finalized in Step 41) for the full
field list matching Step 4 exactly. Confidence bands follow Step 25's
mapping table verbatim, always paired with reason codes, never a
fabricated percentage.

## 9. Error / fallback behavior

Every `BrudError` subclass in Step 23's list maps 1:1 to a
`backend/core/exceptions.py`-compatible class (`code` = the exact
stable string, e.g. `code = "CHAT_WEB_NOT_AVAILABLE"`). No internal
exception or stack trace ever reaches the response body (inherited for
free from the existing generic-`Exception` handler).

## 10. Privacy and retention

No raw public question or answer text is stored in the new public
routing-event table — only a SHA-256 input hash, route/status/reason
codes, and latency, mirroring Phase 17's own
`routing_classification_decisions` convention exactly. Full
conversation turn text is only persisted where the existing
`session_mode`/consent rules already allow it (unchanged
`ConversationMemoryRepository` behavior), and only for sessions the
public user's own `conversation_id` scopes to.

## 11. Frontend integration

`apps/chatbot` is updated to the new response schema, a compact route
label, clarification/refusal/insufficient states, loading/timeout/
rate-limit states, feedback controls, and the language selector wired
as an **output-only** override (Auto/Tamil/English — Tanglish removed
from the option list, per Step 27). Vitest + Testing Library are added
to `apps/chatbot` (currently absent) following the exact tooling
`apps/admin-dashboard` already uses.

## 12. Phase 19 handoff

Phase 18 hands Phase 19 exactly: a real, working public router with
honest unavailable-route handling for `trusted_web`/`tool`; a
`PublicChatRoutingService` that Phase 19's knowledge-gap registry can
subscribe to (via its already-audited routing events) without any
further Phase 18 code changes; and zero coupling to a knowledge-gap
table (none is created here, per explicit out-of-scope).

## 13. Pass/fail criteria for this plan

Phase 18 code begins once this document is committed to disk, matching
the Phase 15A/16/17 precedent.
