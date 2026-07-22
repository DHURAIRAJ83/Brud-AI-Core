# Architecture

Brud AI is a modular monorepo with three product surfaces and a shared backend. The boundaries are intentional: frontend code never imports backend or model internals, and the backend depends only on the public model contract when model work begins.

## Chatbot

The Vite/React chatbot is a stateless Phase 1 client. It checks `GET /api/health`, submits validated text and a language preference to `POST /api/chat`, and renders loading and failure states. The development server proxies `/api` to the local backend. Persistence and real inference are deferred.

## Backend runtime

FastAPI is assembled by `create_app`. Its lifespan initializes SQLite after startup rather than during module import. Routes are grouped below `/api`, CORS accepts only the two configured local origins, and centralized handlers prevent accidental internal-error disclosure. Logs are JSON objects suitable for later collection.

## Core Model

`core_model` defines stable contracts for `TokenizerManager`, `ModelConfig`, `ModelTrainer`, `InferenceEngine`, `ModelEvaluator`, and `ModelExporter`. Every unavailable operation raises `NotImplementedError`. `ModelStatus` describes the future lifecycle without pretending a model exists.

## Admin Dashboard

The separate Vite/React admin application uses a responsive dashboard shell. Overview consumes `GET /api/admin/overview`; the remaining navigation entries are explicit future-phase placeholders. Components and API access are separated so a later authentication layer can be added centrally.

## Database

SQLite uses a configurable path, foreign-key enforcement, WAL journaling, and a bounded busy timeout. The migration CLI verifies integrity and foreign keys, makes a checksum-verified backup, and then applies additive schema changes. Schema v2 establishes review, immutable dataset-version, training-event, model-version/assignment, feedback, approval, and append-only audit boundaries.

Repositories own parameterized SQL, transaction boundaries, public-ID lookup, pagination, JSON encoding, and lifecycle validation. Numeric database IDs never cross the public API boundary. Dataset versions marked ready and audit events are protected from content mutation at both repository and database-trigger levels.

The temporary read-only admin control plane exposes safe database, configuration, schema, and audit metadata. It deliberately omits filesystem paths, secret settings, raw request bodies, and chat content.

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
