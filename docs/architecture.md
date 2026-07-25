# Architecture

Brud AI is a modular monorepo with three product surfaces and a shared backend. The boundaries are intentional: frontend code never imports backend or model internals, and the backend depends only on the public model contract when model work begins.

## Chatbot

The Vite/React chatbot is a stateless Phase 1 client. It checks `GET /api/health`, submits validated text and a language preference to `POST /api/chat`, and renders loading and failure states. The development server proxies `/api` to the local backend. Persistence and real inference are deferred.

## Backend runtime

FastAPI is assembled by `create_app`. Its lifespan initializes SQLite after startup rather than during module import. Routes are grouped below `/api`, CORS accepts only the two configured local origins, and centralized handlers prevent accidental internal-error disclosure. Logs are JSON objects suitable for later collection.

## Core Model

`core_model` defines stable contracts for `TokenizerManager`, `ModelConfig`, `ModelTrainer`, `InferenceEngine`, `ModelEvaluator`, and `ModelExporter`. Every unavailable operation raises `NotImplementedError`. `ModelStatus` describes the future lifecycle without pretending a model exists.

## Admin Dashboard

The separate Vite/React admin application has an unauthenticated login boundary and a responsive protected dashboard. Session state is held by an HttpOnly cookie; a separately issued CSRF value is kept only in page memory and sent on mutations. Dataset tabs provide overview metrics, manual sources, editable draft/pending records, a review queue, duplicate conflicts, and review history. Other product areas remain explicit placeholders.

```text
Admin Dashboard
      ↓ cookie session + CSRF
Authentication dependency
      ↓ authenticated admin context
Dataset API → Dataset services → Repositories → SQLite
```

Routes translate validated inputs and controlled errors. Lifecycle, duplicate, and transaction rules live in the service/repository layers rather than React or route handlers.

Phase 4 extends that boundary with a preview-first pipeline:

```text
Multipart upload → controlled artifact storage → format parser
      → conservative normalization → canonical record validation
      → duplicate analysis → persisted preview
      → explicit admin confirmation → transactional draft records
```

Uploaded bytes are never executed or served as static assets. Parsers, normalization, mapping, duplicate analysis, and confirmation live in backend services; the route and React layers only transport validated choices and render safe summaries.

Phase 6 adds the quality and versioning control plane:

```text
Approved records → deterministic quality evidence → build validation
      → grouped deterministic split → immutable version items
      → manifest + checksum → UTF-8 JSONL export
```

Quality scoring, leakage checks, split generation, manifest serialization, and export writing are backend service concerns. React renders summaries and triggers explicit admin actions.

Phase 7 adds the tokenizer control plane:

```text
Ready dataset version → deterministic UTF-8 corpus → dry-run validation
      → bounded SentencePiece training → registered artifacts
      → deterministic evaluation → staging → explicit activation
```

Tokenizer corpus building, training, evaluation, artifact verification, activation, assignment, and export live in backend services. The Admin Dashboard exposes these operations under the Tokenizer area. The chatbot is not connected to tokenizers in Phase 7.

Phase 8 adds the Brud Core architecture foundation:

```text
Registered tokenizer → validated Micro/Tiny config → PyTorch model allocation
      → forward/backward checks → safe checkpoint round trip
      → tiny overfit smoke test → staging architecture default
```

The model is a decoder-only Transformer with token embeddings, RMSNorm, RoPE, causal self-attention, SwiGLU blocks, final RMSNorm, and a language-model head. Random or smoke-tested weights are explicitly not presented as chat-capable models.

Phase 9 adds bounded base-pretraining:

```text
Ready dataset version → deterministic token blocks → queued pretraining job
      → separate local worker → AdamW + scheduler training loop
      → metrics + validation → optimizer-aware checkpoints
      → explicit base-pretrained staging promotion
```

The worker is launched with `python -m backend.training_worker`. It claims at most one queued job, persists metrics and events, checks pause/cancel flags at safe boundaries, writes registered checkpoints, and can resume from the latest job checkpoint. CPU remains the default device, and public chat stays disconnected.

Phase 10 adds training reliability, recovery, and dataset coverage on top of the same worker and service:

```text
Admin Dashboard
      ↓
Pretraining API → Pretraining Reliability / Worker Recovery / Training Evaluation services
      ↓
Worker Lease Manager (lease generation fencing on pretraining_jobs)
      ↓
Tokenizer-backed Dataset Stream → Coverage + Stream Manifest
      ↓
Trainer (periodic checkpoints via on_checkpoint)
      ↓
Checkpoint Manager → Recovery Validator (never resumes an unverified checkpoint)
      ↓
Training Evaluation (run summary, safe perplexity, quality gates)
      ↓
Quality Gate → Model Promotion (blocking issues cannot be overridden)
```

The worker heartbeats and its job lease are tracked in `worker_heartbeats` and
`training_worker_leases`; `pretraining_jobs.lease_generation` is the fencing
token that makes a stale worker's writes provably rejected after a takeover.
Coverage, stream manifests, recovery attempts, run summaries, quality
assessments/issues, and comparisons are all append-only evidence tables. See
[pretraining_architecture.md](pretraining_architecture.md),
[training_worker_leases.md](training_worker_leases.md),
[training_crash_recovery.md](training_crash_recovery.md),
[training_dataset_coverage.md](training_dataset_coverage.md),
[training_stream_manifest.md](training_stream_manifest.md),
[training_quality_gates.md](training_quality_gates.md),
[training_run_comparison.md](training_run_comparison.md), and
[checkpoint_retention.md](checkpoint_retention.md) for the full detail. No
instruction tuning, RAG, quantization, GGUF export, or distributed training
was added in this phase; the public chatbot remains an unchanged placeholder.

Phase 11 asks a different question than Phase 9/10: not "did training run
reliably", but "did the model learn anything resembling language patterns
from representative data":

```text
Representative dataset version → deterministic dataset profile + warnings
      → tokenizer suitability decision (reuse / retrain / blocked)
      → base training experiment → one or more comparable runs
        (each run = one existing Phase 9 pretraining_jobs row, reused)
      → per-language (Tamil/English/Tanglish/Mixed/Overall) evaluation
        against fixed, never-trained-on held-out fixtures
      → learning checks (11 fixed pass/warning/fail checks)
      → generalization classification (never stronger than the evidence)
      → candidate selection (still not_instruction_tuned, not_chat_ready)
      → reproducibility manifest with a SHA-256 checksum
```

`BaseTrainingService` (`backend/services/base_training_service.py`) does not
train anything itself — it builds `PretrainingJobCreate` payloads for the
existing `PretrainingService` and calls Phase 10's
`TrainingEvaluationService` for run comparison and training-process quality
gating. The only new pure-function modules are under
`core_model/training/`: `dataset_profile.py`, `language_evaluation.py`,
`learning_checks.py`, and `fixed_eval_fixtures.py`. See
[base_training_dataset_profile.md](base_training_dataset_profile.md),
[base_training_experiments.md](base_training_experiments.md),
[base_training_language_evaluation.md](base_training_language_evaluation.md),
[base_training_generalization.md](base_training_generalization.md),
[base_training_candidate_selection.md](base_training_candidate_selection.md),
and [base_training_reproducibility.md](base_training_reproducibility.md).
No instruction tuning, chatbot inference, RAG, quantization, GGUF export, or
distributed training was added in this phase; a base-pretrained candidate
is never assigned to the public chatbot, which remains the unchanged
placeholder.

Phase 12 answers the next question: not "does the model show generalization
evidence" (Phase 11), but "can it be taught to follow instructions and
respond only as the assistant":

```text
Verified Phase 11 base-pretrained candidate + its checkpoint
      → approved instruction dataset (instruction/chat/translation/
        tanglish_pair/safety; preference records validated but excluded)
      → versioned instruction template (checksum, tokenizer-compatible)
      → response-only label masking (system/user/padding → ignore_index)
      → instruction-tuning experiment → one or more comparable SFT runs
        (each run = one existing Phase 9 pretraining_jobs row, reused;
         worker dispatch isolation prevents either worker claiming the
         other's job type)
      → per-language response-only loss + bounded fixture-based structural
        checks (leakage, repetition, memorization)
      → learning checks (12 fixed pass/warning/fail checks)
      → candidate selection (still evaluation_required, not_public_chat_ready)
      → reproducibility manifest with a SHA-256 checksum, including
        base-checkpoint-unchanged proof
```

`InstructionTuningService` (`backend/services/instruction_tuning_service.py`)
does not train anything itself in the sense of adding a second model or
optimizer — it builds `PretrainingJobCreate` payloads for the existing
`PretrainingService` and calls a new sibling trainer function,
`core_model.training.trainer.run_instruction_tuning()`, that reuses the same
optimizer/scheduler/checkpoint/pause/cancel machinery as
`run_pretraining()` and differs only in consuming precomputed response-only
labeled examples. The new pure-function modules live under
`core_model/instruction_tuning/`: `dataset_validator.py`, `templates.py`,
`formatter.py`, `label_masking.py`, `batch_builder.py`, `evaluation.py`,
`language_checks.py`, `memorization_checks.py`, `learning_checks.py`,
`generation.py`, and `fixed_eval_fixtures.py`. See
[instruction_dataset_profile.md](instruction_dataset_profile.md),
[instruction_templates.md](instruction_templates.md),
[instruction_label_masking.md](instruction_label_masking.md),
[instruction_tuning_training.md](instruction_tuning_training.md),
[instruction_language_evaluation.md](instruction_language_evaluation.md),
[instruction_leakage_checks.md](instruction_leakage_checks.md),
[instruction_candidate_selection.md](instruction_candidate_selection.md),
and [instruction_reproducibility.md](instruction_reproducibility.md).
No public chatbot inference, RLHF, DPO, reward modeling, RAG, tool calling,
web search, quantization, GGUF export, or external model providers were
added in this phase; an instruction-tuned candidate is never assigned to
the public chatbot, which remains the unchanged placeholder.

Phase 13 answers the next question: not "can it be taught to follow
instructions" (Phase 12), but "how well does this instruction-tuned
candidate actually behave across supported languages and safety
conditions":

```text
Verified Phase 12 instruction-tuned candidate (base_pretrained +
instruction_tuned + evaluation_required, staging/active) + its checkpoint
      → admin-authored, versioned evaluation suite (generation policy,
        automated thresholds, human-review rubric, readiness-gate config)
      → admin-authored fixture set (20 categories × ta/en/tgl/mixed,
        never hardcoded content) → suite activation
      → evaluation run: bounded greedy generation over every fixture
        (reusing Phase 12's generate_greedy() and render_example()
         unchanged, no sampling, no new decoding loop)
      → per-fixture checks: language compliance, instruction following,
        surface relevance (not factual correctness), unsupported-claim
        risk (a bounded heuristic, not hallucination detection), safety/
        refusal behavior (conservative, keyword-based), leakage,
        repetition/degeneration, unicode integrity
      → human review (append-only, multiple reviews per output, visible
        disagreement, required-review coverage tracking)
      → run comparison (compatible/partially_compatible/incompatible)
      → chat-readiness gate: evaluation_passed_with_limits /
        evaluation_warning / evaluation_blocked — any blocking reason
        (unsafe compliance, role leakage, unverified checkpoint, zero
         Tamil coverage, no instruction-following evidence) forces
         evaluation_blocked regardless of other scores
      → reproducibility manifest with a SHA-256 checksum
```

`ModelEvaluationService` (`backend/services/model_evaluation_service.py`)
composes existing Phase 8/9/12 machinery — `BrudForCausalLM`,
`TrainingCheckpointManager`, `TokenizerService`, and Phase 12's
`generate_greedy`/`render_example` — rather than building a new inference
path. Because evaluation here is a bounded, synchronous admin-triggered
execution over a fixed fixture set (not an unbounded training loop), it
needs no worker/queue/lease machinery of its own; `execute_run()` runs
directly inside the request. The new pure-function modules live under
`core_model/model_evaluation/` (not `core_model/evaluation/`, which
already existed from Phase 8 and is unrelated —
`ModelEvaluationEvaluator`/`architecture_checks.py`, still used by
`core_model_service.py`): `fixtures.py`, `scoring.py`,
`language_evaluation.py`, `instruction_following.py`, `relevance_checks.py`,
`hallucination_checks.py`, `refusal_checks.py`, `safety_checks.py`,
`degeneration_checks.py`, `robustness_checks.py`, `human_review.py`,
`readiness_gates.py`, `comparison.py`, and `suite.py`. See
[database_schema_v13.md](database_schema_v13.md),
[model_evaluation_suites.md](model_evaluation_suites.md),
[model_evaluation_fixtures.md](model_evaluation_fixtures.md),
[multilingual_evaluation.md](multilingual_evaluation.md),
[instruction_following_evaluation.md](instruction_following_evaluation.md),
[factual_support_evaluation.md](factual_support_evaluation.md),
[safety_refusal_evaluation.md](safety_refusal_evaluation.md),
[evaluation_leakage_repetition.md](evaluation_leakage_repetition.md),
[human_evaluation.md](human_evaluation.md),
[chat_readiness_assessment.md](chat_readiness_assessment.md), and
[model_evaluation_reproducibility.md](model_evaluation_reproducibility.md).
No RLHF, DPO, reward modeling, RAG, tool calling, web search,
quantization, GGUF export, or external model providers were added in this
phase; every candidate remains `not_public_chat_ready` regardless of the
readiness-gate outcome, and the public chatbot remains the unchanged
placeholder.

Phase 14 answers the next question: not "how well does this candidate
behave" (Phase 13), but "is this already-evaluated candidate safe and
complete enough to become a governed release" — never "should it be
deployed":

```text
Verified core model version (base_pretrained, instruction_tuned, or
evaluated) + its checkpoint
      → release candidate (checkpoint resolved automatically from the
        registry — direct FK, or checksum match for a promoted
        instruction-tuned lineage — never a raw path)
      → artifact collection + verification (path-confined, checksummed,
        against the checkpoint/tokenizer/config/dataset/manifest lineage)
      → release eligibility (14 deterministic dimensions; any blocking
        condition — missing/corrupt checkpoint, vocabulary mismatch,
        evaluation_blocked, missing manifest, unresolved safety issue —
        is never overridable by approval)
      → model card (generated from registered data only; a card
        describing a blocked model as capable/production-ready fails
        validation) + immutable release manifest (scanned for secrets/
        paths before being persisted)
      → configurable, role-based, append-only approvals (stale the
        moment the candidate's evidence changes)
      → release (semantic-style version, unique per family;
        deployment_eligibility kept separate from release status)
      → comparison / safe export bundle (excludes the database, .env,
        sessions, and raw datasets by construction) / metadata-only
        rollback (changes only a family's current-release pointer —
        never a file on disk, never public-chat assignment)
```

`ModelReleaseService` (`backend/services/model_release_service.py`)
composes the existing core-model, checkpoint, tokenizer, dataset,
instruction-tuning, and evaluation registries rather than building a
second one of any of them. The new pure-function modules live under
`core_model/release/`: `artifact_inventory.py`, `compatibility.py`,
`eligibility.py`, `model_card.py`, `manifest.py`, `approval_policy.py`,
`rollback.py`, `comparison.py`, and `release_bundle.py`. See
[database_schema_v14.md](database_schema_v14.md),
[model_release_registry.md](model_release_registry.md),
[model_release_artifacts.md](model_release_artifacts.md),
[model_release_eligibility.md](model_release_eligibility.md),
[model_cards.md](model_cards.md),
[model_release_manifests.md](model_release_manifests.md),
[model_release_approvals.md](model_release_approvals.md),
[model_release_bundles.md](model_release_bundles.md),
[model_release_rollback.md](model_release_rollback.md), and
[model_release_comparison.md](model_release_comparison.md). No public
chatbot model assignment, production model serving, container
deployment, RAG, RLHF, DPO, reward modeling, quantization, GGUF export,
external model providers, or automatic deployment/rollback of running
infrastructure were added in this phase; a registered release is never
automatically deployable or available to the public chatbot, which
remains the unchanged placeholder.

Phase 15 answers the next question: not "is this candidate safe enough
to release" (Phase 14), but "can this already-released, already-eligible
model be loaded into a bounded local runtime and safely used for admin
testing" — never "is it ready for the public":

```text
Released, deployable, evaluation-ready release (Phase 14)
      → release/runtime compatibility assessment (14 deterministic
        dimensions; any integrity mismatch is blocking)
      → resource guard (fail-closed, bounded estimate vs measured
        available memory/disk, labelled honestly)
      → registered-artifact-only model load (manifest → artifacts →
        checkpoint → tokenizer → model config → resource guard → load
        → health check; never an arbitrary path)
      → scope-specific assignment (admin_diagnostic / admin_chat_lab /
        internal_canary / public_chat, the last disabled by default;
        a registry-workflow fixture can never reach internal_canary or
        public_chat) → validate → approve (role-based, non-overridable
        when blocked) → activate → versioned, immutable once approved
      → admin diagnostic generation / admin chat lab (bounded, never
        the public chatbot) / explicit fixture-based canary (append-
        only lifecycle, auto-stop on leakage/failure/timeout thresholds)
      → assignment-level rollback (restores a prior version's full
        config snapshot; never touches an artifact on disk) / runtime
        manifest (checksummed, no paths/secrets/raw content)
      → public-chat activation gate (release readiness + runtime
        health + canary success + all required approvals + a verified
        rollback target; rejects outright on any gap — never fabricated
        to pass)
```

`InferenceRuntimeService` (`backend/services/inference_runtime_service.py`)
and `ModelAssignmentService`
(`backend/services/model_assignment_service.py`) compose the existing
release registry, checkpoint verifier, tokenizer registry, and core-model
loader rather than building a second one of any of them. The new
pure-function modules live under `core_model/inference_runtime/`:
`runtime_config.py`, `resource_guard.py`, `model_loader.py`,
`generation_config.py`, `generation_engine.py`, `context_builder.py`,
`assignment_policy.py`, `canary.py`, `runtime_health.py`, `fallback.py`,
and `comparison.py`. See
[database_schema_v15.md](database_schema_v15.md),
[inference_runtime_architecture.md](inference_runtime_architecture.md),
[inference_runtime_profiles.md](inference_runtime_profiles.md),
[inference_resource_guard.md](inference_resource_guard.md),
[inference_model_loading.md](inference_model_loading.md),
[model_assignment_scopes.md](model_assignment_scopes.md),
[model_assignment_lifecycle.md](model_assignment_lifecycle.md),
[admin_diagnostic_inference.md](admin_diagnostic_inference.md),
[admin_chat_lab.md](admin_chat_lab.md),
[inference_canary.md](inference_canary.md),
[inference_fallback.md](inference_fallback.md),
[inference_assignment_rollback.md](inference_assignment_rollback.md), and
[inference_runtime_manifest.md](inference_runtime_manifest.md). No RAG,
web search, tool calling, external model providers, multi-model
concurrent serving, GPU cluster/distributed serving, quantization, GGUF
export, RLHF, DPO, or production deployment were added in this phase;
the public chatbot remains the unchanged placeholder, and public-chat
activation remains rejected/disabled against real development data.

Phase 16 answers the next question: not "can a released model generate
text in a bounded runtime" (Phase 15), but "can that same controlled
runtime answer a question using only retrieved, approved evidence, with
every citation traceable and every low-confidence case failing safely
to a no-answer result — still never the public chatbot":

```text
Approved knowledge source (registry-backed or inline) → immutable,
checksummed source version → deterministic chunking + quality/
injection assessment (a flagged or unapproved chunk can never enter an
index) → registered embedding model → embedding run → versioned vector
index (repository_flat, no FAISS) + versioned FTS5 keyword index →
hybrid retrieval profile (access-filtered before scoring, deterministic
tie-break) → context-budgeted, fixed-format grounded prompt → existing
Phase 15 controlled inference runtime (reused admin_diagnostic scope,
never a second runtime) → citation extraction/validation (never
fabricated) → grounded-answer status (grounded_answer /
insufficient_evidence / retrieval_failed / generation_failed /
blocked_evidence) → admin RAG Chat Lab (fresh retrieval every turn) /
retrieval+generation evaluation (known-relevance fixtures only) / index
comparison / RAG manifest (checksummed, no raw content/paths/secrets)
```

`RagIngestionService`, `RagRetrievalService`, `RagGenerationService`, and
`RagEvaluationService` (`backend/services/rag_*.py`) compose the
existing release/runtime/assignment machinery rather than building a
second inference runtime or model loader. The new pure-function modules
live under `core_model/rag/` (20 modules). See
[database_schema_v16.md](database_schema_v16.md),
[rag_architecture.md](rag_architecture.md),
[rag_knowledge_ingestion.md](rag_knowledge_ingestion.md),
[rag_chunking.md](rag_chunking.md), [rag_embeddings.md](rag_embeddings.md),
[rag_vector_index.md](rag_vector_index.md),
[rag_keyword_index.md](rag_keyword_index.md),
[rag_hybrid_retrieval.md](rag_hybrid_retrieval.md),
[rag_context_budget_and_prompt.md](rag_context_budget_and_prompt.md),
[rag_citations_and_grounding.md](rag_citations_and_grounding.md),
[rag_answer_policy.md](rag_answer_policy.md),
[rag_chat_lab.md](rag_chat_lab.md), [rag_evaluation.md](rag_evaluation.md),
[rag_manifest.md](rag_manifest.md), [rag_settings.md](rag_settings.md),
[rag_api_and_cli.md](rag_api_and_cli.md), and
[rag_admin_dashboard.md](rag_admin_dashboard.md). No web search, tool
calling, external model providers, RLHF, DPO, reward modeling,
quantization, GGUF export, or automatic public-chat activation were
added in this phase; the public chatbot remains the unchanged
placeholder.

Phase 17 answers the next question: not "can this runtime answer from
retrieved evidence" (Phase 16), but "can a conversation carry a
bounded, consent-aware memory of itself — inspectable, correctable,
deletable — without that ever becoming hidden permanent profiling":

```text
Session (mode + policy) → turn (role-validated, mode-dependent
persistence) → deterministic summary (validated before use) → memory
proposal (category/purpose/safety checked) → consent gate /
confirmation gate → active | awaiting_confirmation | proposed →
participant-scoped memory retrieval (keyword + vector, reusing Phase
16 embeddings unchanged) → chat orchestration: memory retrieval + RAG
retrieval (separate, self-committing calls) → injection guard over
every context item → context budget (mandatory first, optional
greedy-packed, current message never dropped) → existing Phase 15
controlled inference runtime (reused, never a second runtime) →
response policy → answer status → memory and RAG citations kept
separate
```

`ConversationSessionService`, `MemoryService`, and
`ChatOrchestrationService` (`backend/services/{conversation_session,memory,chat_orchestration}_service.py`)
compose the existing Phase 15 runtime/assignment machinery and Phase
16 RAG retrieval service rather than building a second runtime, model
loader, or vector-index implementation. The new pure-function modules
live under `core_model/conversation/` (18 modules). See
[database_schema_v17.md](database_schema_v17.md),
[conversation_memory_architecture.md](conversation_memory_architecture.md),
[conversation_sessions_and_privacy.md](conversation_sessions_and_privacy.md),
[memory_consent_and_policies.md](memory_consent_and_policies.md),
[memory_lifecycle_and_categories.md](memory_lifecycle_and_categories.md),
[memory_versioning_and_correction.md](memory_versioning_and_correction.md),
[memory_retrieval_and_embeddings.md](memory_retrieval_and_embeddings.md),
[context_orchestration.md](context_orchestration.md),
[conversation_injection_guard.md](conversation_injection_guard.md),
[chat_orchestration_architecture.md](chat_orchestration_architecture.md),
[conversation_response_policy.md](conversation_response_policy.md),
[memory_evaluation.md](memory_evaluation.md),
[conversation_memory_manifest.md](conversation_memory_manifest.md),
[conversation_memory_settings.md](conversation_memory_settings.md),
[conversation_memory_api_and_cli.md](conversation_memory_api_and_cli.md),
and
[conversation_memory_admin_dashboard.md](conversation_memory_admin_dashboard.md).
No web search, tool calling, external model providers, autonomous
agents, RLHF, DPO, reward modeling, quantization, GGUF export, or
automatic public-chat activation were added in this phase; the public
chatbot remains the unchanged placeholder.

Phase 18 answers the next question: not "can a conversation carry a
bounded memory of itself" (Phase 17), but "can useful feedback about a
model response become reviewed, privacy-safe, explicitly-approved
training/evaluation evidence without ever training anything
automatically":

```text
model response -> privacy-safe feedback (immutable subject-lineage
snapshot, checksums only) -> classification -> deterministic triage ->
review queue -> review assignment -> human review(s) (append-only,
disagreement measured explicitly) -> corrected response (immutable
proposal, its own draft/validated/rejected/superseded lifecycle,
original output never overwritten) -> dataset candidate (privacy/
safety/licence/deduplication/contamination checked) -> explicit
approval -> export through the EXISTING Phase 3 dataset-record
pipeline (never a direct finalized-version write) | regression fixture
(evaluation-only, never exported to training) -> regression run
against the existing Phase 15 runtime -> model comparison (compatible
evidence only) -> improvement report
```

`FeedbackService`, `FeedbackReviewService`, `FeedbackDatasetService`,
and `RegressionEvaluationService`
(`backend/services/{feedback,feedback_review,feedback_dataset,regression_evaluation}_service.py`)
compose the existing Phase 3 dataset pipeline and Phase 15 runtime
rather than building a second dataset-management system, a second
inference runtime, or a second memory store. The new pure-function
modules live under `core_model/feedback/` (14 modules). See
[database_schema_v18.md](database_schema_v18.md),
[feedback_architecture.md](feedback_architecture.md),
[feedback_policies.md](feedback_policies.md),
[feedback_privacy_and_safety.md](feedback_privacy_and_safety.md),
[feedback_classification.md](feedback_classification.md),
[feedback_human_review.md](feedback_human_review.md),
[feedback_corrected_responses.md](feedback_corrected_responses.md),
[feedback_dataset_candidates.md](feedback_dataset_candidates.md),
[feedback_deduplication_and_contamination.md](feedback_deduplication_and_contamination.md),
[feedback_licence_and_provenance.md](feedback_licence_and_provenance.md),
[feedback_regression_suites.md](feedback_regression_suites.md),
[feedback_model_comparison.md](feedback_model_comparison.md),
[feedback_improvement_reports.md](feedback_improvement_reports.md),
[feedback_manifest.md](feedback_manifest.md),
[feedback_api_cli.md](feedback_api_cli.md), and
[feedback_admin_dashboard.md](feedback_admin_dashboard.md). No
automatic self-training, automatic fine-tuning, automatic dataset
approval, reward-model training, RLHF, DPO, preference optimization,
autonomous agents, external model providers, web search, tool
execution, or production deployment were added in this phase.

## Database

SQLite uses a configurable path, foreign-key enforcement, WAL journaling, and a bounded busy timeout. The migration CLI verifies integrity and foreign keys, makes a checksum-verified backup, and then applies additive schema changes. Schema v2 establishes the data control plane; schema v3 adds local admin accounts and revocable sessions; schema v4 adds import jobs, preview rows, and append-only import events; schema v5 adds document extraction; schema v6 adds quality assessments, build jobs, immutable dataset versions, and exports; schema v7 adds tokenizer training, evaluation, assignment, and export tables; schema v8 adds core model architecture, config, checkpoint, check, and assignment tables; schema v9 adds bounded pretraining jobs, metrics, checkpoints, evaluations, events, and worker leases without rebuilding existing tables; schema v10 (migration `010_phase10_training_reliability`, independent of migration 009) adds worker heartbeats, lease-generation fencing columns, recovery attempts, dataset coverage, stream manifests, run summaries, quality assessments/issues, checkpoint/run comparisons, and retention actions — see [database_schema_v10.md](database_schema_v10.md); schema v11 (migration `011_phase11_base_pretraining_evaluation`, independent of migration 010) adds base-training experiments, experiment runs, dataset profiles, language metrics, learning checks, candidate selections, and reproducibility manifests, all referencing existing dataset/tokenizer/core-model/pretraining/checkpoint tables rather than duplicating them — see [database_schema_v11.md](database_schema_v11.md); schema v12 (migration `012_phase12_instruction_tuning`, independent of migration 011) adds instruction-tuning experiments, runs, dataset profiles, instruction templates, per-step metrics, evaluations/evaluation results, learning checks, candidate selections, and reproducibility manifests, again referencing existing tables rather than duplicating them — see [database_schema_v12.md](database_schema_v12.md); schema v13 (migration `013_phase13_multilingual_evaluation`, independent of migration 012) adds evaluation suites, fixture sets, fixtures, evaluation runs, outputs, metrics, issues, human reviews, comparisons, chat-readiness assessments, and reproducibility manifests — see [database_schema_v13.md](database_schema_v13.md); schema v14 (migration `014_phase14_model_release_registry`, independent of migration 013) adds release families, release candidates, artifacts, manifests, model cards, eligibility assessments, issues, approvals, releases, comparisons, rollback plans/events, and bundles, all referencing existing candidate/checkpoint/tokenizer/dataset/evaluation tables rather than duplicating them — see [database_schema_v14.md](database_schema_v14.md); schema v15 (migration `015_phase15_controlled_inference_runtime`, independent of migration 014) adds runtime profiles/instances, runtime health checks, compatibility assessments, assignment scopes/assignments/versions/approvals/events, chat-lab sessions, inference requests/results/failures, canary runs/results, and runtime manifests, all referencing existing release/core-model/checkpoint/tokenizer tables rather than duplicating them — see [database_schema_v15.md](database_schema_v15.md); schema v16 (migration `016_phase16_rag_grounded_answering`, independent of migration 015) adds knowledge spaces/sources/versions, chunk sets/chunks, embedding models/runs/chunk embeddings, vector/keyword indexes, retrieval profiles/runs/retrieved chunks, context assemblies, grounded requests/answers/citations, grounding issues, evaluation suites/fixtures/runs/metrics, index comparisons, and RAG manifests — 24 tables, all referencing existing dataset/document/release/inference-runtime tables rather than duplicating them — see [database_schema_v16.md](database_schema_v16.md); schema v17 (migration `017_phase17_conversation_memory`, independent of migration 016) adds conversation memory policies, sessions, session participants, turns/turn events, summaries/summary versions, memory consents, memory items/versions/events/embeddings, memory retrieval profiles/runs/results, chat context assemblies/items, chat orchestration runs/grounded responses/citations/issues, and memory evaluation suites/fixtures/runs/metrics plus a manifest table — 26 tables, all referencing existing inference-runtime and RAG tables where relevant rather than duplicating them — see [database_schema_v17.md](database_schema_v17.md); schema v18 (migration `018_phase18_feedback_learning_loop`, independent of migration 017) adds feedback policies, subjects, events, classifications, attachments, review queues/assignments, human reviews, corrected responses, privacy/safety findings, quality assessments, dataset candidates/versions/issues/approvals, regression suites/fixtures/runs/results, model comparisons, improvement reports, and a feedback manifest — 23 tables, all referencing existing inference-runtime and dataset tables where relevant rather than duplicating them — see [database_schema_v18.md](database_schema_v18.md).

Repositories own parameterized SQL, transaction boundaries, public-ID lookup, pagination, JSON encoding, and lifecycle validation. Numeric database IDs never cross the public API boundary. Dataset versions marked ready and audit events are protected from content mutation at both repository and database-trigger levels.

All admin control-plane and dataset routes now require a valid active local-admin session. Mutations additionally require CSRF validation. Responses deliberately omit numeric IDs, password/session hashes, filesystem paths, secret settings, raw request bodies, and chat content.

## Future data and training workflow

```text
Admin Dashboard
      ↓
Dataset Management
      ↓
Core Model Training
      ↓
Evaluation
      ↓
Model Registry            ← implemented in Phase 14 (release governance,
      ↓                      not deployment — see the Phase 14 section above)
Chatbot Testing
```

Phase 14 implements the Model Registry stage of this workflow: approved,
versioned datasets and immutable evaluation evidence are now required
before a candidate can become a governed release (registry/release
eligibility, never registry *promotion to production*). "Chatbot
Testing" — actually assigning a release to the public chatbot — remains
unimplemented and out of scope; audit events already accompany every
administrative mutation from Phase 3 onward, including every Phase 14
mutation.
