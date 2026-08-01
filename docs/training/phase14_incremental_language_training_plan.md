# Phase 14 — Training Dataset Promotion, Incremental Language Training, Checkpoint Evaluation & Admin Approval — Plan

Baseline: `PHASE_13_COMPLETE_WITH_LIMITATIONS`, schema version 36. Written before implementation
code, per Step 1.

## 1. Existing systems reused (baseline inspection findings)

Inspected directly (file + exact identifier):

| Need | Existing component | Reuse strategy |
|---|---|---|
| Incremental SFT trainer/worker/checkpointing | `backend/services/instruction_tuning_service.py::InstructionTuningService` (`create_experiment`, `create_run`, `queue_run`, `run_one`, `evaluate_run`, `metrics`, `language_metrics`, `learning_checks_for_run`, `compare_runs`, `select_candidate`, `candidate`, `generate_manifest`) | Call directly. Phase 14 never reimplements a training loop, checkpoint save/load, or an evaluation metric computation |
| Continued-pretraining trainer/worker/checkpointing | `backend/services/pretraining_service.py::PretrainingService` (`create_job`, `queue_job`, `run_one`, `checkpoints`, `checkpoint`, `verify_checkpoint`, `evaluate`, `promote`, `estimate`, `preflight_payload`) | Call directly for `training_strategy="continued_pretraining"` |
| Resource hard limits (already enforced) | `PretrainingService._enforce_config()` checks `batch_size`/`sequence_length`/`total_steps`/`gradient_accumulation_steps` against `Settings.pretraining_max_*` and raises `ValidationError` | Reused verbatim via `estimate()`/`preflight_payload()`/`create_job()` — Phase 14 adds only the *governance* layer (a separate, bound, stale-checked Admin approval) around a call that already refuses unsafe configuration |
| Checkpoint comparison / catastrophic-forgetting signal | `backend/services/training_evaluation_service.py::TrainingEvaluationService.compare_runs()`/`assess_quality()` (already computes leakage rate, memorization warnings, readiness status) | Call directly from `IncrementalRegressionService`/`IncrementalTrainingComparisonService` — never recomputed |
| Model-candidate registration (`core_model_versions`, `lifecycle_status='staging'`) | `PretrainingService.promote()` / `InstructionTuningService._promote_instruction_candidate()` — both insert one `core_model_versions` row with `lifecycle_status='staging'`, `not_public_chat_ready`/`evaluation_required` metadata flags | `IncrementalModelCandidateRegistrationService` performs the identical insert shape (same table, same `staging` lifecycle value), tagged with Phase 14's own `source_experiment_public_id`/`incremental_training` provenance. Never calls `ModelReleaseService` (a separate, later, out-of-scope pipeline — see §2) |
| Dataset record storage | `backend/services/dataset_service.py::DatasetService.create_record()` (writes to the *existing* `dataset_records` table, Phase 1/2 schema, content-hash deduplicated) | Reused to materialize governed, transformed Phase 12/13 candidates as real `dataset_records` rows before versioning — the *only* new-data insertion point, unavoidable since transformed content does not exist in `dataset_records` yet |
| Dataset version build/split/manifest/checksum | `backend/services/dataset_versioning.py::DatasetVersioningService` (`create_build`, `validate_build`, `run_build`, `verify_version`, `manifest`) — source-level grouping, duplicate-hash isolation, leakage detection, reproducible seeded splits, SHA-256 manifest checksum | Reused verbatim for Step 9's immutable training dataset version. Phase 14 never creates a competing version table or duplicates split/leakage/checksum logic |
| Tokenizer compatibility | `backend/services/tokenizer_registry.py::TokenizerService`, `core_model_versions.tokenizer_version_id` FK already enforced by `PretrainingService`/`InstructionTuningService` at job/experiment creation | Reused read-only for the Step 10 compatibility check; Phase 14 never creates or retrains a tokenizer |
| Training reliability / crash recovery / quality assessment | `backend/services/pretraining_reliability_service.py`, `backend/database/repositories/training_reliability.py::TrainingReliabilityRepository` (`latest_quality_assessment`) | Reused read-only; Phase 14 never reimplements crash-recovery or resumption logic — it is inherited automatically by delegating job/run execution to the existing services |
| Governed dataset-version→pipeline handoff pattern | `backend/services/governed_training_handoff_service.py::GovernedTrainingHandoffService` — "mark ready, never auto-start a run" pattern | Phase 14's `TrainingDatasetPromotionService`/`IncrementalTrainingApprovalService` split follows the identical two-gate shape (promotion≠run-start), extended with Phase 14's own Training-Run-specific approval binding (Step 14) |
| Model registry lifecycle vocabulary | `backend/database/schema.py` `core_model_versions.lifecycle_status CHECK IN ('draft','validating','initialized','architecture_verified','smoke_tested','staging','active','failed','retired','archived')` — a partial unique index enforces one `active` row per family | Phase 14 code path **only ever** writes `lifecycle_status='staging'` — `'active'` is set exclusively by a separate, later, out-of-scope release-activation mechanism this phase never touches |
| Release-candidate pipeline (explicitly NOT reused/entered) | `backend/services/model_release_service.py::ModelReleaseService` (`create_candidate`, `assess_eligibility`, `generate_model_card`) — the actual pre-production release gate | Deliberately never called. A Phase-14 `model_candidate` (a `staging` `core_model_versions` row) is a *precondition* a human Admin may later feed into `ModelReleaseService` themselves, entirely outside this phase |
| Phase 12/13 lineage | `backend/database/repositories/dataset_sample_import.py::DatasetSampleImportRepository`, `backend/database/repositories/rag_sandbox.py::RagSandboxRepository` | Read-only. Suitability assessment reads accepted Phase 12 records/reviews and accepted Phase 13 reports/records; never writes to either |
| Migration/repository/Admin-Assistant/API conventions | Phases 11–13's own established patterns (forward-only migration functions, `BaseRepository.transaction()`/`.pagination()`, append-only/immutability triggers, `propose→preview→review→stale-check→execute→verify→audit`, `ACTION_EXECUTORS`/`STALE_CHECK_FINGERPRINTS`/`PREVIEW_GENERATORS` parity, `AuditLogRepository.append()`) | Byte-for-byte identical patterns, not re-derived |

### Deliberately NOT reused / NOT duplicated

No line of the pretraining/SFT trainer, checkpoint save/load, tokenizer, evaluation-metric
computation, or dataset-version split/manifest/checksum code is rewritten anywhere in Phase 14.
`RagPage.jsx`/`PretrainingReadinessPage.jsx`/existing training-workspace pages are left untouched;
Phase 14 adds a new, additive workspace layered *around* the same backend services.

### Built from scratch (no reusable component existed)

Phase 12/13-lineage-aware training-suitability assessment (19 dimensions); language-vs-factual
data classification (15 record categories); governed, lineage-preserving example transformation
(Q&A/summary/translation/correction/conversation-structuring); a *real* contamination-checksum
recheck sourcing actual checksum sets from existing dataset/RAG/evaluation tables (addressing
Phase 12/13's own documented deferred gap — Step 6); a replay-data plan; the two-gate
promotion≈dataset-version-approval / run-request≈training-run-approval split *specific to this
lineage*; checkpoint acceptance as a separate, stale-protected, human-review-gated Admin decision
(distinct from `InstructionTuningService.select_candidate()`'s single-step auto-promotion); a
model-candidate registration step that records Phase-14-specific lineage metadata.

## 2. Two production-adjacent lines this phase must never cross

1. **`core_model_versions.lifecycle_status='active'`** — set only by a separate activation
   mechanism (outside every file this phase touches). Verified: no Phase 14 module contains the
   string `'active'` in an `UPDATE core_model_versions` or `INSERT INTO core_model_versions`
   statement — checked by a dedicated security test.
2. **`ModelReleaseService`** — the actual release-candidate/eligibility/model-card pipeline.
   Phase 14 never imports or calls it. A `model_candidate` this phase produces is a `staging`
   `core_model_versions` row an Admin may *later*, separately, manually feed into that existing
   pipeline — never something Phase 14 does on their behalf.

## 3. Schema design — 16 tables (as recommended, no addition needed)

Unlike Phase 12 (12→13 tables) and Phase 13 (16→17 tables), the Step 2 recommended list of 16
tables is sufficient without a justified extra table — Phase 14's "separate decision" pattern
(dataset promotion vs. run approval vs. checkpoint acceptance) already maps onto 3 distinct
tables in the recommended list (`training_dataset_promotion_requests`,
`incremental_training_run_approvals`, `incremental_training_checkpoint_acceptances`), so no
17th table is needed.

| Table | Kind |
|---|---|
| `training_data_assessments` | Mutable lifecycle row |
| `training_data_assessment_items` | Append-only (one row per source record's routed classification) |
| `training_example_candidates` | Append-only (governed transformation output) |
| `training_example_revisions` | Append-only (human review / correction trail) |
| `training_dataset_promotion_requests` | Mutable until approved, then immutable except → `expired`/`superseded` |
| `training_replay_plans` | Append-only |
| `incremental_training_run_requests` | Mutable lifecycle row |
| `incremental_training_run_approvals` | Mutable until approved, then immutable except → `expired`/`superseded` |
| `incremental_training_runs` | Mutable lifecycle row (links to underlying `instruction_tuning_experiment`/`pretraining_job`) |
| `incremental_training_run_events` | Append-only |
| `incremental_training_checkpoints` | Append-only (governance wrapper referencing a real `pretraining_checkpoints` row) |
| `incremental_training_evaluations` | Append-only |
| `incremental_training_comparisons` | Append-only |
| `incremental_training_human_reviews` | Append-only |
| `incremental_training_checkpoint_acceptances` | Append-only |
| `incremental_training_reports` | Append-only, versioned |

`training_data_assessment_items`/`training_example_candidates` are append-only at the row level;
corrections happen through a new `training_example_revisions` row referencing the original
candidate, never an in-place edit — mirroring Phase 12's edit/redact-derived-copy pattern.

## 4. Training suitability model (Step 3)

`TrainingSuitabilityAssessmentService.run_assessment(sample_import_public_id | rag_sandbox_experiment_public_id)`
reads, read-only: Phase 11 verification case (licence/training/commercial permissions, currency),
Phase 12 sample import + records + reviews, Phase 13 RAG sandbox experiment + records + latest
**accepted** report. Computes all 19 Step-3 dimensions per candidate record, deterministic, no
LLM. `rag_sandbox_acceptance` dimension is read (Phase 13's `accepted`/`accepted_with_conditions`
decision) but **RAG success alone never sets a record `suitable_for_sft`/`suitable_for_pretraining`**
— that requires the record to also pass language-vs-factual routing (§5) into a training-eligible
category. This is the direct code-level enforcement of the "RAG success alone must never make
data training-suitable" rule.

## 5. Language-vs-factual policy (Step 4)

`core_model.training_incremental.classify_record_category()` — deterministic heuristic classifier
(no LLM) using: `rag_sandbox_records.contamination_flagged`, the record's Phase 12
`review.decision`, presence of instruction/response structure (looked up from the sample record's
`task`/`modality` and, when available, the RAG sandbox query/answer-run linkage for records that
were also tested in Phase 13), and simple lexical volatility signals (dates, version numbers,
"current"/"latest"/"today" markers, procedural-instruction phrasing) to route into the 15 Step-4
categories. Routing table implemented exactly as Step 4 specifies; `general_text_corpus`/
`language_pattern`/`grammar`/`conversation` → tokenizer-or-pretraining candidates,
`instruction_response`/`translation_pair`/`summarization_pair`/`correction_pair` → SFT candidates,
`stable_knowledge`/`volatile_knowledge`/`source_specific_fact` → `rag_only` (never promoted),
`evaluation_example` → `evaluation_only` (hard-blocked from training, §6), `unsafe_or_blocked` →
`blocked`. Every routing decision stores a human-readable `reason` string, surfaced verbatim by
both the API and the Admin Assistant (Step 4's "explain why each record is routed" requirement).

## 6. Transformation model (Step 5)

`TrainingExampleTransformationService.transform()` — one `training_example_candidates` row per
transformation, all Step 5 fields, `review_status` starts `pending_review` and **must** reach
`approved` (human) before a candidate is eligible for dataset promotion — no transformation is
ever auto-approved. Evaluation-only records are rejected at the API/service boundary before a
transformation attempt is even made (`evaluation_example`/Phase-13-query-set-linked records raise
immediately). Ambiguous Tamil-correction transformations default `review_status='pending_review'`
with no fast path to auto-approval, satisfying "ambiguous Tamil correction must remain
review-required" structurally, not just by convention.

## 7. Contamination recheck (Step 6) — addressing Phase 12/13's deferred gap

`TrainingContaminationService.check()` builds a **real** checksum set by querying, directly and
freshly each call (never cached): `dataset_version_items`→`dataset_records.content_hash` for every
*existing* `ready`/`archived` dataset version (training/validation/test already shipped),
`rag_sandbox_queries.query_text` checksums across every experiment (RAG sandbox query sets),
`instruction_tuning_evaluations`/`pretraining_evaluations` result sets where available, and any
table tagged as a benchmark/release-gate suite. This directly satisfies Step 6's explicit
instruction to "build actual checksum-set sourcing from existing approved dataset, RAG, and
evaluation tables" — the exact gap Phase 12/13's own reports flagged as deferred. Result vocabulary
(`clear`/`possible_overlap`/`confirmed_overlap`/`unknown`) exactly as specified; `confirmed_overlap`
against a validation/test/evaluation source hard-blocks; `unknown` (checksum set unavailable/query
failed) is stored as `unknown`, never silently coerced to `clear`.

## 8. Split policy (Step 7)

`DatasetVersioningService`'s existing `_groups()`/`_split_groups()`/`_leakage()` are reused
verbatim (source-level + content-hash grouping, seeded reproducible shuffle, leakage-blocked
build). Phase 14 supplies `selection_filters` scoped to its own newly-created `dataset_records`
(tagged via `dataset_sources.source_type='incremental_training_promotion'` and a
`metadata_json.training_dataset_promotion_request_public_id` marker) so the existing builder only
ever selects Phase-14-governed content for a given promotion — never accidentally pulling in
unrelated existing dataset records.

## 9. Replay plan (Step 8)

`TrainingReplayPlanService.create_plan()` selects replay records from **existing `ready`/`archived`
dataset versions** only (never from ungoverned tables), excluding any record whose `dataset_version`
split was `test` or whose source is tagged evaluation-only, deterministic via a stored
`selection_seed`, computing the Step 8 language/task/domain distributions from real
`dataset_records.language`/`record_type` columns. Default ratio 80% new / 20% replay (within the
recommended 70–90/10–30 band), explicitly documented as a recommendation, overridable per plan.

## 10. Immutable training dataset version (Step 9)

`TrainingDatasetPromotionService`:
1. `create_promotion_request()` — binds selected `training_example_candidates` (must all be
   `review_status='approved'`) + replay plan, mutable until Admin-approved.
2. `approve_promotion()` — separate Admin approval (Step 9's own explicit approval requirement),
   stale-checked against candidate set + replay plan fingerprint.
3. `build_dataset_version()` — only after approval: materializes each approved candidate as a real
   `dataset_records` row via `DatasetService.create_record()` (idempotent, content-hash
   deduplicated — a candidate already present as a `dataset_record` is linked, not re-inserted),
   then calls `DatasetVersioningService.create_build()`→`validate_build()`→`run_build()` scoped to
   exactly those records + replay records, producing a real, immutable, checksummed
   `dataset_versions` row through the **existing, unmodified** builder. The Phase-14 manifest
   fields (source Phase 13/12/verification-case ids, promotion request id, replay plan id,
   transformation version) are stored in `training_dataset_promotion_requests.lineage_manifest_json`,
   cross-referencing the dataset version's own real manifest — never a second competing manifest
   table.

## 11. Tokenizer compatibility (Step 10)

`TrainingResourcePreviewService._tokenizer_compatibility()` reads the target
`tokenizer_versions` row (vocabulary size, Tamil/English/Tanglish coverage fields already recorded
by Phase 5's tokenizer evaluation) and the dataset version's own `language_distribution_json`,
producing a pass/blocked verdict with a recommendation string. Phase 14 never retrains or creates a
tokenizer version itself.

## 12. Training strategy selection (Step 11) and resource preview (Step 12)

`training_strategy` one of `incremental_sft`/`continued_pretraining`/`tokenizer_only_assessment`/
`no_training_rag_only`, stored on the run request. `incremental_sft` creates an
`InstructionTuningService` experiment; `continued_pretraining` creates a `PretrainingService` job;
the other two strategies terminate the workflow at the assessment/resource-preview stage with no
job/experiment created at all (`tokenizer_only_assessment` produces only the §11 compatibility
report; `no_training_rag_only` is the direct, structural expression of "facts default to RAG" —
it creates nothing further). `TrainingResourcePreviewService.preview()` calls the underlying
service's own `estimate()`/`preflight_payload()` (§1) for the hard-enforced numeric bounds, and
adds Phase-14-only live-resource checks (disk free space via `shutil.disk_usage`, RAM via
`/proc/meminfo` parsing — no new dependency — CPU core count via `os.cpu_count()`, GPU availability
via a bounded, safe `nvidia-smi`-absence check with no shell interpolation of any content).
`execution_target` one of `local_cpu`/`cpu_vps`/`external_gpu_manual`; `external_gpu_manual`
produces a signed export manifest only *after* Training Run approval, storing no credentials and
triggering no cloud API call anywhere in this codebase (there is none to call).

## 13. Training Run approval (Step 14)

`IncrementalTrainingApprovalService` — a structurally distinct table/service from
`TrainingDatasetPromotionService`'s approval (§10 step 2). Binds all 15 Step-14 fields;
`target_fingerprint` covers dataset-version checksum + configuration checksum + resource-preview
checksum + replay-plan id + base-checkpoint id; immutable once approved except → `expired`/
`superseded`, identical trigger shape to Phase 12/13.

## 14. Incremental training execution (Step 15)

`IncrementalTrainingExecutionService.start_run()` — only callable after both the dataset
promotion is `ready` **and** a Training Run approval is `approved` and not stale/expired — creates
the real underlying `InstructionTuningService`/`PretrainingService` experiment/job (base checkpoint
= parent checkpoint for resumption, exactly as those services already support), then
`create_run()`/`queue_run()`, and drives `run_one()` synchronously in bounded, resumable stages
(no new background job system — matches "CPU-first", "synchronous or resumable staged execution
is acceptable"). `incremental_training_runs` stores `underlying_run_kind` (`instruction_tuning_run`
/`pretraining_job`) + the underlying public_id — a thin governance pointer, never a duplicate
event/metric store (events/metrics are read live from the underlying tables via existing
`events()`/`metrics()` methods, mirrored into `incremental_training_run_events` only for the
Phase-14-specific governance milestones: approval consumed, run started, run finished/failed).

## 15. Checkpoint lineage, verification, evaluation, forgetting, memorization, comparison (Steps 16–21)

`incremental_training_checkpoints` rows reference real `pretraining_checkpoints.public_id` rows
(created automatically by the underlying trainer) — one Phase-14 governance row per real
checkpoint, `status` tracking Step 16's vocabulary. `IncrementalCheckpointVerificationService`
calls `PretrainingService.verify_checkpoint()` (file/checksum/manifest verification, load-on-CPU,
NaN/Inf, shape checks — all pre-existing) and records the Phase-14 verdict.
`IncrementalTrainingEvaluationService` calls `evaluate_run()`/`language_metrics()`/
`learning_checks_for_run()` (SFT) or `evaluate()` (pretraining) and stores a Phase-14 rollup.
`IncrementalRegressionService` calls `compare_runs()`/`compare_runs` equivalents between the
candidate and a **baseline run** (the parent checkpoint's own prior training run when it exists;
otherwise the comparison is honestly marked `not_comparable`, never fabricated), classifying
`improved`/`unchanged`/`minor_regression`/`major_regression`/`not_comparable` — `major_regression`
hard-blocks checkpoint acceptance, enforced in code, not merely displayed.
`IncrementalMemorizationService` reads the same `learning_checks_for_run()` memorization-warning
signals plus a bounded train/validation loss-gap check, producing `low_risk`/`warning`/
`high_risk`/`blocked` — a checkpoint is never accepted on training-loss improvement alone (checked
structurally: `IncrementalCheckpointAcceptanceService.decide()` requires both a completed
regression check and a completed memorization check on record before "accepted"/"accepted_with_
conditions" is permitted). `IncrementalTrainingComparisonService` aggregates loss/language/
instruction/safety/leakage/memorization/checkpoint-size into one stored comparison row per
Step 21's field list.

## 16. Human review, report, acceptance (Steps 22–24)

Byte-for-byte the same shape as Phase 13's human-review/report/acceptance services (already
proven in this codebase): append-only, attributed, 10-dimension review; a report service that
recomputes everything fresh and refuses finalization while any tested prompt has zero human
review; acceptance as its own call, stale-rejected if the report or a bound checksum changed.

## 17. Model Registry handoff (Step 25)

`IncrementalModelCandidateRegistrationService.register_candidate()` — only after
`incremental_training_checkpoint_acceptances.decision` is `accepted`/`accepted_with_conditions` —
inserts one `core_model_versions` row, `lifecycle_status='staging'` (§2), tagged
`metrics_summary_json`/`architecture_summary_json` with full Phase 14 lineage (checkpoint id,
training run id, dataset version id, evaluation/comparison/report ids, human review summary,
conditions). Never sets `active`. Never calls `ModelReleaseService`.

## 18. Failure and rollback (Step 26)

Inherited for free: `PretrainingService`/`InstructionTuningService` already implement crash
recovery, lease-based worker claiming, and safe partial-checkpoint cleanup (Phase 9's training
reliability system). Phase 14 adds nothing here except recording the failure in
`incremental_training_run_events` and never advancing a failed run's governance state past
`failed` — the parent/prior approved checkpoint is never touched by a failed run, structurally
(a new run always creates a *new* checkpoint lineage node; nothing here ever deletes or overwrites
an existing `pretraining_checkpoints` row).

## 19. Phase 13 integration and inherited-limitation handling (Steps 32, 40)

From an accepted Phase 13 report: "Create Training Suitability Assessment"/"Open Existing
Assessment" buttons, bound to the report's checksum and `target_fingerprint`; a rejected sandbox or
changed report invalidates any pending promotion (checked via the same `is_stale()` pattern).
Phase 13's own documented limitations are addressed exactly as Step 40 requires: (a) resource-bound
constants are hard-enforced here (§12, via the pre-existing `_enforce_config()` plus new live
disk/RAM checks — Phase 14's own API layer rejects before any job/experiment is created); (b) real
contamination checksum sourcing is implemented (§7); (c) Phase 13's citation-conflict-scoring gap is
never depended upon — training-suitability routing (§5) does not read `rag_sandbox_citations`
`unsupported`/`conflicting` statuses at all, only the coarser, already-reliable Phase 13 acceptance
decision and record-level contamination flag; (d) `rag_sandbox_approvals.expires_at` being nullable
is immaterial here since Phase 14 only ever reads an **accepted** (already-finalized) Phase 13
report, past the approval-expiry-relevant stage entirely.

## Phase 15 handoff

Phase 14 produces `core_model_versions` rows in `lifecycle_status='staging'` only — nothing more.
Phase 15 (or whatever governs production release) must consume them through its own, entirely
separate approval gate (`ModelReleaseService`'s existing `create_candidate`/`assess_eligibility`
pipeline, invoked manually by a human Admin, never automatically by this phase).
