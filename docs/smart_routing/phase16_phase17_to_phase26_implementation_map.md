# Phase 16 — Execution Architecture & Phase 17-26 Implementation Map

## A. Proposed future architecture (Step 23)

Evidence-backed by the audit in `phase16_existing_system_audit_and_gap_
report.md`. This is a proposed design for future phases — **nothing in
this section is implemented in Phase 16.**

```
User Question
  -> Input Normalization              [text_normalization.py — EXISTS, reuse]
  -> Language Detection               [language_routing.py::classify_language() — EXISTS, reuse]
  -> Safety Classification            [MISSING — Phase 22 must build live enforcement;
                                        SAFETY_CATEGORIES taxonomy EXISTS as a starting vocabulary]
  -> Intent Classification            [MISSING — Phase 17 must build]
  -> Knowledge Domain                 [MISSING — Phase 17 must build]
  -> Freshness / Volatility           [MISSING — Phase 17 must build]
  -> Evidence Requirement             [derived from the above three — Phase 17/18]
  -> Route Decision                   [Phase 18 — the router itself]

Possible routes (Step 23):
  core_model            -> InferenceRuntimeService + prompt construction (EXISTS, admin-only today)
  approved_rag           -> rag_retrieval_service.py + rag_generation_service.py,
                             but selecting an ADMIN-APPROVED PRODUCTION space
                             automatically (Phase 18 must build this selection logic —
                             today RAG scope is a manually-configured session profile)
  trusted_web             -> MISSING; Phase 20 builds this on
                             dataset_verification_transport.py (SSRF-safe fetch, EXISTS)
  deterministic_tool      -> MISSING; Phase 20 builds this on the
                             Admin Assistant ActionDefinition permission pattern (EXISTS)
  conversation_memory     -> memory_service.py + ChatOrchestrationService memory
                             retrieval (EXISTS, admin-only today)
  clarification            -> MISSING; Phase 18 builds a clarify-response type
  safe_refusal             -> MISSING as a live path; SAFETY_CATEGORIES taxonomy
                             + refusal-evaluation markers EXIST as a starting vocabulary
  insufficient_evidence    -> EXISTS today (core_model/rag/answer_policy.py,
                             core_model/conversation/response_policy.py) — reuse verbatim

Selected route execution
  -> Evidence normalization           [citation_builder.py / chat_orchestration_service.py's
                                        inline mechanism — EXISTS, consolidate to one (Phase 18)]
  -> Grounding / confidence policy    [answer_policy.py, response_policy.py — EXISTS, reuse]
  -> Output safety                    [MISSING — Phase 22]
  -> User-language rendering          [language_continuity.py — EXISTS; default policy for
                                        Tanglish input needs an explicit ta-output decision
                                        for the public router, Phase 17/21]
  -> Source transparency               [citation data model EXISTS (admin-only); public
                                        schema + UI MISSING — Phase 18 (schema) / 23 (UI)]
  -> Feedback                          [core_model/feedback/__init__.py — EXISTS; needs
                                        3 new categories + a public-facing affordance —
                                        Phase 19/24]
  -> Knowledge-gap classification      [MISSING — Phase 19 builds the registry;
                                        insufficient_evidence status EXISTS as the trigger]
```

**Explicitly not recommended**: running `core_model → RAG → web`
sequentially for every question. The evidence in this audit (a real
domain/freshness/intent classification is entirely absent, but the
underlying execution engines for each route are already built and fast)
supports a **single deterministic route decision up front**, per Step
23's own instruction, not a cascade. A cascade would also make the
"execution route" vs. "learning target" separation (below) incoherent,
since a cascaded answer has no single route to attribute learning to.

## B. Execution-route vs. learning-target separation (Step 24)

Two independent classifications, per the task's explicit requirement.

**Execution route** (what actually answered this specific question):
`core_model | approved_rag | trusted_web | tool | memory | clarify |
refuse | insufficient`

**Learning target** (what, if anything, this interaction should
influence going forward): `core_model | rag_only | web_preferred |
tool_required | evaluation_only | future_training_candidate |
do_not_learn | blocked`

Worked examples, matching the task's own:

| Question | execution_route | learning_target | Why (evidence-based reasoning) |
|---|---|---|---|
| Tamil grammar question | `core_model` | `core_model` | Timeless linguistic knowledge; the base model's own weights are the right long-term home. No RAG/web evidence class applies. |
| Current government scheme | `trusted_web` | `rag_only` or `do_not_learn` | Volatile, changes without notice; answering from live web evidence is correct, but baking a snapshot into model weights (training) risks a permanently wrong answer once the scheme changes — `rag_only` if the source is durable enough to become an approved knowledge-space source, `do_not_learn` if it's too ephemeral even for that. |
| Large calculation | `tool` | `tool_required` | A deterministic tool (calculator-equivalent) is correct and cheap; no learning signal is needed because the tool is always authoritative. |
| Unsafe operational request | `refuse` | `blocked` | Per Step 6/22's safety findings — this must never become a training signal of any kind, positive or negative. |
| "What's pending in RAG sandbox right now" (an Admin-only diagnostic-style question) | `memory` or `core_model` (context-dependent) | `evaluation_only` | Session-specific operational state, not a fact worth generalizing. |
| A question the system genuinely has no evidence for | `insufficient` | `future_training_candidate` (via the knowledge-gap → RAG-trial bridge, Phase 19/24) or `do_not_learn` (if it's a one-off/malformed question) | This is the exact bridge Phase 19/24 formalizes — today `insufficient_evidence` is real but ephemeral (Step 11 finding). |

This separation matters because the audit found the existing RAG Sandbox
/ training-promotion chain (Step 12) is a mature, human-gated pipeline
that must never be triggered automatically by a bare execution-route
decision — `learning_target` is the field that should feed Phase 24's
bridge into that chain, deliberately decoupled from the low-latency,
per-message `execution_route` decision.

## C. Phase 17-26 implementation map

Each phase's "Existing components reused" cites concrete audit findings;
"Missing components" states only what Phase 16 confirmed does not exist.

### Phase 17 — Knowledge Domain & Learning-Target Router

- **Objective**: build intent classification, knowledge-domain
  classification, and freshness/volatility classification — the inputs
  the Phase 18 router decision needs — plus the `learning_target`
  taxonomy itself (as a classification, not yet acted upon).
- **Existing components reused**: `language_routing.py::classify_
  language()` (as the language input to these classifiers);
  `text_normalization.py` (input normalization); the general pattern of
  `core_model/admin_assistant/intent.py`'s deterministic keyword/
  pattern-matching classification style, as a structural template (not
  its code, which is dashboard-navigation-specific).
- **Missing components**: intent classifier, domain classifier,
  freshness/volatility classifier, learning-target classifier — all four
  confirmed `MISSING` in Steps 3/6/7.
- **Likely schema impact**: none required for classification logic
  itself; a router-decision log table (see Phase 18) will store the
  classification outputs once Phase 18 exists.
- **Backend impact**: new `core_model/` classification modules
  (deterministic-first, per the project's established pattern of
  `language_routing.py` — script/keyword/rule-based, not a new ML
  model, unless a follow-up phase explicitly justifies one).
- **Frontend impact**: none.
- **Admin Assistant impact**: none required; optionally a read-only
  "explain this classification" inspection action later.
- **Security risks**: low (pure classification, no execution).
- **Required tests**: fixture-based classification-accuracy tests,
  added as a new canonical-regression-manifest batch/category.
- **Entry gate**: Phase 16 complete (this report).
- **Exit gate**: classifiers demonstrably correct against a real fixture
  set covering Tamil/English/Tanglish and known freshness-sensitive vs.
  timeless question examples; zero existing test regressed.
- **Dependencies**: none beyond Phase 16.
- **Out of scope**: any actual routing decision or route execution
  (that's Phase 18); any live safety enforcement (Phase 22).

### Phase 18 — Smart Answer Router

- **Objective**: build the route-decision layer and wire it to a new
  public chat entry point, calling into the **already-built**
  orchestration engine rather than reimplementing it.
- **Existing components reused (the majority of the work)**:
  `ChatOrchestrationService` (or an extracted, public-safe variant of
  its evidence-assembly/generation/citation/status-classification
  logic); `rag_retrieval_service.py`, `rag_generation_service.py`;
  `memory_service.py`; `core_model/rag/answer_policy.py::decide_answer_
  status()`; `core_model/conversation/response_policy.py::decide_
  response_status()`; the RAG failure→clean-fallthrough pattern (Step 4).
- **Missing components**: the router decision itself (Phase 17's
  classifiers feed it); auto-selection of an admin-approved production
  RAG space (confirmed `MISSING`, Step 4 — today it's a manual session
  config); a public, unauthenticated entry point (today's `/api/chat` is
  a placeholder — replace its body, keep the route/schema shape
  additive/compatible where reasonable, or introduce a new versioned
  route if the schema must change incompatibly); consolidation of the
  two existing citation implementations onto one canonical path (design
  decision, not new code, mostly); a router-decision log table.
- **Likely schema impact**: one new table — a structured router-
  decision log (route, learning_target, timestamp, session ref) — per
  the schema-impact map in the audit report; reuses the established
  append-only-table convention, does not touch any existing table.
- **Backend impact**: the largest phase in this list, but overwhelmingly
  integration work — wiring Phase 17's classifiers + existing engines
  into one public-facing service.
- **Frontend impact**: `apps/chatbot`'s API client/response handling
  must be updated to a real response shape (still owned narrowly by this
  phase for the minimum viable public chat; full source UI is Phase 23).
- **Admin Assistant impact**: none required for the router itself;
  optionally a read-only "inspect a router decision" action later.
- **Security risks**: **medium-high** — this is the first time
  unauthenticated traffic reaches real model/RAG/memory execution.
  Must not skip Phase 22's safety gating; recommend Phase 22's live
  input classifier exists (at least a minimal version) before or
  alongside Phase 18's public launch, not strictly after.
- **Required tests**: end-to-end router-decision fixtures (Tamil/
  English/Tanglish, freshness-sensitive, tool-shaped, unsafe), added to
  the canonical regression manifest; real Playwright coverage for the
  new public chat UI, following the exact pattern already established
  for the admin dashboard in Phase 15A.
- **Entry gate**: Phase 17 complete.
- **Exit gate**: the full 48+ N-batch canonical regression manifest
  passes; a real public chat request produces a real, non-placeholder,
  evidence-appropriate answer for each of the manual-verification
  question types already exercised in Phase 16 §9.
- **Dependencies**: Phase 17 (classifiers). Should not fully launch
  publicly before at least a minimal Phase 22 safety gate exists.
- **Out of scope**: web search, tool execution, translation, source UI,
  Tamil-first training policy (all later phases).

### Phase 19 — Unknown Question & Knowledge-Gap Registry

- **Objective**: persist `insufficient_evidence`/ambiguous/unanswerable
  interactions durably, distinctly from the ephemeral per-answer status
  that already exists.
- **Existing components reused**: `core_model/rag/answer_policy.py`'s
  `insufficient_evidence` classification as the trigger; the established
  append-only-table + `AuditLogRepository` pattern; `core_model/
  feedback/__init__.py`'s classification-category pattern as a template
  for the gap record's own categorization; consent/capability gating
  from the memory system (Step 5) as the model for how a gap record may
  reference a conversation safely.
- **Missing components**: the knowledge-gap table itself (confirmed
  absent, zero hits repo-wide); a clarification-event concept, distinct
  from a knowledge gap (Step 11's four-way classification: knowledge
  missing / ambiguous / prohibited / operational-failure — only the
  first has any home today, and only ephemerally).
- **Likely schema impact**: one new table (knowledge-gap records,
  lifecycle: open → clustered → trialed → resolved), following the
  Phase 15 `production_readiness_events`-style precedent but with real
  structured columns (not a generic JSON blob), because it needs to be
  efficiently queryable/dedupable per Step 21's "duplicate gap
  clustering" requirement.
- **Backend impact**: capture hook in the Phase 18 router (when
  `execution_route=insufficient`), a small service for CRUD + basic
  clustering, PII-safety gating on capture (reuse `memory_safety.py`'s
  pattern).
- **Frontend impact**: none required in `apps/chatbot`; an Admin
  Dashboard triage page is plausible but not required by the task's
  minimum scope — flag as optional/Phase 26 polish.
- **Admin Assistant impact**: read-only "list open knowledge gaps"
  inspection action is a natural, low-risk addition, matching the
  existing action-registry pattern exactly.
- **Security risks**: PII leakage from raw conversation content into a
  gap record — mitigate by referencing content through the same
  consent/policy gate memory already uses, never a raw copy.
- **Required tests**: capture correctness, dedup/clustering correctness,
  PII-gate enforcement.
- **Entry gate**: Phase 18 complete (needs `execution_route=
  insufficient` events to capture).
- **Exit gate**: a real "no known answer" chat interaction produces a
  real, queryable, deduplicated gap record; feedback's 3 missing
  categories (`stale information`, `source conflict`, `unknown
  question`) added as enum values.
- **Dependencies**: Phase 18.
- **Out of scope**: any automatic RAG trial or training action on a gap
  (Phase 24); clustering beyond basic deduplication.

### Phase 20 — Trusted Web & Tool/MCP Gateway

- **Objective**: build the `trusted_web` and `tool` execution routes.
- **Existing components reused**: `dataset_verification_transport.py`
  (SSRF-safe fetch — extend, do not rewrite); the 6-connector `Protocol`
  pattern in `external_data_connectors/base.py` (add new connector
  types/capabilities to the existing shape); `core_model/rag/
  injection_filter.py` + `conversation/injection_guard.py` (screen all
  fetched/tool content before it enters a prompt — mandatory, per the
  risk register); the Admin Assistant's `ActionDefinition(risk_level,
  permission)` pattern as the template for tool permission levels.
- **Missing components**: everything execution-specific — live web
  search, page fetch-and-extract for chat answers, official-domain
  filtering, freshness/reputation scoring, cross-source agreement, MCP
  support (fully absent — Step 8), a common tool-result schema for
  chat-facing use (the *dataset-discovery* schema exists but is a
  different shape/purpose).
- **Likely schema impact**: an evidence-snapshot table for live web
  answers (distinct from the heavyweight `dataset_verification_case`
  chain — see Step 9's explicit web≠RAG≠training distinction); a
  tool/MCP call log (likely reusable as-is on the generic `audit_logs`
  shape, per Pass F's finding — probably no new table needed there).
- **Backend impact**: new connector implementations, a fetch/search
  gateway service, a tool-execution service with permission gating.
- **Frontend impact**: minimal for MVP (a "searching the web…" status
  indicator is a Phase 23 polish item, not required here).
- **Admin Assistant impact**: read-only inspection of web/tool call logs
  is reasonable; no execution actions should be added here per the
  task's non-negotiable rules (no new production actions).
- **Security risks**: **high** — SSRF (mitigated by reusing the
  existing safe transport), prompt injection via fetched content
  (mitigated by reusing the existing filter — mandatory, not optional),
  malicious MCP servers (evaluate before building; may be deferred/
  scoped out if direct connectors suffice, per the task's own
  LOW/NOT_APPLICABLE severity example for "no MCP but direct connectors
  are sufficient").
- **Required tests**: SSRF-rejection fixtures, injection-fixture
  regression (extended to web/tool payloads), a decision record for
  MCP scope.
- **Entry gate**: Phase 19 complete (so gaps can trigger web lookups
  where appropriate); Phase 22's tool-permission model should exist
  alongside this phase, not strictly after (they are tightly coupled).
- **Exit gate**: a real current-events fixture question is answered via
  `trusted_web` with a real, verifiable citation; injection fixtures
  extended to web content all still classify correctly.
- **Dependencies**: Phase 18 (routing), Phase 22 (permission model,
  tightly coupled — recommend building together).
- **Out of scope**: translation (Phase 21); source UI (Phase 23).

### Phase 21 — Multilingual Translation Gateway

- **Objective**: add a real translation provider and correct the
  Tanglish-input-to-Tamil-output default policy for the public chatbot.
- **Existing components reused**: `language_routing.py::classify_
  language()`, `language_continuity.py::decide_language()`,
  `text_normalization.py`'s protective-token pattern (names/numbers/
  code/URLs/formulas — apply the same guards around whatever translation
  call is added).
- **Missing components**: the translation provider itself (fully
  absent, Step 7); the corrected default policy (`tgl→ta` for public
  chat, distinct from the admin-diagnostic path's current `tgl→tgl`
  default — this phase must not silently change the *admin* diagnostic
  tool's existing behavior, only the *public* router's policy).
- **Likely schema impact**: optional translation-result cache, low
  priority per the audit's schema-impact map.
- **Backend impact**: provider integration behind a narrow interface
  (so it can be swapped later without touching callers).
- **Frontend impact**: make `apps/chatbot`'s currently-inert language
  `<select>` meaningfully affect output (it is UI-present but backend-
  ignored today).
- **Admin Assistant impact**: none required.
- **Security risks**: mistranslation of protected tokens (mitigated by
  reusing `text_normalization.py`'s guards); cost growth (needs a
  budget/rate limit).
- **Required tests**: protected-token-survives-translation regression
  fixtures; Tanglish→Tamil default-policy fixture.
- **Entry gate**: Phase 18 complete.
- **Exit gate**: a real Tanglish input produces real Tamil output by
  default for the public router, verified by a real test; the admin
  diagnostic path's existing `tgl→tgl` behavior is unchanged (regression
  check).
- **Dependencies**: Phase 18.
- **Out of scope**: any change to Admin Assistant's isolated language
  preference system (must remain isolated, per the task's explicit
  instruction and Step 7's confirmed-isolated finding).

### Phase 22 — Safety, Search Governance & Tool Permissions

- **Objective**: build live input/output safety classification and the
  action-specific permission model (answer/search/fetch/tool/approval/
  block) that Steps 6 and 20 both found `MISSING`.
- **Existing components reused**: `SAFETY_CATEGORIES` taxonomy
  (`core_model/model_evaluation/__init__.py`) as the starting
  vocabulary; `REFUSAL_MARKERS`/`PROCEDURAL_HARM_MARKERS`/`SAFE_
  REDIRECTION_MARKERS` (`refusal_checks.py`) as reusable classification
  signal patterns; `core_model/rag/injection_filter.py` (context
  screening, extend to live input/output); the Admin Assistant's
  `ActionDefinition(risk_level, permission)` pattern as the direct
  structural template for the new action-specific chat-permission model.
- **Missing components**: everything about making the taxonomy *live*
  (today it only scores offline eval fixtures) — an input classifier, an
  output classifier, and the permission-decision layer itself.
- **Likely schema impact**: a safety-verdict log, likely reusable on the
  `audit_logs` generic shape (low schema risk).
- **Backend impact**: the classifier(s) + permission-decision service,
  invoked by the Phase 18 router before route execution and, for
  output, before rendering.
- **Frontend impact**: a refusal/redirect message rendering (minimal;
  full polish is Phase 23's concern).
- **Admin Assistant impact**: none required; the pattern is borrowed,
  not the Admin Assistant subsystem itself touched.
- **Security risks**: this phase *is* the primary mitigation for most of
  the risk register's High entries — must ship before or alongside
  Phase 20 (web/tool), not after, per the risk register.
- **Required tests**: the full category list from Step 6 (violent/
  weapons/malware/fraud/PII-extraction/drugs/self-harm/disinformation)
  plus the explicit "must still allow" list (political criticism, policy
  analysis, RTI/petition guidance, lawful protest info, defensive
  cybersecurity education) as real, both-directions regression fixtures.
- **Entry gate**: Phase 18 complete.
- **Exit gate**: the full both-directions fixture set passes; the
  action-specific permission model is demonstrably distinct from a
  single allow/block verdict (per the task's explicit requirement).
- **Dependencies**: Phase 18. Tightly coupled with Phase 20 — recommend
  parallel/joint delivery.
- **Out of scope**: MCP-specific sandboxing beyond the general tool
  permission model (covered in Phase 20's own risk evaluation).

### Phase 23 — Source Transparency UI

- **Objective**: build the frontend source/citation display the audit
  confirmed is entirely `MISSING` in `apps/chatbot` today.
- **Existing components reused**: the full citation data model already
  computed server-side (`evidence_type`, per-citation status, real FK
  links) — this phase is almost entirely frontend + a public response-
  schema extension, not new backend citation logic.
- **Missing components**: every UI element listed in Step 14 (source
  type, document/website title, publisher/domain, page/section,
  published/updated/retrieved dates, citation, source URL, verification
  status, confidence band, conflict warning) plus the memory-vs-RAG
  visual distinction (Step 5's "data is there, UI is not" finding).
- **Likely schema impact**: none beyond what Phase 18 already added to
  the public response schema.
- **Backend impact**: minor — ensure the public response schema carries
  every field this UI needs (mostly already computed internally).
- **Frontend impact**: the primary work of this phase — new components
  in `apps/chatbot/src/components/`.
- **Admin Assistant impact**: none.
- **Security risks**: low (display-only); must not leak memory content
  a user hasn't consented to surfacing (reuse the existing typed-
  citation distinction, Step 5).
- **Required tests**: component tests + real Playwright coverage,
  mirroring the exact pattern Phase 15A established for the admin
  dashboard (accessibility, mobile layout, broken-link handling).
- **Entry gate**: Phase 18 complete (needs real citations flowing).
- **Exit gate**: every field in Step 14's checklist is rendered
  correctly for a real grounded answer, verified by a real browser test.
- **Dependencies**: Phase 18.
- **Out of scope**: any new backend retrieval/citation logic.

### Phase 24 — Knowledge-Gap to Existing RAG Trial Bridge

- **Objective**: connect Phase 19's knowledge-gap registry to the
  **already-existing** RAG Sandbox trial-before-promotion workflow —
  explicitly not a new trial pipeline (Step 12's central finding).
- **Existing components reused**: the entire RAG Sandbox chain
  (`RagSandboxEligibilityService.create_experiment()` as the concrete
  entry point, through to `RagSandboxAcceptanceService.decide()`);
  `FeedbackDatasetService.create_candidate()` and `RegressionFixtureCreate`'s
  `source_feedback_event_public_ids` field as the closest existing
  feedback→pipeline bridge pattern to model this on.
- **Missing components**: the bridge itself (a gap record → sandbox-
  experiment linkage, with a traceability pointer back to the
  originating gap); attaching user-feedback metrics to a sandbox trial
  (confirmed absent, Step 12).
- **Likely schema impact**: a link field on the knowledge-gap table
  (added in Phase 19, or as a small additive migration here) pointing to
  the resulting `rag_sandbox_experiment` id; no change to any RAG
  sandbox table.
- **Backend impact**: a bridge service calling existing sandbox entry
  points; must never skip the sandbox's existing eligibility/human-
  review/acceptance gates (Step 12's non-negotiable finding).
- **Frontend impact**: optional Admin Dashboard visibility into
  gap-originated trials; not required for MVP.
- **Admin Assistant impact**: a "propose a RAG trial from this
  knowledge gap" action is a natural, correctly-scoped addition (creates
  a draft/proposal only, per the existing pattern — never auto-accepts).
- **Security risks**: low — this phase only adds a trigger into an
  already-safe, already-human-gated pipeline.
- **Required tests**: bridge-creates-a-real-sandbox-experiment test;
  gate-bypass-is-impossible test (confirm the bridge cannot skip
  eligibility/review/acceptance).
- **Entry gate**: Phase 19 complete.
- **Exit gate**: a real knowledge-gap record can be turned into a real
  RAG sandbox experiment through the existing, unmodified sandbox
  pipeline, with full traceability.
- **Dependencies**: Phase 19.
- **Out of scope**: any change to the RAG Sandbox pipeline itself;
  automatic (non-human-gated) promotion of any kind.

### Phase 25 — Tamil-First Continuous Improvement

- **Objective**: wire the already-defined `tamil_quality_regression`/
  `tanglish_regression` categories into real training-promotion gating,
  and connect re-testing of historically-failed questions after a new
  training run.
- **Existing components reused**: `core_model/feedback/__init__.py::
  REGRESSION_CATEGORIES` (already includes the Tamil/Tanglish
  categories — vocabulary exists, Step 12); `RegressionEvaluationService.
  compare_runs()`/`create_improvement_report()` (real, working
  before/after comparison engine — reuse directly, do not build a new
  one); `training_suitability_service.py` (extend its language-quality
  check, currently generic, with Tamil-specific logic).
- **Missing components**: the actual gate (today `training_suitability_
  service.py` has no Tamil-specific check); the re-test-a-specific-
  historical-question-after-training linkage (confirmed absent, Step 12).
- **Likely schema impact**: none required beyond what Phase 19's gap
  registry already provides (the "original failed questions" to re-test
  are exactly the knowledge-gap records with `learning_target=
  future_training_candidate`).
- **Backend impact**: extend `training_suitability_service.py`;
  extend/parametrize `RegressionEvaluationService` calls to include
  gap-derived fixtures automatically.
- **Frontend impact**: surfacing Tamil-quality regression results in the
  existing Feedback & Improvement admin pages (already built).
- **Admin Assistant impact**: none required beyond what already exists
  (`compile_production_readiness_report`-style reporting pattern could
  be mirrored, optionally, not required).
- **Security risks**: low — this is an additive quality gate on an
  already-human-approved training-promotion path, must remain additive
  (never silently loosens existing gates).
- **Required tests**: a synthetic Tamil-quality-regression fixture must
  correctly block promotion; a synthetic pass-through case must not be
  falsely blocked.
- **Entry gate**: Phase 24 complete (needs gap-derived training
  candidates to exist).
- **Exit gate**: a real training-promotion decision demonstrably
  considers Tamil/Tanglish regression signal, and a real historical
  knowledge-gap question is automatically re-tested against a new
  checkpoint.
- **Dependencies**: Phase 19, Phase 24.
- **Out of scope**: any change to the core training/incremental-training
  execution engines themselves (Phase 15/15A territory, untouched).

### Phase 26 — Integrated Production Acceptance

- **Objective**: extend Phase 15A's canonical regression manifest and
  production-readiness/acceptance pipeline to cover everything built in
  Phases 17-25, producing one final, integrated readiness verdict —
  exactly the same discipline Phase 15A already established for
  Text/NLP, applied now to Smart Answer Routing.
- **Existing components reused**: the entire Phase 15A apparatus —
  `ProductionRegressionService`, the manifest (add new batches/
  categories, e.g. `router`, `web_gateway`, `translation`, `safety`,
  `knowledge_gap`), `ProductionDeploymentReadinessService`,
  `ProductionReadinessReportService`, `ProductionAcceptanceReviewService`
  — all unchanged in mechanism, extended in coverage only, per the
  duplication-prevention map.
- **Missing components**: nothing new — this phase is pure integration
  of Phases 17-25's own test suites into the existing apparatus.
- **Likely schema impact**: none.
- **Backend impact**: manifest updates only.
- **Frontend impact**: none beyond what earlier phases already built.
- **Admin Assistant impact**: none.
- **Security risks**: low — this phase's entire purpose is risk
  reduction via comprehensive final verification.
- **Required tests**: the full, extended canonical regression manifest,
  run clean.
- **Entry gate**: Phases 17-25 complete.
- **Exit gate**: a final, real, evidence-backed production-readiness
  report and Admin acceptance decision for the complete Smart Answer
  Routing system, following exactly the Phase 15A pattern (real
  canonical regression run, real report compilation, real acceptance
  review — no simulation).
- **Dependencies**: Phases 17-25.
- **Out of scope**: any new feature; this phase verifies, it does not
  build.
