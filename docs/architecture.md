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

## Database

SQLite uses a configurable path, foreign-key enforcement, WAL journaling, and a bounded busy timeout. The migration CLI verifies integrity and foreign keys, makes a checksum-verified backup, and then applies additive schema changes. Schema v2 establishes the data control plane; schema v3 adds local admin accounts and revocable sessions; schema v4 adds import jobs, preview rows, and append-only import events; schema v5 adds document extraction; schema v6 adds quality assessments, build jobs, immutable dataset versions, and exports; schema v7 adds tokenizer training, evaluation, assignment, and export tables; schema v8 adds core model architecture, config, checkpoint, check, and assignment tables; schema v9 adds bounded pretraining jobs, metrics, checkpoints, evaluations, events, and worker leases without rebuilding existing tables; schema v10 (migration `010_phase10_training_reliability`, independent of migration 009) adds worker heartbeats, lease-generation fencing columns, recovery attempts, dataset coverage, stream manifests, run summaries, quality assessments/issues, checkpoint/run comparisons, and retention actions — see [database_schema_v10.md](database_schema_v10.md).

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
