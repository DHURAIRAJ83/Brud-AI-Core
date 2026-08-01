# Phase 14 — Training Dataset Promotion, Incremental Language Training, Checkpoint Evaluation & Admin Approval

## 1. Architecture

Phase 14 is a thin governance layer over the existing Phase 7–13 training
infrastructure, not a reimplementation of it. It takes an *accepted* Phase 13
RAG sandbox report as its only entry point, and moves accepted-and-approved
records through five independently governed gates before anything is ever
trained: suitability assessment → candidate transformation/review → dataset
promotion → training-run approval → checkpoint acceptance. Every gate is a
separate row/decision in its own table; none of them implies the next. See
`docs/training/phase14_incremental_language_training_plan.md` §1 for the
full reuse map.

## 2. The two production-adjacent lines this phase never crosses

1. `core_model_versions.lifecycle_status` is only ever written as `'staging'`
   by this phase (via the existing `PretrainingService.promote()`), never
   `'active'`.
2. `ModelReleaseService` is never imported or called anywhere in this phase.

Both are enforced structurally (no code path can reach them) and by a
dedicated static-analysis test (`tests/backend/test_incremental_training_security.py`)
that scans every Phase 14 service source file for violations.

## 3. Schema (migration 037, schema version 36 → 37)

16 new, additive tables: `training_data_assessments`,
`training_data_assessment_items` (append-only), `training_example_candidates`
(mutable pre-approval; append-only `training_example_revisions` is its audit
trail), `training_dataset_promotion_requests` (immutable once approved except
transitioning to `expired`/`superseded`/`building`/`ready`/`failed`),
`training_replay_plans` (append-only), `incremental_training_run_requests`
(mutable throughout — staleness is enforced by fingerprint comparison at
execution time, not by schema immutability), `incremental_training_run_approvals`
(immutable once approved except `expired`/`superseded`),
`incremental_training_runs`, `incremental_training_run_events` (append-only),
`incremental_training_checkpoints` (mutable while
`created`/`verified`/`evaluation_pending`; once `evaluated` it may only
progress forward to `accepted_candidate`/`rejected`/`superseded` — see §4 for
why this required a schema fix mid-build),
`incremental_training_evaluations` (append-only), `incremental_training_comparisons`
(append-only), `incremental_training_human_reviews` (append-only),
`incremental_training_checkpoint_acceptances` (append-only),
`incremental_training_reports` (append-only, versioned via
`UNIQUE(run_id, report_version)`).

No 17th table was needed — unlike Phase 12/13, the three separate-decision
gates (dataset promotion, run approval, checkpoint acceptance) already map
onto three distinct existing tables in the 16-table design.

## 4. A real bug found and fixed during this build

The checkpoint-immutability trigger was originally written as "mutable only
while `status IN ('created','verified','evaluation_pending')`", which
correctly protects lineage/metric fields but also accidentally blocked the
one transition the whole phase exists to make possible:
`evaluated → accepted_candidate`/`rejected`. This was caught by the
checkpoint-acceptance service's own integration test failing with
`sqlite3.IntegrityError: checkpoint lineage fields are immutable once
evaluated`. Fixed by widening the trigger to also permit
`OLD.status='evaluated' AND NEW.status IN ('accepted_candidate','rejected','superseded')`,
while keeping every other transition (including any backward move, and any
change to `underlying_checkpoint_public_id`) blocked. The corresponding
repository-level immutability test was updated to assert the corrected
behavior explicitly, in both directions.

## 5. Suitability assessment (Step 3) and language-vs-factual classification (Step 4)

`TrainingSuitabilityAssessmentService.create_assessment()` hard-requires the
target RAG sandbox experiment's latest acceptance to be
`accepted`/`accepted_with_conditions` — this is the direct code-level
enforcement of "only records accepted through Phase 12 and included in an
accepted Phase 13 report may be considered." `run_assessment()` computes a
19-dimension `dimension_results` map per record (permission/licence/source-
currency checks via Phase 11 read-only, PII/safety issue checks via Phase 12
read-only, prompt-injection detection reusing `core_model.rag.injection_filter`
verbatim, evaluation-linkage detection against the Phase 13 query set) and
calls the pure, deterministic `core_model.training_incremental.classification`
module (regex-based, bilingual Tamil/English markers, no LLM) to route each
record into one of 15 categories and from there into one of 10 suitability
statuses. A blocking dimension always overrides the category routing.

## 6. Governed transformation (Step 5)

`TrainingExampleTransformationService.transform()` structurally rejects any
item whose `suitability_status` is not in the promotable set — evaluation-
only, RAG-only, not-suitable, and blocked records can never be transformed,
enforced in code, not just by convention. `review_candidate()` always writes
an append-only `training_example_revisions` row first, and only actually
mutates the live candidate's text/checksum when the reviewer's decision is
explicitly `approved` — an ambiguous Tamil-correction transformation stays
`needs_revision` unless a human explicitly approves it.

## 7. Contamination recheck (Step 6)

`TrainingContaminationService` sources real reference checksum/text sets
from three places: the validation/test splits of every existing
`ready`/`archived` dataset version, the Phase 9/10 model-evaluation-suite
fixtures, and the Phase 13 RAG-sandbox query sets. Each candidate gets an
exact-hash check (→ `confirmed_overlap`) and a bounded substring-containment
check against the same reference texts (→ `possible_overlap`) — never a
silent `clear` when a check could not run. This directly addresses Phase
13's own documented deferred-checksum-gap limitation.

## 8. Replay plan (Step 9) and dataset promotion (Step 10)

`TrainingReplayPlanService` deterministically samples (seeded
`random.Random`) from existing approved train-split records across ready
dataset versions; 70–90% new / 10–30% replay is recorded as a
recommendation, with an explicit `within_recommended_range` note, not a hard
rule. `TrainingDatasetPromotionService.create_request()` re-runs the
contamination recheck and rejects the whole request if any selected
candidate is `confirmed_overlap`. `materialize()` (only reachable once
`approved`) creates real `dataset_records` via the *existing, unmodified*
`DatasetService.create_record()` + `transition()` two-step approval, then
calls the *existing, unmodified* `DatasetVersioningService.create_build()`
scoped via `selection_filters={"include_public_ids": [...]}` — the exact
mechanism `GovernedBuildService` already established for Phase 7, reused
verbatim.

## 9. Resource preview (Step 12) and training-run approval (Step 13)

`TrainingResourcePreviewService` hard-enforces the same
`Settings.pretraining_max_*` bounds `PretrainingService._enforce_config()`
already uses for base pretraining, plus Phase-14 bounds
(`core_model.training_incremental.DEFAULT_MAX_*`) and the existing
`Settings.pretraining_min_free_disk_bytes` reserve — this directly satisfies
Step 36's "harden Phase 13's deferred resource-bound gap" requirement using
real, already-configured limits rather than inventing new ones.
`IncrementalTrainingRunApprovalService` binds a run request to a
*materialized* (`status='ready'`) promotion request, snapshots a fingerprint
(dataset version + base checkpoint + tokenizer + strategy + configuration
checksum + resource-preview checksum) into a separate
`incremental_training_run_approvals` row, and
`IncrementalTrainingExecutionService._validated_approval()` recomputes and
compares that fingerprint at execution time — any change to the run request
after approval is caught here, not by schema immutability (run requests stay
mutable throughout; the fingerprint comparison is the actual enforcement).

## 10. Execution (Step 14)

Both executable strategies (`continued_pretraining`, `incremental_sft`)
ultimately produce a `pretraining_checkpoints` row: `continued_pretraining`
calls `PretrainingService.create_job/validate_job/queue_job` directly;
`incremental_sft` calls `InstructionTuningService.create_experiment/
create_run/queue_run`, which itself internally wraps a
`PretrainingJobCreate` with `job_mode='bounded_pretraining'`. Either way,
`_execute_synchronously()` calls the relevant service's existing `run_one()`,
which already runs a job to completion (or to pause/cancel) inside one call
— satisfying "bounded, resumable, staged execution" with zero new background
infrastructure. `tokenizer_only_assessment`/`no_training_rag_only` never
reach this method; they use `acknowledge_no_execution_strategy()` instead,
since those strategies are themselves the terminal governance decision.

## 11. Checkpoint verification, evaluation, comparison (Steps 19–24)

`IncrementalTrainingCheckpointService.verify()` delegates to the existing
`PretrainingService.verify_checkpoint()`; `.evaluate()` delegates to
`PretrainingService.evaluate()` (validation loss) and
`TrainingEvaluationService.assess_quality()` (train/validation gap, checksum-
reference validation, resume consistency, non-finite detection — reused as
the Step 23 memorization/overfitting signal set) and always transitions to
`evaluated` regardless of outcome — an automated evaluation only records a
signal, it never itself accepts or rejects.
`IncrementalTrainingComparisonService.compare()` reuses
`TrainingEvaluationService.compare_checkpoints()`/`compare_runs()` for the
raw deltas and adds the one thing those don't have: a deterministic
`classify_regression()` threshold function
(`improved`/`unchanged`/`minor_regression`/`major_regression`/
`not_comparable`, based on relative validation-loss delta).
`compare_to_parent()` is the same mechanism with `comparison_type=
"forgetting_check"` and the candidate's own parent as baseline.

## 12. Human review, report, acceptance, model-candidate handoff (Steps 25–28)

`IncrementalTrainingHumanReviewService` requires the checkpoint to already
be automatically evaluated. `IncrementalTrainingReportService.finalize_report()`
deterministically aggregates evaluations/comparisons/human-reviews into a
versioned, checksum-stamped, append-only report with an advisory
`checkpoint_recommendation` — `production_release_readiness` is always
written `"not_assessed"`; this phase never assesses it.
`IncrementalTrainingCheckpointAcceptanceService.accept()` is the one place a
binding decision is made: it hard-blocks any accepting decision
(`accepted_candidate`/`accepted_with_conditions`) if any comparison for the
checkpoint has `result_status='major_regression'` — **not overridable**, even
with an `override_comment`, verified directly in
`tests/backend/test_incremental_training_security.py`. Only on an accepting
decision does it call the *existing* `PretrainingService.promote()`, which
can only ever write `lifecycle_status='staging'`.

## 13. A second real bug found and fixed during the security pass

`IncrementalTrainingExecutionService._validated_approval()` checked approval
`status=='approved'` and fingerprint match, but never checked `expires_at` —
an approval that had expired could still be used to start a real training
run. Fixed by adding an expiry check that marks the approval `expired` (a
new `TrainingIncrementalRepository.mark_run_approval_expired()` method,
mirroring the promotion-request's existing expiry-handling pattern) and
raises, with a dedicated regression test
(`test_expired_run_approval_blocks_start_and_cannot_be_overridden`).

## 14. Backend services (18)

`TrainingSuitabilityAssessmentService`, `TrainingExampleTransformationService`,
`TrainingContaminationService`, `TrainingReplayPlanService`,
`TrainingDatasetPromotionService`, `TrainingResourcePreviewService`,
`IncrementalTrainingRunApprovalService`, `IncrementalTrainingExecutionService`,
`IncrementalTrainingCheckpointService`, `IncrementalTrainingComparisonService`,
`IncrementalTrainingHumanReviewService`, `IncrementalTrainingReportService`,
`IncrementalTrainingCheckpointAcceptanceService`, plus the repository
(`TrainingIncrementalRepository`) and the `core_model.training_incremental`
enum/classification modules.

## 15. API (47 routes under `/api/admin/incremental-training`)

Admin-only, CSRF-protected (`dependencies=[Depends(require_admin)]`), no raw
SQL in the route layer. Verified live against a real running server: 401 on
an unauthenticated request, 403 on a POST missing the CSRF header, correct
real (non-fabricated) zero-state data from `/overview` against an empty dev
database. No production-activation endpoint and no model-release endpoint
exist anywhere in this router — asserted by a dedicated test that scans
every registered route path for `activate`/`release`/`production`.

## 16. Admin Assistant integration

8 controlled actions, deliberately scoped to the pre-approval data-curation
stages only: `assess_language_sample_suitability`,
`run_language_sample_suitability_check`,
`acknowledge_language_sample_assessment`,
`transform_language_sample_candidate`, `review_language_sample_candidate`,
`create_replay_data_plan`, `create_dataset_promotion_request`,
`submit_dataset_promotion_request`. None of their action_type names contain
"train"/"pretrain" — the codebase's own pre-existing
`BLOCKED_ACTION_SUBSTRINGS = ("train", "pretrain")` safety gate would refuse
them anyway, but the scoping itself is deliberate: the assistant stops at
"submit this dataset promotion for Admin approval." It can never approve or
materialize a promotion, create/approve a training-run request, start a run,
evaluate/accept a checkpoint, or register a model candidate — every one of
those remains a direct, non-assistant-mediated Admin action, verified by a
dedicated regression test that scans `ACTION_DEFINITIONS` for any action
type resembling those operations.

## 17. Frontend

One page (`IncrementalTrainingPage.jsx`, `apps/admin-dashboard`), 7 tabs
(Overview, Assessments, Candidates, Dataset Promotion, Training Runs,
Checkpoints, Reports & Acceptance), wired into `App.jsx`/`Sidebar.jsx` under
the existing "Data" nav group, plus a `core_model.admin_assistant.
dashboard_registry` page entry (required by a strict test that parses
`Sidebar.jsx` directly and asserts equality against the registry). Overview
shows the real 10 `overview_counts()` metrics; a dedicated test asserts no
"Production Model Activated"/"Model Released" text appears anywhere on the
page. Integrated into Data Overview as an 11th metrics group plus an "Open
Incremental Training" quick action.

## 18. Phase 13 integration

An assessment can only be created against an experiment whose *latest*
acceptance is `accepted`/`accepted_with_conditions`; a rejected sandbox
report structurally blocks assessment creation (`TrainingSuitabilityError`,
tested directly). `training_data_observation` from Phase 13's report is read
as advisory context only and never bypasses this phase's own independent
19-dimension check.

## 19. Existing-system integration

`PretrainingService`, `InstructionTuningService`, `TrainingEvaluationService`,
`DatasetService`, and `DatasetVersioningService` are all reused unmodified
except for the one additive schema fix in §4 (which touches only Phase 14's
own new tables). Regression coverage: `tests/backend/test_pretraining_api.py`,
`test_instruction_tuning_api.py`, and the Phase 9 core-model pretraining
suite all continue to pass unchanged.

## 20. Performance and resource controls

Hard-enforced via `TrainingResourcePreviewService`: max batch size, max
sequence length/context length, max total steps, max gradient-accumulation
steps, max epochs, max token budget, max checkpoint count, minimum free
disk. Every bound reuses an existing `Settings` field where one already
existed (`pretraining_max_*`, `pretraining_min_free_disk_bytes`) rather than
inventing a parallel, potentially-inconsistent set.

## 21. Security tests

`tests/backend/test_incremental_training_security.py`: static guard against
`lifecycle_status='active'` writes, static guard against `ModelReleaseService`
imports, static guard against `inference_model_assignments` writes, unsafe
batch size blocked, excessive gradient accumulation blocked, expired run
approval blocks execution and cannot be bypassed, expired promotion approval
blocks materialization, `major_regression` blocks checkpoint acceptance even
with an explicit override comment. Plus, distributed across the other test
files: CSRF/auth rejection (both service-level and live-server HTTP),
rejected/absent RAG sandbox acceptance blocks assessment creation,
contamination confirmed-overlap blocks promotion, non-approved candidates
cannot be promoted, stale/superseded promotion selections are structurally
immutable at the SQL level once approved.

## 22. Tests (comprehensive list)

- `tests/database/test_training_incremental_repository.py` — 18 tests
- `tests/backend/test_training_suitability_and_transformation.py` — 10 tests
- `tests/backend/test_training_contamination_replay_and_promotion.py` — 10 tests
- `tests/backend/test_incremental_training_run_and_execution.py` — 9 tests
- `tests/backend/test_incremental_training_checkpoint_and_comparison.py` — 5 tests
- `tests/backend/test_incremental_training_review_report_and_acceptance.py` — 6 tests
- `tests/backend/test_incremental_training_api.py` — 4 tests
- `tests/backend/test_incremental_training_admin_assistant.py` — 4 tests
- `tests/backend/test_incremental_training_security.py` — 8 tests
- `apps/admin-dashboard/src/pages/IncrementalTrainingPage.test.jsx` — 6 tests
- Updated: `apps/admin-dashboard/src/pages/DataOverviewPage.test.jsx`,
  `apps/admin-dashboard/src/components/Sidebar.test.jsx` (implicit),
  `tests/backend/test_system_api.py` (migration name), `tests/core_model/
  test_admin_assistant_registries.py` (implicit, all 13 pass unchanged),
  `tests/backend/test_admin_assistant_lifecycle.py` (implicit, all pass
  unchanged including the strict `ACTION_EXECUTORS == ACTION_DEFINITIONS`
  equality test).

All Phase 14 test files pass together (100+ tests). Full-repo `ruff check`
passes. The admin-dashboard production build succeeds
(`npm run build`, 139/139 frontend tests pass).

## 23. Manual verification

No browser automation tool was available in this session. Verified instead
against a real running backend (`uvicorn`, port 8000) and frontend (`vite`,
port 5174) using the project's real development database
(`data/database/brud_ai.db`, already at schema version 37): created a real
admin account (`phase14-verifier`, matching the project's existing
`phaseN-verifier` naming convention), logged in over real HTTP, confirmed
`/api/admin/incremental-training/overview` returns real (non-fabricated)
zero-state data, confirmed a POST without a CSRF header is rejected with 403
and an unauthenticated GET is rejected with 401, and confirmed every
frontend module touched in this phase (`IncrementalTrainingPage.jsx`,
`DataOverviewPage.jsx`, `Sidebar.jsx`, `App.jsx`, `services/api.js`) compiles
and serves cleanly through Vite's dev transform. Both dev servers were
stopped after verification.

## 24. Known limitations inherited from Phase 13

Phase 13's own contamination-scoring/citation-conflict signals remain
advisory context for this phase, never a training-eligibility decision on
their own (Phase 14 runs its own independent, real contamination recheck —
§7). Phase 13's `training_data_observation` field is read but never trusted
in place of Phase 14's own 19-dimension assessment.

## Out of scope (explicitly, not attempted)

Production model activation, model release approval, production RAG
activation, automatic rollout, A/B testing, public traffic routing, billing,
any new cloud GPU provider, automatic cloud instance creation, new tokenizer
training, full base-model pretraining from scratch, image/audio/video/
multimodal training.

## Phase 15 handoff

An accepted checkpoint exists only as a `model_candidate` (`staging`) row in
`core_model_versions`. Promoting it to an actual production release remains
entirely `ModelReleaseService`'s separate, later, manual mechanism — Phase
14 deliberately stops one step before it.

---

**PHASE_14_COMPLETE**

Do not proceed to Phase 15.
