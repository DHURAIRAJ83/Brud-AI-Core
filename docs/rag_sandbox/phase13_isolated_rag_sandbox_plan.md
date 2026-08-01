# Phase 13 — Isolated RAG Sandbox, Retrieval Evaluation, Grounded Answer Testing & Admin Acceptance — Plan

Baseline: Phase 12 complete (`PHASE_12_COMPLETE_WITH_LIMITATIONS`), schema version 35. This
document is written before any Phase 13 implementation code, per Step 1.

## 1. Existing systems reused (baseline inspection findings)

Inspected directly (file + exact identifier):

| Need | Existing component | Reuse strategy |
|---|---|---|
| Knowledge namespace / corpus / chunk / index tables | `backend/database/schema.py` `PHASE16_SCHEMA` (migration 020 area): `rag_knowledge_spaces`, `rag_knowledge_sources`, `rag_source_versions`, `rag_chunk_sets`, `rag_chunks`, `rag_embedding_models`, `rag_embedding_runs`, `rag_chunk_embeddings`, `rag_vector_indexes`, `rag_keyword_indexes`, `rag_retrieval_profiles`, `rag_retrieval_runs`, `rag_retrieved_chunks`, `rag_context_assemblies`, `rag_grounded_requests`, `rag_grounded_answers`, `rag_answer_citations`, `rag_grounding_issues`, `rag_evaluation_suites/fixtures/runs/metrics`, `rag_index_comparisons`, `rag_manifests` | **Reuse the live tables/rows themselves, not just the code.** Every sandbox experiment creates its own `rag_knowledge_spaces` row; all ingestion/chunking/embedding/indexing/retrieval/generation for that experiment go through the *existing* services against that one space. No new corpus/chunk/index table is created. |
| Ingestion (source → source_version → chunk_set → chunks) | `backend/services/rag_ingestion_service.py::RagIngestionService` (`create_source`, `create_source_version`, `create_chunk_set` → `core_model/rag/chunking.py::chunk_text()`) | Call directly with `source_type="manual_admin_content"` (already an allowed value in the existing `rag_knowledge_sources.source_type` CHECK — no schema edit needed) and content = the promoted sandbox record's text |
| Embedding | `RagIngestionService.create_embedding_model/create_embedding_run` → `core_model/rag/embedding.py::compute_embedding()` (deterministic local providers only: `local_sentence_transformer`/`local_custom_embedding`/`deterministic_test_embedding` — no external embedding provider exists in this repo) | Reuse directly; sandbox never introduces a new provider type |
| Vector/keyword index build | `RagIngestionService.create_vector_index/build_vector_index`, `create_keyword_index/build_keyword_index` (BM25 via SQLite FTS5, vector via `index_type="repository_flat"` — brute-force cosine over `rag_chunk_embeddings.vector_blob`, no external index file) | Reuse directly. Confirms Step 9's "no uncontrolled concurrency, disk-space precheck" is inherited for free — everything lives inside the same bounded SQLite file, no separate on-disk vector index artifact |
| Hybrid retrieval / ranking | `backend/services/rag_retrieval_service.py::RagRetrievalService.retrieve()` + `core_model/rag/hybrid_retrieval.py`, `access_filter.py`, `keyword_index.py`, `vector_index.py`, `query_normalization.py`, `language_routing.py` | Call `RagRetrievalService.retrieve()` unmodified, pointed at a sandbox-scoped `rag_retrieval_profiles` row (itself FK'd to the sandbox `knowledge_space_id`) |
| Grounded generation | `backend/services/rag_generation_service.py::RagGenerationService` (`grounded_answer()`/`_generate_and_persist()`) + `core_model/rag/answer_policy.py`, `context_budget.py`, `context_builder.py`, `citation_builder.py`, `grounding_checks.py` | Call directly. Insufficient-evidence refusal, context budgeting, and citation-map construction are already implemented — Phase 13 never re-implements them |
| Prompt-injection filtering | `core_model/rag/injection_filter.py::detect_injection_signals()/classify_injection_status()` — already wired into `RagIngestionService`'s chunk creation (`rag_chunks.injection_status`) and structurally excluded from every index/context by `rag_retrieval_service.py`'s access filter | Reuse verbatim — a sandbox chunk containing an injection payload is flagged and excluded exactly as production chunks are, with zero new code |
| Citation validation | `core_model/rag/grounding_checks.py::validate_citation()`, `compute_grounding_quality()`, `unsupported_sentence_ratio()` | Reuse directly for base validation; Phase 13 adds a *richer* status vocabulary (`partially_supporting`/`conflicting`) as its own governance-layer classification on top, stored in the new `rag_sandbox_citations` table — never altering the existing `rag_answer_citations.validation_status` CHECK |
| Retrieval/generation evaluation metrics | `backend/services/rag_evaluation_service.py`, `core_model/rag/evaluation.py` (`hit_rate`, `mean_reciprocal_rank`, `precision_at_k`, `recall_at_k`, `ndcg_at_k`, `aggregate_retrieval_metrics`, `aggregate_generation_metrics`) | Reuse the pure metric functions directly against sandbox retrieval results |
| Model assignment / inference runtime | `backend/services/model_assignment_service.py::ModelAssignmentService`, `backend/services/inference_runtime_service.py::InferenceRuntimeService`, `inference_model_assignments` (scope_key, e.g. `admin_diagnostic`) | Reuse the existing `admin_diagnostic` assignment scope for actual model execution (no new model/embedding provider); sandbox isolation is expressed instead via `rag_grounded_requests.scope` (a plain `TEXT` column with no CHECK constraint) — set to `"admin_rag_sandbox:<experiment_public_id>"` instead of the existing `"admin_rag_lab"` |
| Conversation-memory scoping | `backend/database/schema.py` migration 017 (`conversation_memory_policies`, `conversation_sessions.participant_scope_key`), `backend/services/chat_orchestration_service.py` | Not written to by default (Step 34: stateless mode acceptable). If a sandbox chat-lab-style multi-turn session is ever used, `participant_scope_key = "admin_rag_sandbox:<experiment_id>"` — same convention already used for `"admin:<admin_public_id>"` |
| Public/production chat surface | `backend/api/routes/chat.py` (`POST /chat` — explicit placeholder, no model wired, no RAG call at all); `core_model/admin_assistant/dashboard_registry.py`'s own `knowledge_rag` page safety_note: *"The public chatbot is never connected here — this remains an admin-only lab."* | Confirms there is no live public RAG surface today. "Production RAG" in this codebase = the existing admin-only `admin_rag_lab` (Knowledge & RAG page). Phase 13's sandbox must be isolated from *that*, which is already achieved structurally by using a distinct `knowledge_space_id` (every retrieval call is FK-scoped to one space; cross-space leakage is impossible without an admin manually pointing a retrieval profile at the wrong space, which the sandbox never does) |
| Migration conventions | `backend/database/schema.py` (`SCHEMA_VERSION`, `PHASE35_SCHEMA` executescript pattern), `backend/database/migrations.py` (`_apply_v35`, idempotent via `schema_migrations` guard) | Byte-for-byte same pattern for migration 036 |
| Append-only trigger pattern | Phase 12's `external_dataset_sample_*` triggers (`BEFORE UPDATE/DELETE ... RAISE(ABORT, ...)`), approval-immutability trigger (blocks bound-field change once `status='approved'`, permits only transition to `expired`/`superseded`) | Same pattern for all 11 append-only Phase 13 tables and the sandbox approval |
| Deletion-request append-only-per-transition | Phase 12's `external_dataset_sample_deletion_requests` (`deletion_request_code` shared across `requested`/`confirmed`/`executed`/`cancelled` rows) | Same pattern for `rag_sandbox_deletion_requests` |
| Audit | `backend/database/repositories/phase2.py::AuditLogRepository.append()` (auto-redacts via `redact_secrets()`) | Reuse directly, as Phase 12 did |
| Admin Assistant registries | `core_model/admin_assistant/action_registry.py::ActionDefinition`, `backend/services/admin_assistant_tools.py::ToolDefinition`, `core_model/admin_assistant/dashboard_registry.py::PageEntry`, `backend/services/admin_assistant_service.py` (`ACTION_EXECUTORS`/`STALE_CHECK_FINGERPRINTS`/`PREVIEW_GENERATORS`), Phase 10A's `localize()` | Structurally identical new entries |
| Phase 12 lineage source | `backend/database/repositories/dataset_sample_import.py::DatasetSampleImportRepository`, tables `external_dataset_sample_imports/reports/records/reviews/record_issues` | Read-only: sandbox eligibility/promotion reads these directly, never writes them |
| Storage-directory convention | `backend/core/config.py::Settings` allowlisted `Path` fields | Not needed — Phase 13 introduces no new on-disk payload storage; every sandbox artifact (chunks, embeddings, index rows) lives in the same SQLite database Phase 16 already uses |

### Deliberately NOT reused / NOT duplicated

`RagPage.jsx`'s existing "Knowledge & RAG" admin lab workflow is left completely untouched —
Phase 13 adds an *orchestration and governance layer* around the same backend services, never a
competing reimplementation. No chunking, BM25, vector scoring, hybrid ranking, citation mapping,
grounded-generation, or injection-filtering code is rewritten anywhere in Phase 13.

### Built from scratch (no reusable component existed)

Sandbox experiment/approval lifecycle and staleness binding (mirrors Phase 12's shape, new
domain); record-promotion rules bridging Phase 12 review decisions into new `rag_source_versions`;
query-set model (admin/assistant-authored, multilingual, adversarial, insufficient-evidence,
conflict, injection test queries) — nothing like this exists; per-query retrieval/answer
evaluation-metric persistence keyed to a query set (existing `rag_evaluation_fixtures` is
suite-wide and requires pre-known "expected relevant chunk ids", not the richer per-query
governance fields Phase 13 needs); conflict-handling and prompt-injection-resistance *test*
harnesses (the existing injection filter only classifies retrieved-chunk *content*; nothing
today deliberately injects malicious content into a query set and scores the model's resistance);
human review at query granularity; immutable sandbox report; separate Admin acceptance step.

## 2. Architecture decision: isolation model

Step 7 offers two options. **Preferred is chosen**: reuse the existing `rag_knowledge_spaces`
table as the sandbox namespace itself, rather than building a parallel corpus/index stack.

- `sandbox_scope_key` = the sandbox `rag_knowledge_spaces.slug` (`sandbox-<experiment_public_id>`,
  globally unique per the table's existing `UNIQUE(slug)` constraint — this *is* the namespace).
- `sandbox_corpus_id` = the sandbox `rag_knowledge_spaces.public_id` (governance-tracked in the new
  `rag_sandbox_corpora` table, which is a thin link row, not a payload store).
- `sandbox_index_id` = the sandbox `rag_vector_indexes.public_id` / `rag_keyword_indexes.public_id`
  built inside that space (governance-tracked in `rag_sandbox_indexes`).
- `production_visible` = a hard-coded `0` CHECK constraint on `rag_sandbox_corpora` — there is no
  code path that can ever set it to 1; it exists purely as an explicit, auditable structural
  assertion, not a runtime toggle.

**Why this satisfies every Step 7 hard requirement without new retrieval code:**

- `RagRetrievalService.retrieve()` always resolves `active_vector_index_for_space(space_id)` /
  `active_keyword_index_for_space(space_id)` from the retrieval profile's own
  `knowledge_space_id` FK. A sandbox retrieval profile is FK'd to the sandbox space; it is
  *structurally impossible* for it to retrieve production chunks, and vice versa, without an
  admin manually rewriting a foreign key by hand (which no Phase 13 code path does).
- Production chat cannot reach sandbox data because production chat does not exist yet (`chat.py`
  is a placeholder) and the one real consumer of `RagRetrievalService` outside the admin lab
  (`chat_orchestration_service.py`, used by the Admin Assistant's own conversation-memory chat) is
  itself admin-only and only ever passes a `retrieval_profile_public_id` that a human admin chose
  — Phase 13 never auto-registers a sandbox profile there.
- "Sandbox retrieval cannot silently include production records unless explicitly configured as a
  comparison baseline" — a sandbox retrieval profile has exactly one `knowledge_space_id` (the
  sandbox space). There is no comparison-baseline feature in Phase 13 (out of scope); this
  requirement is satisfied by omission — a baseline comparison would require a second, explicit
  retrieval profile pointed at a different space, which Phase 13 does not build.
- Admin-only APIs enforce authentication/CSRF via the same dependency every other admin route
  already uses (`backend/api/deps.py`'s admin-session dependency, applied to `rag.py` and
  `dataset_sample_import.py` identically) — Phase 13's router uses the identical dependency, not a
  new one.

## 3. Schema design — 17 tables

Step 2 recommends 16. A 17th, `rag_sandbox_acceptances`, is added and justified: Step 24 requires
Admin acceptance to be a *separate*, append-only, staleness-checked decision distinct from
per-query human review (Step 22) and from the experiment's own mutable lifecycle row. Folding
acceptance into `rag_sandbox_experiments` would make re-acceptance after "needs_more_testing"
overwrite history and would prevent the stale-report check Step 24 requires (which needs to
compare the *current* report checksum against the checksum bound at the time of a specific
acceptance decision). This mirrors Phase 12's own precedent of adding a 9th table beyond a
12-table recommendation for an analogous reason.

| Table | Kind | Notes |
|---|---|---|
| `rag_sandbox_experiments` | Mutable lifecycle row | status/stage columns (Step 3), advisory readiness signals set only at report finalization |
| `rag_sandbox_approvals` | Mutable until decided, then append-only (immutability trigger) | Binds all Step 5 fields incl. `target_fingerprint` |
| `rag_sandbox_corpora` | Mutable status (building/ready/failed) | Thin link to the sandbox `rag_knowledge_spaces` row; `production_visible` hard-CHECKed to 0 |
| `rag_sandbox_records` | Append-only | Promotion record: source lineage to Phase 12 + link to the real `rag_knowledge_sources`/`rag_source_versions` row created for it |
| `rag_sandbox_indexes` | Mutable lifecycle (validated transitions only) | Governance wrapper per BM25/vector/hybrid build, linking to real `rag_vector_indexes`/`rag_keyword_indexes`/`rag_retrieval_profiles` rows |
| `rag_sandbox_query_sets` | Mutable until finalized, then immutable | `finalize` blocks further inserts into `rag_sandbox_queries` via trigger |
| `rag_sandbox_queries` | Mutable while parent draft, immutable once parent finalized | Trigger checks parent `rag_sandbox_query_sets.status` |
| `rag_sandbox_retrieval_runs` | Append-only | One row per (query set, index) batch header |
| `rag_sandbox_retrieval_results` | Append-only | One row per query within a run; links to the real `rag_retrieval_runs.public_id`; stores Step 12 metrics, honestly marked `partial`/`not_available` when ground truth is missing |
| `rag_sandbox_answer_runs` | Append-only | One row per query's grounded-answer test; links to the real `rag_grounded_requests.public_id` |
| `rag_sandbox_citations` | Append-only | Per-citation richer validation status, links to the real `rag_answer_citations.public_id` |
| `rag_sandbox_evaluations` | Append-only | General-purpose evaluation result row (unsupported-claim / insufficient-evidence / conflict / injection / language / quality), covers Steps 15–20 |
| `rag_sandbox_human_reviews` | Append-only | Query-level review, Step 22 |
| `rag_sandbox_reports` | Append-only, versioned | Immutable snapshot, Step 23, mirrors Phase 12's `report_version` auto-increment pattern |
| `rag_sandbox_acceptances` | Append-only | Justified 17th table, Step 24 |
| `rag_sandbox_events` | Append-only | Domain timeline (UI "Deletion & History"), parallel to (not a replacement for) `audit_logs` |
| `rag_sandbox_deletion_requests` | Append-only per transition | Mirrors Phase 12's `deletion_request_code` pattern |

## 4. Experiment lifecycle

18 statuses (Step 3, verbatim) stored in `rag_sandbox_experiments.status`; 13 stages in
`current_stage` (a separate plain column, never conflated with status — same "no single boolean"
discipline as Phase 11/12). Transitions logged to `rag_sandbox_events`.

## 5. Eligibility gate

Reads only, never writes, Phase 12's `external_dataset_sample_imports`/`_reports`/`_records` and
Phase 11's `dataset_verification` case (via `DatasetSampleImportRepository`/
`DatasetVerificationRepository`, both already read-only-safe). Checks every Step 4 condition.
Training permission is explicitly not checked (Step 4). Commercial permission is surfaced
read-only in the eligibility response payload, never gated on.

## 6. Approval binding

`rag_sandbox_approvals` stores every Step 5 field. `target_fingerprint` is computed the same way
Phase 12's `compute_target_fingerprint()` was: a deterministic hash over every bound field.
Immutability trigger fires once `status='approved'`, permitting only `status IN ('expired',
'superseded')` afterward — byte-for-byte the same trigger shape as Phase 12's
`external_dataset_sample_import_approvals_immutable_once_approved`.

## 7. Record promotion

Only records where, in Phase 12:

- `external_dataset_sample_records.status = 'accepted'`, AND
- the latest `external_dataset_sample_reviews` row with `target_type='record'` and
  `target_id=record.id` has `decision IN ('accept','accept_with_conditions',
  'edit_derived_copy','redact_derived_copy')`, AND
- no `external_dataset_sample_record_issues` row for that record has `issue_category='pii'` and
  `reviewer_decision IS NULL` (an unresolved PII finding always blocks promotion, matching Step 6)

...are eligible. `edit_derived_copy`/`redact_derived_copy` decisions use the review's own
`derived_content_text`/`derived_content_checksum` instead of the record's original
`normalized_content`/`record_checksum`. Each promoted record becomes one `rag_sandbox_records`
row *and* one real `rag_knowledge_sources` + `rag_source_versions` row (via
`RagIngestionService.create_source(source_type="manual_admin_content", ...)`), scoped to the
experiment's sandbox `knowledge_space_id`. Evaluation-contaminated records (flagged
`issue_category='contamination'`) may still be promoted but are tagged
`contamination_flagged=1` on `rag_sandbox_records` and are only usable by query sets whose
`query_type` is evaluation-oriented — enforced at the query-set/record-selection service layer,
not by a schema CHECK (the same record can be legitimately promoted while its *use* is
restricted).

## 8. Chunking

Reuses `core_model/rag/chunking.py::chunk_text()` and `RagIngestionService.create_chunk_set()`
verbatim, through the sandbox's own `rag_chunk_sets`/`rag_chunks` rows (FK'd to the sandbox
`source_version_id`, itself FK'd to the sandbox space). Bounded chunk configuration fields already
exist on `ChunkSetCreate`/`ChunkingConfig` (`target_tokens`, `maximum_tokens`,
`minimum_characters`, `overlap_tokens`, `sentence_window_sentences`, plus `chunking_strategy` one
of `paragraph`/`heading_aware`/`sentence_window`/`fixed_token_window`/`record_based`). Original vs.
normalized text distinction: `rag_source_versions.raw_content`/`normalized_content` already store
both separately — Phase 13 supplies the sandbox record's already-normalized Phase 12 content as
`raw_content` (Phase 12 already normalized it) and leaves `normalized_content` to whatever
additional RAG-specific normalization the existing ingestion pipeline applies, never overwriting
Phase 12's own normalization.

## 9. Index building

Reuses `RagIngestionService.create_embedding_model/create_embedding_run/execute_embedding_run`
and `create_vector_index/build_vector_index`, `create_keyword_index/build_keyword_index`
verbatim. `rag_sandbox_indexes` records `index_type` (bm25/vector/hybrid — hybrid meaning both a
vector and a keyword index built and referenced together, matching how `RagRetrievalService`
already treats hybrid as "both present"), resource usage, and status. CPU-first: reuses the
existing `rag_embedding_batch_size`/`rag_max_active_embedding_runs`/`rag_max_chunks_per_source`
settings already in `backend/core/config.py` — no new concurrency primitive.

## 10. Query-set model

New. `rag_sandbox_query_sets` (draft → finalized, then immutable) and `rag_sandbox_queries` (Step
10 fields verbatim). Assistant-suggested queries are inserted with `human_authored=0` and require
an explicit Admin review action before `finalize` will succeed if any such query remains
unreviewed.

## 11–12. Retrieval configurations and evaluation

`rag_sandbox_indexes` doubles as the versioned, explainable "retrieval configuration" (it stores
`build_config_json` including top_k/threshold/language-filter/source-filter/rerank-if-available
settings passed straight through to a sandbox `rag_retrieval_profiles` row). Metrics (Step 12) are
computed with the existing pure functions in `core_model/rag/evaluation.py`, stored per-query in
`rag_sandbox_retrieval_results`, honestly marked `partial`/`not_available` when a query has no
`expected_source_ids_json`.

## 13–15. Grounded answer generation, citation validation, unsupported-claim evaluation

Reuses `RagGenerationService.grounded_answer()` unmodified (scope string changed to
`"admin_rag_sandbox:<experiment_id>"`, disclaimer text changed to a sandbox-specific string —
Step 13's exact requirement). `rag_sandbox_answer_runs` records the Step 13 fields. Citation
validation (Step 14) starts from the existing `validate_citation()`/`rag_answer_citations` and
adds richer sandbox-only classification (`partially_supporting`/`conflicting`) computed
deterministically from token overlap between the cited chunk and answer sentence — never an LLM
self-judgment where a deterministic check is possible (Step 15's explicit requirement).

## 16–18. Insufficient evidence, conflict, injection resistance

Insufficient-evidence and conflict tests are query-set entries (`must_refuse_if_insufficient`,
`conflict_expected`) whose actual answer-run outcome is compared against the expectation by
`RagSandboxEvaluationService`, storing a pass/fail row in `rag_sandbox_evaluations`. Injection
resistance reuses `core_model/rag/injection_filter.py` at chunk-creation time (already blocks/
quarantines/warns per the retrieval profile's `injection_filter_policy`) *and* adds a query-level
test harness: a `query_type="prompt_injection"` query is answered, and the evaluation service
checks the answer text itself for leaked system-prompt content or policy-override language,
storing one of `blocked/neutralized/warning/failed/not_detected` per Step 18. This never claims
complete prompt-injection security (documented in the final report template).

## 19. Multilingual evaluation

Reuses `core_model/rag/language_routing.py::classify_language()` (already invoked by both
retrieval and generation) for requested-language / retrieved-language / answer-language
comparisons stored per query in `rag_sandbox_evaluations`.

## 20–21. Answer quality and thresholds

`rag_sandbox_evaluations` rows tagged `automated=1`. Thresholds live in a small, versioned,
in-code config dict (`core_model/rag_sandbox/thresholds.py`, `THRESHOLD_VERSION` constant) —
never hard-coded inline in the report service — read by `RagSandboxReportService` when computing
pass/fail rollups.

## 22–24. Human review, report, acceptance

Human review: `rag_sandbox_human_reviews`, append-only, attributed. Report:
`RagSandboxReportService.finalize()` recomputes everything fresh (mirrors Phase 12's report
service refusing to trust cached state) and refuses while any blocking evaluation/query remains
unreviewed. Acceptance: separate `RagSandboxAcceptanceService.decide()` call, stale-rejected if
`report_checksum` or `target_fingerprint` no longer match the latest report.

## 25. Phase 14 handoff signals

`eligible_for_production_rag_proposal` / `eligible_for_training_assessment` are plain booleans
computed once at report finalization, stored on `rag_sandbox_experiments`, read-only afterward.
Neither is ever consumed by any Phase 13 code path to activate anything — there is no production
activation endpoint or training-dataset-creation code anywhere in this phase.

## 26. Expiry and deletion

Mirrors Phase 12's `external_dataset_sample_deletion_requests` exactly: request → impact preview
→ approval → execute (deletes the sandbox `rag_knowledge_spaces`/chunks/embeddings/indexes rows
and any on-disk artifact, of which there are none — everything is in SQLite) → reports/audit
retained. No scheduler (Step 26 explicit).

## 27–28. Backend services and APIs

Services listed in Step 27 are implemented as named, with `RagSandboxRetrievalService`/
`RagSandboxAnswerService` implemented as thin orchestration wrappers around the *existing*
`RagRetrievalService`/`RagGenerationService` (never re-implementing them) plus the new
governance-row bookkeeping. No raw SQL in the API or Admin Assistant layers — everything goes
through `RagSandboxRepository`. Routes under `/api/admin/rag-sandbox`, same auth/CSRF dependency
as `rag.py`/`dataset_sample_import.py`.

## 29–30. Admin Assistant integration

Same `propose → preview → review → stale-check → execute → verify → audit` pipeline as every
prior phase, registered in the same three dicts in `admin_assistant_service.py`. Deterministic
help mirrors `core_model/admin_assistant/sample_import_help.py`'s exact pattern (Tanglish always
*derived* via `localize()`, never hand-written).

## 31–36. Frontend, Phase 12 integration, existing RAG integration, memory isolation, Data Overview, help registry

New `RagSandboxPage.jsx` (17 tabs) added under the existing `Data` sidebar group, alongside
`Sample Import & Quarantine` and `Knowledge & RAG`. `DatasetSampleImportPage.jsx`'s finalized
report tab gains "Create RAG Sandbox Proposal"/"Open Existing RAG Sandbox" buttons (same pattern
Phase 12 added to `DatasetVerificationPage.jsx`). `DataOverviewPage.jsx` gains a
`ragSandbox` metrics group. Memory isolation: stateless by default (Step 34); no policy
auto-created.

## 37. Performance and resource controls

New `Settings` fields (`BRUD_RAG_SANDBOX_MAX_*`) mirroring the existing `rag_*`/`quarantine_*`
allowlisted-bounds convention. Synchronous staged execution (no job queue exists in this repo;
none is invented, per Step 37's explicit permission to keep it synchronous-and-bounded).

## 38. Phase 12 known-limitations handling

Phase 12's documented limitations (existing-corpus checksum sets not wired into all contamination
checks; OCR engine not wired by default; pre-existing hash-deep-link bug) are inherited as-is.
Phase 13 uses only finalized, accepted Phase 12 records and does not depend on OCR. The
contamination-checksum-set gap means a promoted record's `contamination_flagged` state is only as
reliable as Phase 12's own contamination check was — documented, not silently assumed complete.

## Phase 14 handoff

Phase 13 produces two advisory booleans only. Phase 14 (training-dataset creation and training)
must consume them through its own separate approval gates, never automatically.
