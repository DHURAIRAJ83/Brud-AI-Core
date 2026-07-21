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

SQLite uses a configurable path, foreign-key enforcement, WAL journaling, and a five-second busy timeout. The idempotent migration runner records schema version 1 in `schema_migrations`. The initial tables establish settings, conversations, datasets, training jobs, model registry, and audit boundaries without implementing those workflows.

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
