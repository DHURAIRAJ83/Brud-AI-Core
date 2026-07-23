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

## Database

SQLite uses a configurable path, foreign-key enforcement, WAL journaling, and a bounded busy timeout. The migration CLI verifies integrity and foreign keys, makes a checksum-verified backup, and then applies additive schema changes. Schema v2 establishes the data control plane; schema v3 adds local admin accounts and revocable sessions; schema v4 adds import jobs, preview rows, and append-only import events; schema v5 adds document extraction; schema v6 adds quality assessments, build jobs, immutable dataset versions, and exports; schema v7 adds tokenizer training, evaluation, assignment, and export tables; schema v8 adds core model architecture, config, checkpoint, check, and assignment tables; schema v9 adds bounded pretraining jobs, metrics, checkpoints, evaluations, events, and worker leases without rebuilding existing tables; schema v10 (migration `010_phase10_training_reliability`, independent of migration 009) adds worker heartbeats, lease-generation fencing columns, recovery attempts, dataset coverage, stream manifests, run summaries, quality assessments/issues, checkpoint/run comparisons, and retention actions — see [database_schema_v10.md](database_schema_v10.md); schema v11 (migration `011_phase11_base_pretraining_evaluation`, independent of migration 010) adds base-training experiments, experiment runs, dataset profiles, language metrics, learning checks, candidate selections, and reproducibility manifests, all referencing existing dataset/tokenizer/core-model/pretraining/checkpoint tables rather than duplicating them — see [database_schema_v11.md](database_schema_v11.md); schema v12 (migration `012_phase12_instruction_tuning`, independent of migration 011) adds instruction-tuning experiments, runs, dataset profiles, instruction templates, per-step metrics, evaluations/evaluation results, learning checks, candidate selections, and reproducibility manifests, again referencing existing tables rather than duplicating them — see [database_schema_v12.md](database_schema_v12.md).

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
Model Registry
      ↓
Chatbot Testing
```

Future phases should require approved, versioned datasets before training; immutable evaluation evidence before registry promotion; and an explicitly active model before chatbot inference. Audit events should accompany administrative mutations.
