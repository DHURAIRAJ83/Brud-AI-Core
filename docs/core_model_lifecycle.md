# Core Model Lifecycle

## Family, config, version

A family is a logical model line. A config is a deterministic validated architecture configuration tied to a registered tokenizer. A version combines a family, config, initialization seed, lifecycle state, checkpoints, and check evidence.

## Lifecycle

```text
draft → initialized → architecture_verified → smoke_tested → staging → active
```

Failures move to `failed`; active/staging versions can retire.

## Assignments

Phase 8 assignments are architecture-only:

- `architecture_default`
- `smoke_training_default`
- `future_pretraining_base`

There is no `public_chat` assignment in Phase 8 or Phase 9.

## Phase 9 promotion

A verified completed pretraining checkpoint may be promoted into a new staging model version labeled `base_pretrained`, `not_instruction_tuned`, and `not_chat_ready`. Promotion preserves the source architecture version, tokenizer reference, dataset reference through the pretraining job, and checkpoint checksum evidence. It does not make the model a chatbot model.

## Phase 11 candidate selection

Phase 11's `base_training_service.select_candidate()` calls this same
promotion path — it does not add a second promotion mechanism. A base
training candidate can only be `selected_base_candidate` or
`selected_with_warnings` (never a plain "selected") after passing both
Phase 10's training-process quality gate and Phase 11's language/
generalization learning checks; a candidate that fails either is
`rejected` and never promoted. Every promoted candidate still carries
`not_instruction_tuned: true` and `not_chat_ready: true`, and no phase
before or including Phase 11 assigns any model version to the
`public_chat` assignment key. See
[base_training_candidate_selection.md](base_training_candidate_selection.md).

## Phase 12 instruction-tuned lineage

Phase 12's `instruction_tuning_service.select_candidate()` promotes into a
**new** `core_model_versions` row (new lineage; the base model row and its
checkpoint file are never modified) carrying
`{"base_pretrained": true, "instruction_tuned": true, "evaluation_required": true,
"not_public_chat_ready": true, "source_experiment_public_id": ..., "source_base_model_public_id": ...}`,
`lifecycle_status = "staging"`. Only a base candidate produced by Phase 11
(`lifecycle_status IN ('staging','active')` and
`architecture_summary_json.base_pretrained == true`, with a verified
checkpoint) is eligible as an instruction-tuning source; an already
instruction-tuned model cannot be selected as a Phase 12 source. Candidate
status is `instruction_tuned_candidate` or `instruction_tuned_with_warnings`
(never a plain "selected"), or `rejected`. No phase up to and including
Phase 12 assigns any model version to the `public_chat` assignment key. See
[instruction_candidate_selection.md](instruction_candidate_selection.md).

## Phase 13 evaluation (no new lineage row)

Phase 13 does not promote a new `core_model_versions` row and does not
change lifecycle status. It reads an existing Phase-12-promoted row
directly — eligibility is `lifecycle_status IN ('staging','active')` and
`architecture_summary_json.base_pretrained`, `.instruction_tuned`, and
`.evaluation_required` all `true`, with a verified checkpoint (matched by
`model_checksum_sha256` against the candidate's own
`weights_checksum_sha256`) — and records its findings entirely in the new
`model_evaluation_*` tables. The candidate's `architecture_summary_json`
is never rewritten by Phase 13, so `not_public_chat_ready` stays exactly
as Phase 12 set it, and the readiness gate's outcome
(`evaluation_passed_with_limits`/`evaluation_warning`/`evaluation_blocked`)
is recorded as a separate, append-only assessment — never as a lifecycle
transition. No phase up to and including Phase 13 assigns any model
version to the `public_chat` assignment key. See
[chat_readiness_assessment.md](chat_readiness_assessment.md).

## Phase 14 release registry (also no new lineage row)

Phase 14 likewise never rewrites a `core_model_versions` row or its
lifecycle status. A release candidate references an existing core model
version, its resolved checkpoint, and (when relevant) its instruction-
tuning candidate and evaluation run entirely by foreign key — release-
candidate status (`draft`/`.../blocked`/`approved`/`released`/...) and
release status (`draft`/`released`/`deprecated`/`retired`/`rolled_back`/
`archived`) live on the new `model_release_candidates`/`model_releases`
tables, completely separate from `core_model_versions.lifecycle_status`,
`instruction_tuning_candidates.status`, and
`model_chat_readiness_assessments.status`. A core model version with
`lifecycle_status` of `retired`, `archived`, or `failed` is rejected
outright at candidate-creation time — it can never become a release
candidate regardless of its evaluation history. Deployment eligibility
(`deployable`/`deployable_with_warnings`/`not_deployable`) is yet another
separate field, on `model_releases`, and is never conflated with release
status or evaluation status. No phase up to and including Phase 14
assigns any model version to the `public_chat` assignment key, and no
release is ever created for a candidate whose evaluation status is
`evaluation_blocked`. See
[model_release_eligibility.md](model_release_eligibility.md).

## Phase 15 inference runtime (also no new lineage row, no lifecycle change)

Phase 15 never rewrites a `core_model_versions` row, its lifecycle
status, or the Phase 14 release/candidate rows it reads. A model
assignment (`inference_model_assignments`) references an existing
`model_releases` row entirely by foreign key, and re-derives evaluation
readiness **live** from `model_chat_readiness_assessments` at every
eligibility check rather than caching it — so a release that was
eligible when created can still be correctly rejected for assignment if
a later append-only readiness assessment reveals a blocking issue.
Runtime instance status, assignment status, and public-chat activation
are three more separate fields, on three different tables, never
conflated with release status, deployment eligibility, or evaluation
status. No phase up to and including Phase 15 assigns any model version
to the `public_chat` assignment key, and no runtime instance ever loads
a release whose evaluation status is `evaluation_blocked` or whose
deployment eligibility is `not_deployable`. See
[inference_runtime_architecture.md](inference_runtime_architecture.md)
and [model_assignment_lifecycle.md](model_assignment_lifecycle.md).

## Phase 16 RAG (no new lineage row, no new inference runtime)

Phase 16 never rewrites a `core_model_versions` row and never loads a
model directly. `RagGenerationService` re-derives the same live
registry-fixture and evaluation-blocked checks Phase 15 already
performs (via `InferenceRuntimeService.gather_release_facts()`) before
every grounded-answer or RAG Chat Lab call, and delegates the actual
load/generate step to `ModelAssignmentService.ensure_instance_loaded()`
and `InferenceRuntimeService.run_generation()` unchanged. RAG generation
reuses the existing `admin_diagnostic` assignment scope rather than
adding a new one — see [database_schema_v16.md](database_schema_v16.md)
and [rag_architecture.md](rag_architecture.md).

## Phase 17 conversation memory (no new lineage row, no new inference runtime)

Phase 17 also never rewrites a `core_model_versions` row and never
loads a model directly. `ChatOrchestrationService` performs the same
assignment verification pattern as `RagGenerationService`
(`_verify_assignment()` re-checks scope, status, registry-fixture, and
evaluation-blocked facts on every message) and calls the identical
`ModelAssignmentService.ensure_instance_loaded()` /
`InferenceRuntimeService.run_generation()` pair — no second runtime,
no second loader, no new assignment scope. Conversation memory itself
(policies, sessions, consent, memory items) is a layer entirely above
the model lineage: it governs what context a generation call receives,
never which model or checkpoint is used. See
[database_schema_v17.md](database_schema_v17.md) and
[chat_orchestration_architecture.md](chat_orchestration_architecture.md).

## Phase 18 feedback pipeline (no new lineage row, no new inference runtime)

Phase 18 never rewrites a `core_model_versions` row either. Regression
execution (`RegressionEvaluationService.execute_run()`) reuses the
identical `ModelAssignmentService.ensure_instance_loaded()` /
`InferenceRuntimeService.run_generation()` pair, requiring an
`admin_diagnostic`-scope assignment exactly like RAG generation and
chat orchestration before it — no second runtime, no second loader, no
new assignment scope. A feedback subject snapshot
(`feedback_subjects`) records which model release/version/checkpoint a
piece of feedback is about via checksums and public-ID references
only — it never touches or reinterprets the lineage row itself. See
[database_schema_v18.md](database_schema_v18.md) and
[feedback_regression_suites.md](feedback_regression_suites.md).
