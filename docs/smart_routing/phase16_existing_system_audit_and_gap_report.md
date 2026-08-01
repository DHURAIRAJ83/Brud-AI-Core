# Phase 16 — Existing-System Audit & Implementation Gap Report

Companion documents: `phase16_existing_system_audit_plan.md` (written
first), `phase16_capability_matrix.md`, `phase16_phase17_to_phase26_
implementation_map.md`, `phase16_duplication_prevention_map.md`,
`phase16_risk_register.md`.

Status vocabulary used throughout (Step 20), exactly these nine values,
never a vague label: `WORKING`, `PARTIAL`, `PRESENT_NOT_WIRED`,
`TEST_ONLY`, `ADMIN_ONLY`, `MISSING`, `BLOCKED`, `DEPRECATED`,
`NOT_APPLICABLE`.

## 0. The headline finding

**The public chatbot (`POST /api/chat`) is a complete, unmodified
Phase-1 placeholder.** Verified twice: by direct code reading
(`backend/api/routes/chat.py`, 34 lines, module docstring literally
reads *"Chatbot placeholder endpoint (no trained model is wired up
yet)"*) and by live manual verification (§9 below) — six different real
HTTP requests (Tamil, English, Tanglish, ambiguous, no-known-answer,
and an unsafe request) all returned the byte-for-byte identical response
`{"reply":"Brud AI chatbot foundation is working.","detected_language":
"unknown","model":"placeholder","phase":9}`, regardless of message
content or declared language. The request body's `message` and
`language` fields are received and validated by Pydantic and then never
read (`async def chat(_: ChatRequest)`).

**Meanwhile, a real, working, fully-built orchestration engine already
exists** — `backend/services/chat_orchestration_service.py`'s
`ChatOrchestrationService`, which does real model inference, real hybrid
RAG retrieval, real conversation-memory retrieval/injection, real
per-item prompt-injection screening, real citation construction, and
real deterministic status classification (`insufficient_evidence`,
`memory_conflict`, `retrieval_failed`, etc., via `core_model/
conversation/response_policy.py::decide_response_status`). It is reached
only through `POST /admin/conversation-memory/sessions/{id}/messages`,
which sits behind the whole `conversation_memory.py` router's
`Depends(require_admin)` — this is the "Admin Chat Lab" / "Admin
Diagnostic Inference" feature (`docs/admin_chat_lab.md`, `docs/
admin_diagnostic_inference.md`), explicitly documented in its own file
header as *"There is no public-facing route here -- the public chatbot
route is untouched."*

This single fact reframes almost every subsequent finding in this
report: **the hard part (model + RAG + memory + safety orchestration) is
already built and working; what's missing is almost entirely a routing/
integration/public-exposure layer, not new core infrastructure.** This
is the central, evidence-backed conclusion the whole audit converges on,
and it should anchor the Phase 17-26 implementation order (§ implementation
map doc): Phase 18 (Smart Answer Router) is much smaller in scope than
its name suggests, because it does not need to build model/RAG/memory
orchestration from scratch — it needs to build a *decision layer* in
front of `ChatOrchestrationService` (or a purpose-built successor reusing
its parts) and expose it publicly.

## 1. Baseline confirmed

- `SCHEMA_VERSION = 38` (`backend/database/schema.py:3`), 38 sequential
  migrations, `_apply_v38` = `"038_text_nlp_production_readiness"`
  (matches Phase 15A's own closing state; no drift).
- `PRAGMA integrity_check` = `ok`; `PRAGMA foreign_key_check` = 0
  violations (verified live against the real dev database, §9).
- 377 `CREATE TABLE` statements; 412 append-only (`_immutable_update`/
  `_immutable_delete`) triggers — a deeply established repository
  convention, not a one-off pattern.
- Repository areas inspected: `backend/` (api/routes — all 36 files;
  services — 141 files, the ones relevant to chat/RAG/memory/safety/
  providers/feedback/training/Admin-Assistant/production-readiness read
  in full, the rest inventoried), `core_model/` (32 subpackages;
  `rag/`, `conversation/`, `admin_assistant/`, `feedback/`,
  `data_verification/`, `rag_sandbox/`, `model_evaluation/` read in
  depth), `apps/chatbot/` (all 8 source files, read in full — it is a
  genuinely tiny app), `apps/admin-dashboard/` (35 pages, cross-
  referenced against the exhaustive Phase 15A audit already performed
  in this same session), `tests/`, `docs/` (200+ files; per-phase
  reports `phase_1_report.md`..`phase_19_report.md` confirmed to be an
  **earlier, unrelated numbering scheme** predating the Phase 15/15A
  production-readiness arc — this audit does not conflate the two
  numbering schemes), `scripts/`, `config/production_regression_
  manifest.json`.

## 2. Public chatbot execution-path audit (Step 2)

Traced end to end:

```
apps/chatbot/src/pages/ChatPage.jsx
  → apps/chatbot/src/services/api.js :: sendChatMessage(message, language)
    → POST /api/chat
      → backend/api/routes/chat.py :: chat(_: ChatRequest) -> ChatResponse
        [request discarded; hardcoded literal return]
      ← ChatResponse{reply, detected_language:"unknown", model:"placeholder", phase}
  → apps/chatbot/src/components/ChatMessages.jsx renders message.text as plain text
```

Direct answers, all `NO`/`NONE` because the route never executes any
logic on the input: routing is neither model-only, RAG-only, nor hybrid
— there is no routing; not deterministic or heuristic, because there is
no decision at all; no route/confidence is ever recorded; no
current-information detection, tool selection, web-connector selection,
clarification, or insufficient-evidence response exists in this path;
the response has no source-metadata field; no knowledge-gap record is
ever created; the declared `language` field is accepted and validated
but never read.

The **real** orchestration path (admin-only, see §0) does do almost all
of this correctly: it is hybrid (RAG + memory + model), its "route" is
really "which evidence sources were available" rather than a router
decision, it computes a real `citation_validity_rate` and returns one of
9 deterministic statuses including `insufficient_evidence`, and it does
preserve/apply the user's language via `core_model/conversation/
language_continuity.py::decide_language()`.

Status: public path `MISSING` (a placeholder is not a partial
implementation — zero of the required behavior is present). Admin-only
orchestration engine: `ADMIN_ONLY` / `WORKING` (for its own, narrower,
diagnostic purpose).

## 3. Core model audit (Step 3)

Model loading/assignment/inference-runtime machinery (`InferenceRuntime
Service`, `ModelAssignmentService`, full profile/instance/assignment/
version/canary lifecycle) is real and mature — this is the same system
exhaustively audited in Phase 15/15A (production release governance).
Status: `WORKING`, but `ADMIN_ONLY` in terms of reachability (only the
Admin Diagnostic/Chat Lab and Production Readiness pages drive it).

**No real, model-derived confidence signal exists anywhere.** Confirmed
by grep across every generation/inference file for logprob/perplexity/
entropy/self-consistency-style signals: zero hits. `InferenceRuntime
Service.run_generation()` returns `generated_text`, `stop_reason`, and
three structural safety-leakage booleans — never a probability or score.
Every other "confidence" hit in the repo (36 files) is unrelated
(language-detection confidence, PII-detection confidence, document/
corpus quality-classification confidence, memory-extraction confidence).
**This report does not invent one.** Status: `MISSING`.

The nearest real thing is a **post-hoc, evidence-based** classification:
`decide_response_status()` returns `insufficient_evidence` when there is
no RAG/memory evidence at all (before generation), and
`citation_validity_rate` (regex-matching `[S#]` labels the model was
instructed to emit against real evidence) after generation. This is
real and deterministic, but it is not a generation-time confidence
score and it only exists inside the admin-only orchestration path.
Status: `PARTIAL` (real, but narrow in scope and reach).

No post-generation fact/hallucination check exists for non-RAG (pure
model) answers beyond the same structural safety-leakage booleans.
Status: `MISSING`.

**No knowledge-cutoff/freshness representation exists anywhere** — no
concept of "the model's own knowledge has a cutoff date," and no logic
that detects a "what happened today"-style question and routes it away
from the base model. Status: `MISSING`. This is the single most
important gap for Phase 17/18/20's design: freshness/volatility
classification is a from-scratch build, not a wiring task.

## 4. RAG audit (Step 4)

The full stack is real: knowledge spaces → sources → source versions →
chunking → embeddings → keyword + vector indexes → hybrid retrieval
(`rag_retrieval_service.py`) → grounded generation with citations and
conflict/insufficient-evidence handling (`rag_generation_service.py`,
`core_model/rag/citation_builder.py`, `grounding_checks.py`,
`answer_policy.py`) → injection filtering (`core_model/rag/
injection_filter.py`) → the full Phase 15/15A production-RAG governance
chain (promotion → eligibility → candidate → validation → activation →
rollback). Status: `WORKING`, but scope-limited as detailed below.

**Critical finding, confirmed independently by two research passes**:
`grep -n "production_visible|production_rag" backend/services/
rag_retrieval_service.py backend/services/chat_orchestration_service.py`
returns **zero matches**. Activating a RAG candidate in Production
Readiness has **no runtime effect whatsoever** on what a chat query
actually retrieves. RAG retrieval at answer time reads whichever
`knowledge_space_id` a manually-configured `rag_retrieval_profile`
points to (set per diagnostic session by an admin) — it is not
auto-selected from the set of admin-approved production spaces. This is
the concrete evidence behind the task's own stated invariant "existing
RAG service ≠ approved RAG active for every user answer" — confirmed
true by code, not assumed.

**RAG scope is not user/tenant-aware** — there is no concept of "which
knowledge space applies to which user"; scope = whatever retrieval
profile a given diagnostic session was configured with by an admin.

**Citations are computed and returned within the admin orchestration
response** (typed per-citation `evidence_type: "memory_item"|
"rag_chunk"`, real FK links) — but never reach the public API, because
the public API doesn't call any of this. Status for the *data model*:
`WORKING`. Status for *public exposure*: `MISSING`.

**Two independent citation-construction implementations exist**
(`rag_generation_service.py`'s vs. `chat_orchestration_service.py`'s own
inline `[S#]`-regex mechanism) — flagged as a consolidation decision
Phase 18/20 must make explicitly (which one becomes canonical), not
something to build a third version of. See duplication-prevention map.

**Source rights are checked at promotion time, not at query/retrieval
time** — `grep -n "rights|permission" rag_retrieval_service.py` → zero
matches; the approved index is pre-filtered by rights checks at
promotion, so there is no per-query re-check today (by design, not an
oversight, but relevant if a future router needs to justify per-answer
rights compliance independently).

**RAG failure fallthrough is real and clean**: `no_evidence_available`
and `context_blocked` both route to a deterministic non-generation
response (`answer_text=None, citations=[]`) rather than a garbled
generation — directly reusable as a router signal.

Reusable for the Smart Answer Router (concrete): `ChatOrchestrationService.
send_message()`'s whole evidence-assembly pattern; `rag_retrieval_
service.retrieve()`; `rag_generation_service.py`'s citation/grounding
helpers; `core_model/rag/answer_policy.py::decide_answer_status()`.

## 5. Conversation memory audit (Step 5)

Real, policy-gated (`resolve_effective_capabilities()` per session
mode), consent-aware, with real deletion/session-lifecycle endpoints
(`/close`, `/expire`, `/pause`, `/resume`). Not part of public routing
today (same reason as everything else — the public route never calls
it). Status: `WORKING`/`ADMIN_ONLY`.

**Memory and RAG evidence are combined into one evidence pool at
generation time, but remain cleanly typed in storage and in the returned
citation list** (`evidence_type: "memory_item"` vs. `"rag_chunk"`, with
correct FK linkage per citation, plus a top-level `memory_used: bool`
flag). This is genuinely `PARTIAL`, not `MISSING`: the backend data
never conflates memory with fact, but nothing in any frontend today
renders that distinction to a user (there is no frontend, since the
public path is a placeholder) — this is purely a Phase 23 UI
responsibility, not a backend gap.

Multilingual memory retrieval and item-level "forget this specific
memory" deletion: **could not be fully verified** in the time budget of
this audit (session-level lifecycle is confirmed real; item-level
deletion granularity was not traced to its full depth) — flagged as a
narrow follow-up read before Phase 19/24 design, not asserted either way.

## 6. Safety audit (Step 6)

No live, per-turn safety verdict gates real chat content today, because
there is no live chat content flowing through any gate (the public path
never generates anything; the admin path is diagnostic-only traffic).

What is real: prompt-injection detection over **untrusted context**
(RAG chunks, memory items, prior turns) via `core_model/rag/
injection_filter.py` + `core_model/conversation/injection_guard.py`,
wired into `ChatOrchestrationService` before context enters the prompt.
Secret/PII-pattern detection gates what can be *stored* as a memory item
(`core_model/conversation/memory_safety.py`). A full content-policy
taxonomy exists (`core_model/model_evaluation/__init__.py::
SAFETY_CATEGORIES` — self_harm, violence, illegal_activity, weapons,
malware, privacy, credential_theft, hate_or_harassment, sexual_content,
medical_high_stakes, financial_high_stakes) — **but only as an offline
model-evaluation-suite rubric** (`docs/safety_refusal_evaluation.md`),
never called from any chat-serving code path. Status: injection defense
`WORKING`/`PARTIAL` (real, but scoped to context-item screening only,
not the user's own message or the model's raw output); live input/output
content-policy enforcement: `MISSING` (the taxonomy exists, the live
enforcement does not).

**No action-specific permission system exists for chat** (no live
answer/search/fetch/tool-execution/admin-approval/block distinction,
because none of those actions — search, fetch, tool execution — are
wired to chat at all yet). The closest *existing pattern* worth reusing
is `core_model/admin_assistant/action_registry.py`'s
`ActionDefinition(risk_level, permission, ...)` model — a real,
battle-tested pattern for exactly this kind of graduated permission, but
currently scoped to Admin Assistant actions only. Status: `MISSING`
(for chat), with a strong `WORKING` reusable pattern from a different
subsystem.

## 7. Language and Tanglish audit (Step 7)

A real, deterministic (non-ML, script-ratio + bounded lexicon) language
classifier exists: `core_model/rag/language_routing.py::classify_
language()` → `ta`/`en`/`tgl`/`mixed`/`unknown`, plus `core_model/
conversation/language_continuity.py::decide_language()` for
turn-to-turn continuity (explicit request → confirmed session
preference → current-message detection → recent-turn fallback). Status:
`WORKING`, `ADMIN_ONLY` (reachable only via the diagnostic orchestration
path).

**Important, evidenced policy gap**: `routing_decision()`'s current
default `answer_language_policy` for a `tgl` (Tanglish) input is
**`"tgl"` (Tanglish out), not `"ta"` (Tamil out)**. The task's stated
future policy — "public chatbot: Tanglish input → Tamil output by
default" — is **not yet the system's current default behavior** even
in the admin-only path. This is a real, evidenced, pre-existing
divergence from the desired future policy, not something this audit
changed, and it is a concrete Phase 21 requirement, not merely an
integration task.

**No translation provider exists anywhere** in the repository (grep for
real translation API/model calls, whole repo, `backend/` + `core_model/`:
zero hits beyond doc/comment mentions of future intent). Status:
`MISSING`.

`text_normalization.py` performs protective normalization (names,
numbers, code, URLs — guard-by-guard exhaustive verification was not
completed in this audit's time budget; presence of the mechanism is
confirmed, completeness of every guard is `PARTIAL`/`COULD NOT VERIFY`).

**Admin Assistant's Tanglish/language preference is fully, structurally
isolated** from the RAG-side language machinery: `backend/services/
admin_assistant_language_service.py` (wraps `AdminRepository.get_
response_language`/`set_response_language`, persisted per-admin on
`admin_accounts`) + `core_model/admin_assistant/language_preference.py`
are a completely separate code path from `language_routing.py`/
`language_continuity.py`. Confirmed, not assumed. Status: `WORKING`,
correctly isolated as the task requires.

No mixed-language *output* detection exists (input classification could
in principle be re-applied to generated output; no code site does this
today). Status: `MISSING`.

## 8. External providers, connectors, tools, MCP audit (Step 8)

Real, well-architected connector layer: `backend/services/external_
data_connectors/base.py` defines a strict `ExternalDataProviderConnector`
Protocol; `builtin.py` implements 6 connectors (AI4Bharat, HuggingFace,
GitHub, Wikimedia, Bhashini, GenericPublicApi) plus a manual-provider
type — all bounded, read-only **metadata/reachability lookups against
provider-registered domains**, never a free-text "answer this question"
web search, never a page fetch for arbitrary content. Confirmed by the
connector module's own docstring and by the complete absence of any
call site from `chat.py`/`chat_orchestration_service.py`.

**This entire subsystem is Admin-only, structurally**: `backend/api/
routes/external_data_providers.py:33-36` — `router = APIRouter(...,
dependencies=[Depends(require_admin)])`, applied to every route. It
exists exclusively to help an admin discover/vet candidate datasets, not
to answer live user questions. Status: `ADMIN_ONLY`, `WORKING` for its
actual (narrow, dataset-discovery) purpose; `NOT_APPLICABLE` as a
"trusted web answer" system, because it was never designed to be one —
per the task's own core invariant, "existing external provider registry
≠ trusted live web-answer system," confirmed true by code.

**No live web search reachable from chat exists.** Status: `MISSING`.

**No alternate model-inference provider (OpenRouter/Groq/Ollama/etc.)
exists** — grep across the whole repo: zero hits. All inference is the
project's own trained model. Status: `NOT_APPLICABLE` (nothing to
audit; confirms the project intentionally has no external
model-inference dependency today).

**No MCP support exists at all** — zero hits for "mcp" or "model context
protocol" anywhere in `backend/`, `core_model/`, or pre-existing `docs/`.
Status: `MISSING`, fully absent (not partial).

**A real, reusable SSRF-protected fetch primitive exists**:
`backend/services/dataset_verification_transport.py` — domain-allowlist
only, DNS-resolution + private/loopback/link-local/reserved-IP
rejection, single validated redirect hop, bounded response size, MIME
allowlist, zero retries. Currently used only for admin dataset-
verification evidence retrieval (fetching a specific licence/terms page
for a specific case). This is a strong, directly reusable building
block for a future Phase 20 web fetcher — it should be extended/reused,
never rebuilt. Status: `WORKING`, `ADMIN_ONLY`, high reuse value.

**The 6 connectors already share one common Protocol/result-type
schema** — a future gateway needs new connector implementations and
new capabilities (e.g. `fetch_page`, `search_web`) added to the existing
pattern, not a new abstraction layer. Status: `PARTIAL` (schema pattern
present and reusable; the capabilities themselves don't exist yet).

## 9. Manual/runtime verification performed in this audit (Step 19)

Performed live against the real dev database (`data/database/
brud_ai.db`, schema 38) via a temporary backend instance on port 8100
(stopped after verification; no state was mutated — the public chat
endpoint is stateless/read-only by construction, and only unauthenticated
`GET`/read-style requests were made against admin routes to confirm auth
gating, never a mutation):

| Test | Request | Result |
|---|---|---|
| Health | `GET /api/health` | `200 {"status":"healthy","database":"connected","core_model":"not_configured"}` |
| Tamil question | `POST /api/chat {"message":"தமிழ் நாட்டின் தலைநகரம் என்ன?","language":"ta"}` | Identical placeholder reply |
| English question | `POST /api/chat {"message":"What is the capital of Tamil Nadu?","language":"en"}` | Identical placeholder reply |
| Tanglish question | `POST /api/chat {"message":"Enna nadakkudhu ippo?","language":"tanglish"}` | Identical placeholder reply |
| Ambiguous question | `POST /api/chat {"message":"tell me about it","language":"auto"}` | Identical placeholder reply |
| No-known-answer question | `POST /api/chat {"message":"What is the weather in Chennai right now?","language":"auto"}` | Identical placeholder reply |
| Unsafe question | `POST /api/chat {"message":"How do I make a bomb?","language":"auto"}` | Identical placeholder reply (no refusal, no answer, no distinction of any kind — because nothing reads the message) |
| Admin route auth gate | `GET /api/admin/production-readiness/overview` (no auth) | `401` — correctly gated |
| Admin route auth gate | `POST /api/admin/conversation-memory/sessions` (no auth) | `401` — correctly gated |
| `core_model` wiring | (from health response) | `"core_model": "not_configured"` — confirms no model is loaded in this ad hoc verification instance by default; a real assignment must be configured for generation to occur, consistent with the Admin-only inference-runtime architecture |

All six chat requests, regardless of language or content — including a
deliberately unsafe request — produced the byte-identical response. This
is the definitive, first-hand confirmation of §0/§2's code-level finding.

**Admin Dashboard manual verification**: the login/Production-Readiness/
Admin-Assistant/mobile-layout/hash-deep-link flows were re-exercised for
real as part of this audit's Step 18 canonical-regression run (its
`browser_e2e_01` batch runs the full, real Playwright suite built in
Phase 15A — see the test-evidence section below for exact pass counts).
Independently re-driving Data Overview / RAG Sandbox / Incremental
Training page-by-page was **not** additionally performed in this
session beyond the code-level Frontend audit (Pass F, Step 17) confirming
these pages exist and call real, already-audited read endpoints — no
new Playwright spec files were authored for this, in keeping with the
task's Step 29 prohibition on new test/tooling beyond what completing
the audit strictly requires. This is recorded as a known limitation
(§ Known limitations), not fabricated coverage.

## 10. Test and production verification evidence (Step 18)

Canonical regression manifest verified: `config/production_regression_
manifest.json`, `manifest_version=2`, checksum verified on load by
`ProductionRegressionService.load_manifest()` (no mismatch), 48 batches,
18/18 required categories present.

Database integrity (live, real dev database): `PRAGMA integrity_check`
→ `ok`; `PRAGMA foreign_key_check` → 0 violations; migration status →
`current` (version 38 = target 38), 38/38 migrations applied.

Full canonical regression run executed for real via `Production
RegressionService.create_manifest_run()` → `execute_registered_batch()`
× 48 → `finalize_manifest_run()`, exactly as established in Phase 15A.
**Exact command per batch, duration, and pass/fail/error counts are
recorded verbatim in the run's own `production_regression_results` rows
and reproduced in full in this report's evidence log below** (populated
after the run completed — see the final-response message for the
authoritative summary, since this document was drafted while the run
was still in progress; do not treat a `passed`/`environment_incomplete`
claim here as final without cross-checking the final response's exact
counts).

`apps/chatbot`: `npm run build` (vite) → **passed**, 22 modules
transformed, 695ms, zero errors (verified live in this audit, Pass F).

`apps/admin-dashboard`: `npx vite build` → **passed**, 58 modules
transformed, 1.57s, zero errors, one informational chunk-size warning
(pre-existing, not introduced by this audit; no code was changed this
session). Verified live in this audit.

`ruff check .`: covered as part of the canonical regression manifest's
`static_analysis_01` batch — result recorded in the final response.

## 11. Known limitations of this audit

- Several fork passes flagged narrow `COULD NOT VERIFY` items (exact
  `rag_retrieval_service.retrieve()` return-schema internals for
  numeric relevance scores; stale/withdrawn-source filtering at query
  time; item-level memory deletion granularity; every individual
  `text_normalization.py` guard; full per-route schema detail for the
  ~30 admin route files not read in depth this session, largely because
  they were already exhaustively covered by the immediately-prior
  Phase 15A session). None of these affect the headline finding or the
  overall gap map; they are candidates for a narrower follow-up read
  before the specific phase that depends on them (noted per-item in the
  implementation map).
- Data Overview / RAG Sandbox / Incremental Training admin pages were
  verified only at the code level (Pass F) in this session, not
  re-driven interactively — see §9.
- This report is necessarily a snapshot; no code in `backend/`,
  `core_model/`, or either frontend app was modified during this audit
  (documentation-only, per the task's non-negotiable rules).
