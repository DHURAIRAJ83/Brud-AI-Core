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
Dataset API → Dataset service → Repositories → SQLite
```

Routes translate validated inputs and controlled errors. Lifecycle, duplicate, and transaction rules live in the service/repository layers rather than React or route handlers.

## Database

SQLite uses a configurable path, foreign-key enforcement, WAL journaling, and a bounded busy timeout. The migration CLI verifies integrity and foreign keys, makes a checksum-verified backup, and then applies additive schema changes. Schema v2 establishes the data control plane; additive schema v3 adds local admin accounts and revocable sessions without rebuilding existing tables.

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
