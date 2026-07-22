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

## Database

SQLite uses a configurable path, foreign-key enforcement, WAL journaling, and a bounded busy timeout. The migration CLI verifies integrity and foreign keys, makes a checksum-verified backup, and then applies additive schema changes. Schema v2 establishes the data control plane; schema v3 adds local admin accounts and revocable sessions; schema v4 adds import jobs, preview rows, and append-only import events; schema v5 adds document extraction; schema v6 adds quality assessments, build jobs, immutable dataset versions, and exports; schema v7 adds tokenizer training, evaluation, assignment, and export tables without rebuilding existing tables.

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
