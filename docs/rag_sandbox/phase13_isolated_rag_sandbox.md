# Phase 13 — Isolated RAG Sandbox, Retrieval Evaluation, Grounded Answer Testing & Admin Acceptance

Baseline: `PHASE_12_COMPLETE_WITH_LIMITATIONS`, schema version 35. This document describes the
system as actually built (migration 036, schema version 36). See also
`docs/rag_sandbox/phase13_isolated_rag_sandbox_plan.md` for the pre-implementation design
rationale — this file is the as-built record and updates a few decisions the plan doc did not
yet know (record-promotion design, the append-only-records constraint, the corpus-approval
expiry fix).

## 1. Architecture

Phase 13 never rewrites or reimplements the existing Phase 16 RAG stack. It reuses the live
`RagIngestionService` / `RagRetrievalService` / `RagGenerationService` / `RagEvaluationService`
classes exactly as they exist, scoped to a **dedicated `rag_knowledge_spaces` row created per
sandbox experiment** — this is Step 7's "preferred" isolation option, chosen because Phase 16's
retrieval model already resolves exactly one active vector index and one active keyword index
per knowledge space (`RagRepository.active_vector_index_for_space` /
`active_keyword_index_for_space`), so a distinct space is *structurally* unreachable from
production retrieval without a human manually rewriting a foreign key — no code path does that.

New Phase 13 code is limited to:
- 17 governance tables (`rag_sandbox_*`) recording the experiment/approval/promotion/query-set/
  retrieval/answer/citation/evaluation/review/report/acceptance/event/deletion lifecycle;
- 11 orchestration services that call the existing Phase 16 services and record governance rows;
- Admin Assistant tools/actions, chat guidance, dashboard registry entry;
- API routes and a frontend page.

No chunking, BM25, vector scoring, hybrid ranking, citation-map construction, grounded-generation,
or injection-filtering code exists anywhere in Phase 13.

## 2. Record promotion design (as built, differs from the plan doc's per-record-source sketch)

Phase 16's retrieval model keeps exactly **one** active vector/keyword index per knowledge space.
Rather than create one `rag_knowledge_sources` row per promoted record (which would require N
separate indexes to make all of them retrievable), `RagSandboxCorpusService.prepare_corpus()`:

1. Resolves every accepted, promotion-eligible record's content (from `external_dataset_sample_
   records.normalized_content`, or from the record's `edit_derived_copy`/`redact_derived_copy`
   review's `derived_content_text` when that is the applicable decision).
2. Concatenates all eligible records into **one** combined document, each record's content under
   its own `# <sample_record_public_id>` Markdown heading.
3. Creates **one** `rag_knowledge_sources`/`rag_source_versions` row (`source_type=
   "manual_admin_content"`) via `RagIngestionService.create_source`/`create_source_version`,
   patched to `approval_status="approved"` (the sandbox experiment's own Admin approval is the
   real governance decision; this patch only wires that decision through to `assess_chunk_
   quality`'s `source_approved` gate, which would otherwise reject every chunk).
4. Chunks it with the **existing, unmodified** `core_model.rag.chunking.chunk_text()` using the
   `heading_aware` strategy — which already splits at `#`-prefixed lines. Each resulting chunk's
   `heading_path[0]` is therefore exactly the originating `rag_sandbox_records.sample_record_
   public_id`, giving free per-record chunk-boundary and provenance recovery through code that
   was never touched.
5. Inserts one append-only `rag_sandbox_records` row per promoted record, each referencing the
   *same* shared `rag_source_id`/`rag_source_version_id`.

Records that are excluded, rejected, unreviewed, or PII-blocked are never included in the
combined document — never given even a chance to appear in a chunk.

`rag_sandbox_records` is append-only at the schema level (no `UPDATE` permitted). Consequently
`rag_source_id`/`rag_source_version_id` **must** be resolved before the row is inserted — there is
no later "link it up" step. `RagSandboxCorpusService` therefore does the promotion pass in three
passes: (1) resolve eligible records and their content without writing anything, (2) build the one
combined RAG source/version, (3) insert every `rag_sandbox_records` row referencing it.

## 3. Schema (migration 036, schema version 35 → 36)

17 tables (16 recommended + `rag_sandbox_acceptances`, justified below), all under the
`rag_sandbox_*` prefix:

| Table | Kind |
|---|---|
| `rag_sandbox_experiments` | Mutable lifecycle row (18 statuses × 13 stages, never one boolean) |
| `rag_sandbox_approvals` | Mutable until `approved`, then immutable except → `expired`/`superseded` |
| `rag_sandbox_corpora` | Mutable status; `production_visible` hard-`CHECK`ed to `0` |
| `rag_sandbox_records` | Append-only |
| `rag_sandbox_indexes` | Mutable lifecycle (`building`→`validated`/`active`/`failed`/`deleted`) |
| `rag_sandbox_query_sets` | Mutable while `draft`, immutable once `finalized` (trigger-enforced) |
| `rag_sandbox_queries` | Mutable while parent is `draft`; insert/update/delete blocked once parent is `finalized` |
| `rag_sandbox_retrieval_runs` | Append-only |
| `rag_sandbox_retrieval_results` | Append-only |
| `rag_sandbox_answer_runs` | Append-only |
| `rag_sandbox_citations` | Append-only |
| `rag_sandbox_evaluations` | Append-only (one row per dimension per answer run) |
| `rag_sandbox_human_reviews` | Append-only, attributed |
| `rag_sandbox_reports` | Append-only, versioned (`report_version` auto-increments) |
| `rag_sandbox_acceptances` | Append-only — the justified 17th table (§4) |
| `rag_sandbox_events` | Append-only domain timeline |
| `rag_sandbox_deletion_requests` | Append-only per transition, sharing a `deletion_request_code` |

Fresh-DB and upgrade-from-35 both verified: `PRAGMA user_version` → 36, `PRAGMA integrity_check`
→ `ok`, 0 foreign-key violations.

## 4. Why a 17th table

Step 24 requires Admin acceptance to be a *separate*, staleness-checked decision distinct from
per-query human review and from the experiment's own mutable lifecycle row. Folding acceptance
into `rag_sandbox_experiments` would let a later "needs_more_testing" resubmission overwrite the
history of a prior decision, and would prevent comparing the *current* report checksum against the
checksum bound at the time of one specific acceptance. `rag_sandbox_acceptances` is append-only,
stores `report_checksum_sha256` + `target_fingerprint`, and is rejected as stale by
`RagSandboxAcceptanceService.decide()` whenever either no longer matches current state.

## 5. Experiment lifecycle

18 statuses (`draft` → `awaiting_approval` → `approved` → `preparing_corpus` →
`building_index` → `ready` → `running_retrieval` → `running_generation` → `needs_review` →
one of `accepted`/`accepted_with_conditions`/`rejected`/`needs_more_testing`(→`needs_review`),
plus `failed`/`cancelled`/`expired`/`withdrawn`/`deleted`) stored in `status`; 13 stages
(`eligibility` → ... → `acceptance`) stored separately in `current_stage`. Never one boolean.
Every transition is logged to `rag_sandbox_events`.

## 6. Eligibility gate (Step 4)

`RagSandboxEligibilityService.check_eligibility(sample_import_public_id)` checks, read-only:
finalized Phase 12 sample import, `rag_sandbox_eligible=true`, a finalized report exists,
≥1 accepted record exists, no unresolved blocked PII issue, no blocked security-scan verdict,
no active rights-withdrawal notice, Phase 11 verification still current, `rag_use` permission not
denied, provider/source lineage intact. Training permission is deliberately never checked.
Commercial permission is surfaced read-only, never gated on.

## 7. Approval binding (Step 5)

`rag_sandbox_approvals` binds all 13 fields Step 5 lists (accepted-record id/checksum set,
bounds, chunking/retrieval configuration, embedding/generation assignment keys, query-set id,
`expires_at`, `target_fingerprint`, `conditions`). `target_fingerprint` is a SHA-256 digest over
the sample-report checksum, accepted-record-checksum-set hash, purpose, query-set id, and the
three bound limits — computed identically by `RagSandboxApprovalService.is_stale()` and (once
wired) the Admin Assistant's `STALE_CHECK_FINGERPRINTS`. Once `status='approved'`, a schema
trigger blocks any change to a bound field except a transition to `expired`/`superseded`.

**Fix applied during this phase's own security pass** (mirroring Phase 12's identical
post-mortem): `RagSandboxCorpusService.prepare_corpus()` originally checked approval `status` and
staleness but never `expires_at`. Added `_is_expired()` (byte-for-byte the same logic as Phase
12's `dataset_sample_download_service._is_expired()`) and a check at the top of `prepare_corpus()`
— Phase 13's equivalent of Phase 12's "first real action taken under the approval". Covered by
`tests/backend/test_rag_sandbox_security.py::test_prepare_corpus_rejects_an_expired_approval` /
`test_prepare_corpus_succeeds_with_a_future_expiry`.

Note: unlike Phase 12, `expires_at` is **optional** in `rag_sandbox_approvals` (nullable column,
optional service parameter) — a deliberate, narrower scope decision, documented in §14 Known
Limitations.

## 8. Isolation model (Step 7)

- `sandbox_scope_key` = the sandbox space's own `rag_knowledge_spaces.slug`
  (`sandbox-<experiment_public_id>`, globally unique).
- `sandbox_corpus_id` = `rag_sandbox_corpora.public_id` (governance link row).
- `sandbox_index_id` = `rag_sandbox_indexes.public_id`.
- `production_visible` = hard-`CHECK`ed to `0` on `rag_sandbox_corpora` — no code path anywhere
  can set it to `1`.

Structural guarantees, verified by tests:
- `RagRetrievalService.retrieve()` always resolves the active vector/keyword index *for the
  profile's own `knowledge_space_id`* — a sandbox profile is FK'd to the sandbox space and cannot
  retrieve production chunks without a human manually rewriting a foreign key (no code path does).
- The only real production-chat entrypoint (`chat.py`) is an explicit placeholder with no RAG
  wiring at all in this codebase; the Admin Assistant's own chat (`chat_orchestration_service.py`)
  only ever queries a `retrieval_profile_public_id` a human Admin explicitly configured — Phase 13
  never auto-registers a sandbox profile there.
- Admin-only APIs use the same `require_admin` + CSRF dependency as `rag.py`/
  `dataset_sample_import.py` — no new auth mechanism.

## 9. Chunking and indexing (Steps 8–9)

Reuses `core_model.rag.chunking.chunk_text()`/`ChunkingConfig` and
`RagIngestionService.create_chunk_set`/`create_embedding_model`/`create_embedding_run`/
`execute_embedding_run`/`create_vector_index`/`build_vector_index`/`create_keyword_index`/
`build_keyword_index` verbatim, through `RagSandboxIndexService.build_index(experiment_id, *,
index_kind, chunking_config, embedding_model_public_id, top_k, minimum_score)`. `index_kind` is
one of `bm25`/`vector`/`hybrid` — `hybrid` builds both a vector and a keyword index and one
retrieval profile with `vector_weight=0.6, keyword_weight=0.4` (bm25-only and vector-only use
`0/1` and `1/0` respectively). Every index build failure marks the `rag_sandbox_indexes` row
`failed` and the experiment `failed`, with an `index_build_failed` event — no silent partial state.

Embedding uses the existing `local_custom_embedding` provider (deterministic CPU-only hashing-
trick) unless an existing embedding model's `public_id` is supplied — never a new provider type.

## 10. Query-set model (Step 10)

`rag_sandbox_query_sets` (`draft`→`finalized`, then immutable — schema trigger blocks further
inserts into `rag_sandbox_queries` once finalized) and `rag_sandbox_queries` (all Step 10 fields:
`query_type` one of 12 values, `language`, `expected_source_ids`, `must_refuse_if_insufficient`,
`conflict_expected`, `injection_test`, `human_authored`). `RagSandboxQuerySetService.
finalize_query_set()` refuses if any `human_authored=0` query has no
`reviewed_by_admin_public_id` yet.

## 11–12. Retrieval configurations and evaluation (Steps 11–12)

`rag_sandbox_indexes.build_config_json` doubles as the versioned, explainable retrieval
configuration. `RagSandboxRetrievalService.run_retrieval()` calls `RagRetrievalService.retrieve()`
unmodified for every finalized query, then computes recall@k/precision@k/MRR/expected-source-hit
using `core_model.rag.evaluation`'s pure functions **only** when a query carries
`expected_source_ids` — otherwise `metric_availability="not_available"`, never fabricated. Per-
query results are matched to their originating sandbox record via each retrieved chunk's
`heading_path[0]` (§2), parsed from the JSON the repository stores (a real bug caught during
testing: the raw `heading_path_json` string was initially indexed directly instead of parsed,
silently breaking every hit — fixed and covered by
`test_rag_sandbox_query_and_retrieval_services.py`). Latency, duplicate-result rate, and
language-match (via `core_model.rag.language_routing.classify_language`, mapped into the sandbox's
own language vocabulary through the shared `core_model.rag_sandbox.
LANGUAGE_CATEGORY_TO_SANDBOX_LANGUAGE` constant) are recorded per query.

## 13–14. Grounded answer generation and citation validation (Steps 13–14)

`RagSandboxAnswerService.run_generation()` calls `RagGenerationService.grounded_answer()`
unmodified for every retrieval result, then prefixes the stored answer text with
`"Sandbox evaluation output — not production guidance."` (Step 13's exact requirement) **without
touching the shared production service** — the disclaimer is added only to what Phase 13 persists
into `rag_sandbox_answer_runs`, never to production's own `rag_grounded_answers` row. Citation
validation reuses production's `valid`/`valid_with_warning`/`invalid`/`not_present` vocabulary,
mapped onto 4 of the sandbox's 6-value vocabulary (`valid`/`partially_supporting`/`invalid`/
`missing`); `unsupported`/`conflicting` are Phase-13-only richer classifications not yet computed
(§14 Known Limitations — never fabricated, only left absent).

## 15–20. Unsupported claims, insufficient evidence, conflicts, injection, language, quality

`RagSandboxEvaluationService.run_evaluation(experiment_id, answer_run_id)` computes and stores one
`rag_sandbox_evaluations` row per applicable dimension, always `automated=1`:
- **unsupported_claim** — reuses `core_model.rag.grounding_checks.unsupported_sentence_ratio()`
  verbatim on the answer body (disclaimer stripped first).
- **insufficient_evidence** — only for queries with `must_refuse_if_insufficient` or
  `query_type='insufficient_evidence'`; compares actual `refusal_used` against expectation
  (`correct_refusal`/`false_answer`/`overconfident_answer`).
- **conflict_handling** — only for `conflict_expected`/`conflicting_sources` queries; a
  deterministic heuristic (English + Tamil conflict-language keyword match, combined with
  citation_count ≥ 2) — documented as a heuristic, not a claim of semantic conflict detection.
- **prompt_injection** — only for `injection_test`/`prompt_injection` queries; reuses
  `core_model.rag.injection_filter.detect_injection_signals()`/`classify_injection_status()`
  against the *answer* text (checking whether the model's own output leaked injected content),
  mapped to `blocked`/`neutralized`/`warning`/`failed`/`not_detected`. Never claims complete
  prompt-injection security.
- **language_compliance** — reuses `classify_language()`, mapped into the sandbox vocabulary,
  compared against the query's declared language.
- **answer_quality** — a small, honestly-labeled composite (`1 - unsupported_ratio -
  repetition_ratio`); `repetition_ratio` is a new, tiny, literal-token-repeat detector (nothing
  existing computes this) — never a substitute for the Step 22 human review acceptance requires.

## 21. Threshold policy (Step 21)

`core_model.rag_sandbox.DEFAULT_THRESHOLDS` (versioned `THRESHOLD_VERSION="v1"`) — 8 dimensions
(minimum expected-source-hit rate, minimum citation-validity rate, maximum unsupported-claim/
hallucination rate, minimum language-compliance rate, maximum injection-failure count, maximum
unresolved-conflict-failure count, maximum average latency). `maximum_injection_failure_count` and
`maximum_unresolved_conflict_failures` are hard-block dimensions — failing either always yields
`production_rag_readiness="blocked"` regardless of every other metric.

## 22. Human review (Step 22)

`rag_sandbox_human_reviews` — append-only, attributed, one row per query covering all 7 Step-22
dimensions plus a `decision` in the 6-value vocabulary. `RagSandboxReportService.finalize()`
refuses while any answered query has zero human-review coverage.

## 23. Final report (Step 23)

`RagSandboxReportService.finalize()` recomputes every metric fresh from the live tables (never
trusts a cached rollup), includes every Step-23 field (lineage, approval scope, selected records,
chunking/index configuration, query-set summary, retrieval/answer/citation/language metrics,
insufficient-evidence/conflict/injection results, human-review summary, failed queries,
conditions, blocking reasons, resource usage, `production_rag_readiness`,
`training_data_observation`, `recommended_next_action`), and is stored append-only with an
auto-incrementing `report_version` and a `report_checksum_sha256`.

## 24. Admin acceptance (Step 24)

`RagSandboxAcceptanceService.decide()` is a wholly separate call from `finalize()`. Rejected as
stale if the `report_public_id` passed no longer matches the latest report, or if the bound
approval's `target_fingerprint` no longer matches current Phase 12 state. Never activates
production RAG or approves training — there is no such code path.

## 25. Phase 14 handoff signals

`rag_sandbox_experiments.eligible_for_production_rag_proposal` /
`eligible_for_training_assessment` — plain booleans set once at report finalization, read-only
afterward, consumed by no Phase 13 code path. Phase 14 must gate on them separately.

## 26. Expiry and deletion (Step 26)

`RagSandboxDeletionService`: `request_deletion` (computes an impact preview) → `confirm_deletion`
→ `execute_deletion` (archives the sandbox `rag_knowledge_spaces` row via the existing
`RagIngestionService.patch_space(lifecycle_status="archived")` — the real production lifecycle
mechanism, never a raw `DELETE` — and marks `rag_sandbox_corpora`/`rag_sandbox_indexes` `deleted`)
→ reports/acceptances/events/audit are never touched. No scheduler.

## 27–28. Backend modules and APIs

11 orchestration services (`rag_sandbox_eligibility_service.py` also hosts
`RagSandboxApprovalService`) + `RagSandboxRepository` (17-table CRUD, mirrors
`DatasetSampleImportRepository`'s exact style). 38 routes under `/api/admin/rag-sandbox`
(`backend/api/routes/rag_sandbox.py`), admin-auth + CSRF on every mutating route, pagination via
`page`/`page_size` query params capped at 100, no raw SQL in the API layer.

## 29–30. Admin Assistant integration

10 read-only tools (`get_rag_sandbox_experiment` … `get_rag_sandbox_acceptance_status`) + 16
controlled actions (`create_rag_sandbox_experiment` … `execute_rag_sandbox_deletion`), each with
full `propose → preview → review → stale-check → execute → verify → audit` wiring — verified by
exact-parity checks (`ACTION_EXECUTORS`/`STALE_CHECK_FINGERPRINTS`/`PREVIEW_GENERATORS` keys ==
`ACTION_DEFINITIONS` action types, no gaps either direction). Deterministic guidance/FAQ
(`core_model/admin_assistant/rag_sandbox_help.py`, 12 fixed questions, Tanglish always derived via
`localize()`, never hand-written) wired into `admin_assistant_chat_service.py`'s dispatch chain
ahead of the general LLM fallback. The pre-existing `"rag sandbox"` keyword was removed from
Phase 12's `_SAMPLE_IMPORT_KEYWORDS` (it predates Phase 13 and would otherwise steal Phase-13
guidance requests).

## 31. Frontend

`RagSandboxPage.jsx` — 17 tabs (Overview, Experiments, Approval, Corpus, Chunks, Indexes, Query
Sets, Retrieval Results, Grounded Answers, Citations, Language/Conflict/Injection Tests, Human
Review, Final Report, Acceptance, Deletion & History). "Chunks" reuses `rag_sandbox_indexes`' own
`chunk_count`/`record_count` fields (no separate chunk-listing endpoint was built — nothing to
fabricate). Sandbox answer text is always rendered as returned, which always begins with the
sandbox disclaimer. Final Report/Acceptance tabs never render "Production RAG Activated",
"Training Approved", or "Model Released" text (asserted by a dedicated frontend test).

## 32. Phase 12 integration

`DatasetSampleImportPage.jsx`'s Final Report tab gains "Create RAG Sandbox Proposal"/"Open
Existing RAG Sandbox" buttons, shown only when `report.rag_sandbox_eligible` is true.

## 33. Existing RAG integration

No production RAG file is modified except two additive, backward-compatible fixes unrelated to
Phase 13's own request shape:
- `dashboard_registry.py`: added `"rag_sandbox"` to `dataset_sample_import`'s
  `related_page_ids` (bidirectional cross-link, matching the existing convention).
No other Phase 16 file (`rag_ingestion_service.py`, `rag_retrieval_service.py`,
`rag_generation_service.py`, `rag_evaluation_service.py`, `database/repositories/rag.py`,
`api/routes/rag.py`) was modified at all.

## 34. Memory isolation

Stateless by default (Step 34 explicit permission) — no sandbox code path writes to or reads
`conversation_memory_policies`/`conversation_sessions`. No persistent memory policy is
auto-created.

## 35. Data Overview integration

New `ragSandbox` metrics group (10 real, server-computed counts from
`RagSandboxRepository.overview_counts()`) + "Open RAG Sandbox" action.

## 36. Help registry

Bilingual `purpose`/`safety_note` text on the new `rag_sandbox` `PageEntry` (Tamil + English),
plus the 12-question deterministic FAQ (§29–30). Tanglish derived, never hand-authored, per
Phase 10A convention.

## 37. Performance and resource controls

CPU-first, synchronous, staged, cancellable-by-not-continuing execution — no background job
system exists in this repo and none was invented. Bounds enforced: `maximum_records`,
`maximum_total_characters`, `maximum_total_tokens` (checked during corpus promotion, blocking
further records once exceeded, not silently truncating already-promoted ones);
`DEFAULT_MAX_QUERIES`/`DEFAULT_MAX_RETRIEVAL_CONFIGURATIONS`/`DEFAULT_MAX_TOP_K`/
`DEFAULT_MAX_GENERATION_TOKENS`/`DEFAULT_MAX_CONCURRENT_RUNS` defined in `core_model.rag_sandbox`
for future enforcement wiring at the API layer (bounds exist and are honored by the underlying
Phase 16 services' own existing limits — `rag_max_chunks_per_source`,
`rag_embedding_batch_size`, etc. — reused, not reinvented).

## 38. Security controls

See `tests/backend/test_rag_sandbox_security.py` (67 tests): structural AST scan (no
`eval`/`exec`/`subprocess`/`os.system`) across all 14 Phase 13 modules; no direct writes to any
production dataset/RAG table (26-table forbidden list, `rag_sandbox_*` deliberately excluded); no
module spells `training_approved`/`production_rag_activated`/"Training Approved"/"Production RAG
Activated"/"Model Released" (enums file correctly excluded — it's the one place that must
enumerate them as prohibited); no module downloads external content; expired-approval rejection at
corpus preparation; `production_visible` hard-`CHECK` proven at the SQL level; rejected/PII-blocked
records proven to block eligibility; every mutating service proven to import and call
`AuditLogRepository`.

## 39. Tests

- Migration: `tests/database/test_rag_sandbox_repository.py` (30 tests) — fresh DB, append-only
  triggers, immutability triggers, lifecycle constraints, FK integrity.
- Eligibility/approval: `test_rag_sandbox_eligibility_service.py` (11).
- Corpus/promotion: `test_rag_sandbox_corpus_service.py` (5).
- Indexing: `test_rag_sandbox_index_service.py` (6).
- Query sets/retrieval: `test_rag_sandbox_query_and_retrieval_services.py` (5).
- Answers: `test_rag_sandbox_answer_service.py` (1, full HTTP-driven admin_diagnostic assignment
  bootstrap + real deterministic generation runtime).
- Evaluation: `test_rag_sandbox_evaluation_service.py` (2).
- Review/report/acceptance/deletion: `test_rag_sandbox_review_report_acceptance_deletion.py` (3,
  full lifecycle).
- API: `test_rag_sandbox_api.py` (4, full HTTP happy path + CSRF + auth + ineligibility).
- Admin Assistant: `test_rag_sandbox_admin_assistant.py` (11, registry parity + full propose/
  review/execute pipeline + FAQ + bilingual chat).
- Security: `test_rag_sandbox_security.py` (67).
- Frontend: `RagSandboxPage.test.jsx` (8) + `DataOverviewPage.test.jsx` updates.

Total backend: **145 Phase 13 tests**, all passing. Full existing backend/admin-assistant
regression suites re-run clean (98 admin-assistant tests, 0 regressions). Frontend: **133 tests**
across the whole admin dashboard (up from 128 pre-Phase-13), 0 regressions; production build
succeeds.

## 40. Manual browser verification

See the final completion report for the executed flow list and results.

## 41. Known Phase 12 limitations inherited

Phase 12's documented limitations (existing-corpus checksum sets not wired into every
contamination check; OCR engine not wired by default; pre-existing hash-deep-link bug) are
inherited unchanged. Phase 13 uses only finalized, accepted Phase 12 records and never depends on
OCR. A promoted record's `contamination_flagged` state is therefore only as reliable as Phase 12's
own contamination check was for that record — surfaced honestly in the corpus record view and the
final report, never silently assumed complete.

## Known limitations (Phase 13's own)

- `rag_sandbox_approvals.expires_at` is optional (nullable), unlike Phase 12's mandatory field —
  a narrower-scope decision. When set, expiry is enforced at corpus preparation (§7); when unset,
  the approval remains subject only to the continuous staleness check against live Phase 12 state.
- Citation validation reuses production's 4-value vocabulary; the sandbox's own `unsupported`/
  `conflicting` citation-status values are defined in the schema but not yet computed by any
  service — citations are never classified into them today.
- `conflict_handling` evaluation is a keyword-based heuristic, not semantic conflict detection.
- No separate on-disk chunk-listing endpoint was built; the "Chunks" frontend tab shows per-index
  aggregate counts only.
- Resource-bound constants (`DEFAULT_MAX_QUERIES`, etc.) are defined but not yet enforced as hard
  request-time limits at the API layer — today's practical bound is Phase 16's own existing
  per-source/per-run limits, inherited for free.
- No load/perf testing was performed against a large (hundreds of records) corpus.

## Phase 14 handoff

Phase 13 produces exactly two advisory booleans
(`eligible_for_production_rag_proposal`/`eligible_for_training_assessment`) and two advisory
strings (`production_rag_readiness`/`training_data_observation`). Phase 14 (training-dataset
creation and training) must consume them through its own, separate, later approval gates — no
Phase 13 code path activates production RAG, creates a training dataset version, starts training,
or approves a model release.
