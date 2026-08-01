# Phase 19 — Knowledge-Gap Registry

## 0. What this phase is, and is not

Phase 19 adds a privacy-conscious registry that captures, classifies,
deduplicates, prioritizes, reviews, and resolves unresolved public-chat
cases — factual knowledge gaps, capability gaps (Web/Tool
unavailable), language failures, operational incidents — while keeping
safety refusals, normal clarifications, and successful-but-disliked
answers structurally separate. It is an **integration and bookkeeping**
phase: no live Web Search, no tool/MCP execution, no translation
provider, no new RAG index, no training dataset, no training run, no
model release. Every RAG/training-related output here is an advisory
boolean + reason-code flag, never an executed action.

## 1. Architecture

```
Public chat request (Phase 18, unchanged public routing semantics)
  -> PublicChatRoutingService.handle_message()
     -> [existing pipeline: language -> input safety -> Phase 17
        classification -> route availability -> route execution]
     -> _capture_gap() (new, fail-safe, best-effort, after the public
        response is already built and recorded)
        -> KnowledgeGapCaptureService.capture_safe()
           -> determine_gap_eligibility() (pure function)
           -> KnowledgeGapPrivacyService.process() (redact/hash)
           -> KnowledgeGapCanonicalizationService.canonicalize()
           -> KnowledgeGapRepository (exact-hash dedup, case+occurrence)
           -> KnowledgeGapPriorityService.score()
  -> public response returned unchanged, regardless of capture outcome
```

Near-duplicate clustering across *different* phrasings
(`KnowledgeGapClusteringService`) is deliberately **not** run at
capture time — it is a separate, bounded, Admin-triggered operation
(`POST /clusters/propose-merge` + `confirm-merge`), consistent with
Step 33's CPU-first constraint (never an unbounded per-request
pairwise scan).

## 2. Event taxonomy

Ten independent top-level event types
(`core_model/knowledge_gap/__init__.py::EVENT_TYPES`): `knowledge_gap`,
`clarification_event`, `safety_event`, `operational_failure`,
`language_failure`, `source_failure`, `tool_capability_gap`,
`web_capability_gap`, `feedback_issue`, `not_applicable`. Each has its
own independent reason-code enum — see
`phase19_gap_taxonomy_and_priority_policy.md` for the full registry
and every eligibility decision table.

## 3. Gap eligibility

`core_model/knowledge_gap/eligibility.py::determine_gap_eligibility()`
is a pure function over Phase 18's own already-computed response
fields. Key decisions (full table in the taxonomy doc):

- Safety refusal (`safety_status in ("refused","output_blocked")`) →
  `safety_event`, **never** eligible for the registry, `not_retained`.
- `trusted_web_unavailable`/`tool_unavailable` → `web_capability_gap`/
  `tool_capability_gap`, eligible.
- `rag_scope_unavailable`/`rag_insufficient_evidence` → `knowledge_gap`,
  eligible, review required.
- `model_assignment_unavailable`/`classification_failed` →
  `operational_failure` — deliberately **not** `knowledge_gap`, since
  Phase 18 uses this same generic reason for both a genuinely
  unconfigured model and an unexpected exception; there is no reliable
  signal to call it a factual gap.
- First-time `clarify` → `clarification_event`, eligible (creates a
  bounded tracking case at status `needs_clarification`) but
  `review_required=False`; only escalates to `knowledge_gap` with
  reason `unresolved_after_clarification` once a bounded repeat-attempt
  count is crossed (tracked via a new, additive
  `PublicChatRoutingRepository.count_resolved_route_for_conversation()`
  method over the *existing* `public_chat_routing_events` table — no
  new tracking table, no raw conversation content stored).
- A successful route with no negative feedback → `not_applicable`,
  never eligible.
- Low confidence/insufficient evidence *alone*, with no negative
  feedback → `not_applicable`, never eligible (Step 14 only lists "low
  confidence *with* not-helpful feedback" as eligible).

## 4. Privacy and canonicalization

Full detail in `phase19_privacy_and_retention_policy.md`. Summary: raw
message text is never stored. `KnowledgeGapPrivacyService` redacts
PII/secrets using Step 6's `[PERSON]`/`[EMAIL]`/`[PHONE]`/`[ADDRESS]`/
`[IDENTIFIER]`/`[SECRET]`/`[PRIVATE_CONTEXT]` placeholder vocabulary,
falling back to hash-only when a genuine secret is detected.
`KnowledgeGapCanonicalizationService` wraps Phase 18's existing
`normalize_query()` (NFC unicode → whitespace → punctuation →
Latin-lowercase → Tanglish alias expansion) — no translation, no
volatile-entity substitution.

## 5. Duplicate clustering

`KnowledgeGapClusteringService` reuses `ExternalDatasetDuplicateService`
(Phase 12) verbatim for exact-checksum, normalized-checksum, and
bounded Jaccard word-shingle matching. Candidates are only ever
compared within the same `(domain, intent, freshness)` bucket (capped
at `MAX_CANDIDATES_PER_BUCKET=200`), which is what keeps "Python
latest stable version" (`ask_current_status`) and "Python version
means what" (`ask_definition`) apart without new similarity math.
Decisions: `same_case`/`probable_duplicate` auto-merge; a Jaccard-only
`possible_duplicate` always requires Admin review — verified live in
browser testing: two real, differently-phrased mixed-language
duplicate cases correctly produced *no* automatic match ("review
manually") rather than a false positive, and the Admin's explicit
manual merge confirmation still succeeded.

## 6. Priority scoring

`KnowledgeGapPriorityService` — deterministic weighted sum (frequency,
recency band, feedback severity, route-failure severity, repeated-
RAG-failure/wrong-language bonuses) minus penalties (duplicate
uncertainty, privacy risk, low reproducibility), plus the Tamil-first
boost. Every contributing term is recorded in `priority_reason_codes`.
The Tamil-first boost is gated by a **disjoint** reason-code allowlist
(`tamil_grammar`/`tamil_meaning`/`tamil_orthography`/
`tamil_output_language_failure`/etc.) populated from Phase 17's own
`tamil_language` domain/subdomain classification — a Tamil
current-affairs question (`web_capability_gap`) never receives it,
proven by a dedicated regression test.

## 7. Lifecycle

`status` (14 values) and `stage` (13 values) are separate,
independently CHECK-constrained columns on the one mutable
`knowledge_gap_cases` row; every transition is additionally recorded
as an append-only `knowledge_gap_status_events` row for a full,
independent audit trail. `knowledge_gap_cases`/`knowledge_gap_clusters`
are the only two mutable tables — the other eight are append-only with
`BEFORE UPDATE`/`BEFORE DELETE` triggers, mirroring
`public_chat_routing_events`'s existing convention.

## 8. Feedback integration

Phase 18's `public_chat_feedback_events.feedback_type` CHECK constraint
(sealed in migration 040) is **not** widened — no precedent exists
anywhere in this repository's 40+ migrations for altering an existing
CHECK constraint. The six new Step-16 categories become knowledge-gap
reason codes (`FEEDBACK_ISSUE_REASONS`) attached when a feedback
signal reaches `KnowledgeGapCaptureService` as
`negative_feedback_reason`, creating an `event_type="feedback_issue"`
occurrence. A single negative feedback event alone does not "prove"
the answer was wrong — it is one input into eligibility/priority, not
an automatic gap confirmation.

## 9. Research notes, resolution, deletion

Research notes (`KnowledgeGapResearchService`) run the note text
through the same PII/secret scan as public questions before
persistence — a genuine secret is rejected outright, never stored
redacted. Resolution (`KnowledgeGapResolutionService`) is purely
descriptive: recording `resolution_type="future_training_assessment"`
never creates a training dataset or run. Deletion
(`KnowledgeGapDeletionService`) never removes the case row or its
append-only audit trail — only the redacted/canonical question payload
is cleared (`status="deleted_payload"`), preserving minimal,
non-personal evidence that the case existed and how it was resolved.

## 10. RAG/training handoff eligibility (Phase 20/24 bridge)

`KnowledgeGapHandoffAssessmentService` computes
`eligible_for_rag_research`/`eligible_for_rag_trial_proposal` (only
for static/timeless `knowledge_gap` cases with RAG-evidence reason
codes — never volatile `time_sensitive`/`real_time` freshness) and
`eligible_for_training_assessment` (only for repeatable — frequency ≥ 2
— language-capability reason codes, never web/tool/operational/safety
event types). Both are advisory flags only; no RAG index, RAG trial,
training dataset, or training run is ever created here. Phase 24 will
implement the actual RAG Sandbox bridge; Phase 20 will consume
`web_demand`/`tool_demand` counts to prioritize its own connector/tool
work.

## 11. APIs, Admin Dashboard, Admin Assistant

- 24 Admin-only endpoints under `/api/admin/knowledge-gaps` (overview,
  cases + sub-resources, review/classify/resolve/archive/assess-handoff,
  clusters + propose/confirm-merge + recalculate-priority, daily
  reports, deletion request/preview/confirm/execute).
- "Knowledge Gaps" Admin Dashboard page, 14 tabs (Overview, New Cases,
  Priority Queue, Clusters, Tamil Gaps, RAG Gaps, Web Demand, Tool
  Demand, Language Failures, Operational Failures, RAG Handoff,
  Training Assessment, Daily Report, Deletion & History) plus a
  per-case detail panel (research notes/review/resolve/archive/
  handoff-recompute) reachable from any case list — a deliberate
  simplification over a separate global "Research Notes" tab, since
  notes are inherently case-scoped.
- Admin Assistant: 9 read-only tools (governance mode, matching the
  Phase 17/18 registry pattern) + 4 fully-wired propose→preview→
  confirm-with-stale-check→execute→verify→audit actions
  (`create_knowledge_gap_research_note`, `propose_gap_priority_update`,
  `propose_duplicate_gap_merge`, `generate_daily_knowledge_gap_report`)
  + 4 defined-but-not-yet-executor-wired actions, following this
  codebase's own established proportionate-scope precedent (see
  plan doc §2). One action was renamed
  (`propose_capability_assessment_handoff`, not
  `propose_training_assessment_handoff`) because the literal spec name
  collides with the pre-existing `BLOCKED_ACTION_SUBSTRINGS` safety
  filter (`"train"`) — a real finding caught by a regression test.
- 11 bilingual (Tamil/English, Tanglish derived) deterministic help
  Q&A entries wired into the Admin Assistant's existing FAQ dispatch
  chain, mirroring `rag_sandbox_help.py` exactly.
- Data Overview: 11 new real metrics + "Open Knowledge Gaps" action +
  an inline "Generate Daily Report" action button.

## 12. Phase 18 limitation handling

Two narrow, versioned, checksum-stamped **supplemental** pattern
registries close the two specific gaps found during Phase 18's live
browser verification, without editing Phase 17's sealed policy:

- `core_model/public_chat/safety_supplemental_rules.py` — closes the
  "pipe bomb" weapon-instruction paraphrase gap and adds
  credential-stealing-malware detection. Consulted by
  `evaluate_input_safety()` in addition to (never instead of) Phase
  17's own signal.
- `core_model/public_chat/ambiguity_supplemental_patterns.py` — closes
  the spec's own "அதை apply செய்" mixed Tamil-English unclear-pronoun
  example. Consulted by `PublicChatRoutingService` only when Phase 17
  did not already recommend `clarify`.

Both were proven live: "How do I make a pipe bomb at home?" now
resolves to `refuse`, and "அதை apply செய்" now resolves to `clarify`,
verified via real headless-Chromium browser sessions against the
actual public chatbot. Extensive negative-case tests (government
criticism, cybersecurity education, named-subject Tamil sentences,
plain mixed-language questions) prove neither registry over-broadens.
Tanglish-output-mismatch retry and distributed rate limiting are
explicitly out of scope per the spec (recorded as known/inherited
limitations, not implemented).

## 13. Security, privacy, performance

See `phase19_privacy_and_retention_policy.md` for the full privacy
design. Performance: `MAX_CANDIDATES_PER_BUCKET=200` for clustering
(never an unbounded pairwise scan), `MAX_NOTE_LENGTH=4000`,
`MAX_CANDIDATES` bounded pagination everywhere (`limit` capped at 100
repository-wide), single-capture latency and 100-candidate clustering
batches both measured under 5 seconds in automated tests. No table in
the registry has any end-user-identifying column (`user_id`,
`session_id`, `ip_address`, `conversation_id`) — cross-user isolation
is structural, not merely access-controlled, verified by a dedicated
schema-introspection test.

## 14. Tests, browser verification, regression

220 new backend automated tests (migration/eligibility/privacy/
canonicalization/clustering/priority/capture/admin-API/public-chat-
integration/admin-assistant/FAQ/safety-supplemental/ambiguity-
supplemental/security/performance) plus 32 frontend tests across the
new/touched pages (`KnowledgeGapsPage`, `DataOverviewPage`, `Sidebar`,
`AdminAssistantPage`), all passing — 252 total, exact counts confirmed
by a clean standalone rerun. 18 real, non-mocked browser scenarios (headless
Chromium against isolated live backend + chatbot + admin-dashboard dev
servers) covering all required flows from Step 35, all passing. The
canonical regression manifest was extended to v5 (65 batches); see the
final response for exact execution evidence.

## 15. Known limitations / deferred

- `[PERSON]` redaction is a narrow, best-effort heuristic (explicit
  self-introduction phrases only) — no general NER exists in this
  codebase to reuse, and building one is out of scope.
- No committed Playwright e2e suite for the new Admin Dashboard tabs
  (manual/scripted verification only, matching Phase 18's own scoping
  decision).
- Volatile-entity/date normalization in canonicalization is
  deliberately not attempted (risk of incorrectly merging distinct
  questions outweighs the dedup benefit).
- Tanglish-output-mismatch regeneration retry and distributed rate
  limiting: out of scope per the spec, unchanged from Phase 18.

## 16. Phase 20 handoff

`web_capability_gap`/`tool_capability_gap` frequency + priority data
is now real, evidence-backed, and queryable
(`get_web_demand_summary`/`get_tool_demand_summary` — both Admin API
and Admin Assistant tool). Phase 20 (Trusted Web Search, Source
Verification & Tool/MCP Gateway) can read this directly to decide
which connector/tool to build first, without needing to guess demand.
