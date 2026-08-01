# Phase 19 — Knowledge-Gap Registry: Plan

## 0. Baseline (confirmed by direct inspection)

Schema version 40. `POST /api/chat` is Phase 18's real public Smart
Answer Router (`PublicChatRoutingService`), resolving every request to
exactly one of `core_model|approved_rag|memory|clarify|refuse|
insufficient`; `trusted_web`/`tool` are recognized-but-unavailable.
`public_chat_routing_events`/`public_chat_feedback_events` (migration
040) are append-only, store only `input_hash` + structured fields,
never raw text. Two known Phase 17 classifier-lexicon gaps exist
(weapon-phrasing, mixed Tamil-English ambiguity) — addressed narrowly
in Step 31 below, not rebuilt.

## 1. Systems inspected and reused (not rebuilt)

| Need | Reused from | Why |
|---|---|---|
| Duplicate/near-duplicate grouping | `backend/services/dataset_sample_duplicate_service.py::ExternalDatasetDuplicateService` (exact-checksum, normalized-checksum, Jaccard-shingle union-find groups) | Exactly the three matching layers Step 9 asks for; already bounded/tested (Phase 12). |
| Canonical-question normalization | `core_model/rag/query_normalization.py::normalize_query()` (NFC unicode → whitespace → punctuation → Latin-only lowercase → Tanglish alias map → technical-term alias map) | Exactly Step 7's pipeline; language-aware, never translates, preserves Tamil script untouched. |
| PII detection/redaction | `core_model/corpus/pii_detection.py::detect_pii()`/`redact_pii()` (email/phone/aadhaar-like/pan-like/passport-like/precise-address/medical-record patterns) | Reused for detection; Phase 19 applies its own Step-6 placeholder vocabulary (`[EMAIL]` etc.) on top rather than the corpus module's `<X_REDACTED>` tokens, since the two registries serve different audiences (corpus ingestion vs. public-chat gap review) — a presentation-layer choice, not new detection logic. |
| Secret detection | `core_model/corpus/secret_detection.py::detect_secrets()` | Reused verbatim; this module's own documented policy is "always block, never redact-and-keep" — Phase 19 honors that: a genuine secret hit means the case falls back to hash-only (`content_unavailable_for_review`), never a `[SECRET]`-redacted-but-kept payload. |
| Propose→preview→confirm→stale-check→execute→verify→audit pipeline | `backend/services/admin_assistant_service.py` (`ACTION_EXECUTORS`/`PREVIEW_GENERATORS`/`STALE_CHECK_FINGERPRINTS`) + `core_model/admin_assistant/action_registry.py` (`ActionDefinition`, `ACTION_DEFINITIONS`) | This is the *general-purpose* Admin Assistant mutation pipeline already used across dataset/governance domains — not chat-specific. Phase 19 registers its own `action_type`s into these same registries rather than building a parallel approval system. |
| Language classification | `core_model.rag.language_routing.classify_language()` | Unchanged, reused for occurrence `language`/`domain` fields. |
| Append-only table convention | `BEFORE UPDATE`/`BEFORE DELETE` triggers `RAISE(ABORT, ...)`, exactly as `routing_classification_decisions`/`public_chat_routing_events` already do | Applied to every occurrence/review/note/resolution/status/deletion/report table. |
| Admin Assistant read-only tool registry | `backend/services/admin_assistant_tools.py::READ_ONLY_TOOLS`/`ToolDefinition`/`run_tool()` | Unchanged pattern; Phase 19 adds entries the same way Phase 17/18 did. |
| Data Overview metrics pattern | `apps/admin-dashboard/src/pages/DataOverviewPage.jsx::GROUPS`/`ACTIONS` | Unchanged pattern; Phase 19 adds one more group + two actions. |

## 2. Scope decision: Admin Assistant proposal actions

The codebase's own established, documented precedent
(`core_model/admin_assistant/action_registry.py`'s module docstring)
is explicit: *"not every example action name mentioned in the task is
wired to a real executor yet... flagged as future work rather than
wired at lower quality under time pressure."* Three of that phase's
example actions were fully wired (spanning low/moderate/high risk),
the rest left as pure metadata.

Phase 19 follows the same precedent for its 8 requested proposal
actions. **Fully wired** (propose → preview → confirm-with-stale-check
→ execute → verify → audit, end-to-end against a real service):
`create_knowledge_gap_research_note` (low risk), `propose_gap_priority_update`
(low risk), `propose_duplicate_gap_merge` (moderate risk, proves the
full stale-fingerprint pattern the way Step 23 requires), and
`generate_daily_knowledge_gap_report` (low risk, non-destructive).
**Defined in `ACTION_DEFINITIONS` but not yet executor-wired**, per the
same precedent: `propose_knowledge_gap_classification`,
`propose_gap_resolution`, `propose_rag_research_handoff`,
`propose_training_assessment_handoff` — a human can already perform
each of these directly through the Step-26 Admin API/Dashboard
endpoints (`POST /cases/{id}/classify|resolve`, and the advisory
handoff-eligibility fields are computed automatically, not something
an LLM needs to "propose"). Recorded here as a documented, deliberate
scope decision, not a silent omission.

## 3. Event taxonomy (Step 2)

Ten independent top-level event types (`core_model/knowledge_gap/__init__.py`):
`knowledge_gap`, `clarification_event`, `safety_event`,
`operational_failure`, `language_failure`, `source_failure`,
`tool_capability_gap`, `web_capability_gap`, `feedback_issue`,
`not_applicable`. Each carries its own independent `reason_codes`
enum (never merged into one generic field) — see
`phase19_gap_taxonomy_and_priority_policy.md` for the full registry.

## 4. Gap eligibility policy (Step 3)

`core_model/knowledge_gap/eligibility.py::determine_gap_eligibility()`
is a **pure function** (routing outcome + safety outcome + evidence
status + feedback signal in, `GapEligibilityResult` out). It never
touches the database or calls the model/RAG. `PublicChatRoutingService`
already computes every input this function needs (`resolved_route`,
`safety_status`, `evidence_status`, `fallbacks_attempted`,
`clarification_required`) — no new classification logic, just a
decision table over Phase 18's own existing outputs plus Phase 17's
recommended (pre-resolution) route, which distinguishes `web_capability_gap`/
`tool_capability_gap` from a plain `knowledge_gap`.

## 5. Privacy design (Step 6)

`KnowledgeGapPrivacyService.process(text) -> PrivacyResult`:

1. Run `detect_secrets()` first. Any hit → `content_unavailable_for_review=True`,
   only `input_hash` retained, no redacted text stored at all (honors
   secret_detection's own "never redact-and-keep" policy).
2. Else run `detect_pii()`. Hits are redacted using Step-6's own
   placeholder vocabulary (`[EMAIL]`, `[PHONE]`, `[ADDRESS]`,
   `[IDENTIFIER]` for aadhaar/pan/passport/medical-record patterns).
3. A narrow, best-effort `[PERSON]` heuristic matches explicit
   self-introduction phrases only (`"my name is ..."`, `"நான் ... என்பவன்/
   என்பவள்"`) — documented as best-effort, not a full NER system (none
   exists in this codebase to reuse, and building one is out of Phase
   19's scope).
4. `[PRIVATE_CONTEXT]` is applied when the occurrence's `source_types`
   included `memory` and the message contains a conversational
   back-reference pattern (`"that thing I told you"`-shaped phrases) —
   defensive, since raw memory content is never pulled into this
   pipeline in the first place (Step 8 already excludes it).
5. If any step cannot complete safely (e.g. redaction leaves an
   ambiguous residual match), fall back to hash-only.

## 6. Canonicalization (Step 7)

`KnowledgeGapCanonicalizationService.canonicalize(redacted_text,
language_category) -> CanonicalResult` wraps `normalize_query()`
directly, then adds one further deterministic step: a small, versioned
**volatile-entity placeholder map** (e.g. `"latest"`/`"stable"`/
`"current"` version-request phrasing is preserved verbatim — it is
*not* replaced with a placeholder, since replacing it would collapse
"latest Python version" and "Python version means what" into the same
canonical form, which the spec explicitly forbids). The only
placeholder substitution applied is for genuinely volatile *values*
that would otherwise fragment identical questions asked on different
days (e.g. an explicit year/date token present in the question is not
substituted either, by design — Phase 19 does not attempt date-arithmetic
normalization, since a wrong substitution risks merging distinct
questions; this is a deliberate, documented conservative choice over
building bespoke entity extraction).

## 7. Clustering (Step 9)

`KnowledgeGapClusteringService` shapes canonical-question records into
`ExternalDatasetDuplicateService`'s expected `{"public_id",
"record_checksum", "normalized_content"}` shape and calls, in order:
`group_exact_duplicates` → `group_normalized_duplicates` →
`group_near_duplicates` (Jaccard shingle, threshold 0.85, reused
verbatim). A domain/intent/freshness compatibility filter is applied
*before* the Jaccard pass (candidates are only compared within the
same `(language_category, domain, intent)` bucket) — this is what
keeps "Python latest stable version" and "Python version means what"
in separate buckets (different `intent`: `ask_current_status` vs.
`ask_definition`), satisfying the spec's own worked example without
any new similarity math. Decisions: `same_case` (exact match, always
auto), `probable_duplicate` (normalized match, always auto),
`possible_duplicate` (Jaccard match — requires Admin review per Step
9's explicit rule: *"All other merges require Admin review"*),
`distinct`, `needs_review`.

## 8. Priority scoring (Step 11-12)

`KnowledgeGapPriorityService.score(case, occurrences) ->
PriorityResult` — deterministic weighted sum over frequency, recency
(exponential recency decay bucketed into bands, not raw days-since, to
stay explainable), feedback severity, route-failure severity, a
Tamil-first capability boost (Step 12 — **only** for language/grammar/
orthography/instruction-following/ambiguity-handling reason codes,
never for Tamil current-affairs freshness reason codes, enforced by a
disjoint reason-code allowlist checked in code, with test coverage
proving the Tamil-current-affairs case does *not* receive the boost),
minus penalties (duplicate uncertainty, privacy risk, low
reproducibility). Output bands: `critical|high|medium|low|informational`,
plus `priority_reason_codes` for explainability. `TAMIL_FIRST_PRIORITY_APPLIED`
is one of those reason codes when the boost fired.

## 9. Migration 041 (Step 4)

Ten new tables, additive only, schema 40→41. `knowledge_gap_cases` and
`knowledge_gap_clusters` are the two mutable-via-service tables
(status/stage/priority columns updated through governed repository
methods only, never a raw UPDATE from an API/Admin-Assistant layer);
the other eight are append-only with `BEFORE UPDATE`/`BEFORE DELETE`
triggers, mirroring `public_chat_routing_events`'s existing convention
exactly. See `phase19_knowledge_gap_registry.md` §migration for full
column lists.

## 10. Lifecycle (Step 5)

`status` (14 values) and `stage` (13 values) are separate columns on
`knowledge_gap_cases`, each individually CHECK-constrained; every
transition goes through `KnowledgeGapReviewService`/
`KnowledgeGapResolutionService`, and every transition is additionally
recorded as an append-only row in `knowledge_gap_status_events` for a
full audit trail independent of the mutable case row's current value.

## 11. Feedback integration (Step 16)

Phase 18's `public_chat_feedback_events.feedback_type` CHECK
constraint (`thumbs_up|thumbs_down|language_report|safety_report`,
sealed in migration 040) is **not** widened. No precedent exists
anywhere in this repository's 40 migrations for altering an existing
CHECK constraint (only `ALTER TABLE ADD COLUMN` is ever used) — adding
one now would be a novel, higher-risk pattern for a codebase that has
consistently avoided it. Instead, the six new Step-16 categories
(`stale_information`, `source_conflict`, `unknown_question`,
`wrong_answer`, `missing_evidence`, plus the two with existing
near-equivalents `unsafe_answer`≈`safety_report`,
`unhelpful`≈`thumbs_down`) become **knowledge-gap reason codes**
(`FEEDBACK_ISSUE_REASONS` in the taxonomy module), attached when a
`public_chat_feedback_events` row is consumed by
`KnowledgeGapCaptureService` to create/augment an occurrence with
`event_type="feedback_issue"`. This is purely additive, needs no
migration risk against a sealed table, and is exactly where "categories"
conceptually belong per the taxonomy's own Step-2 design.

## 12. Phase 20/24 handoff

`eligible_for_rag_research`/`eligible_for_rag_trial_proposal` and
`eligible_for_training_assessment` are advisory boolean + reason-code
fields only — Phase 19 creates no RAG index, no training dataset, no
training run. Phase 24 will implement the actual bridge from an
`eligible_for_rag_research=true` case into the existing RAG Sandbox
workflow (`RagSandboxCorpusService`/etc., already governed, already
tested); Phase 20 will consume `web_capability_gap`/
`tool_capability_gap` demand (frequency + priority) to decide which
Trusted-Web connector or tool to build first — this phase's job is
only to make that demand visible and evidence-backed, never to act on
it.

## 13. Explicitly deferred within Phase 19 itself

- Full NER-based `[PERSON]` redaction (best-effort heuristic only).
- Distributed rate limiting (unrelated to gap registry; recorded as an
  inherited Phase 18 operational limitation, not addressed here).
- 4 of 8 Admin Assistant proposal actions left as defined-but-unwired,
  per the documented precedent in Section 2.
- A committed Playwright e2e suite for the new Admin Dashboard tabs
  (manual/scripted verification only, matching Phase 18's own scoping
  decision).
