# Brud AI

Brud AI is a standalone foundation for a small AI system intended to understand and respond to Tamil, English, Tanglish, and mixed-language input. Phase 1 establishes product boundaries and reliable development infrastructure; it does not train or run an AI model.

## Products

- **Brud Chatbot** — a responsive React chat client with language selection and backend status.
- **Brud Core Model** — Python contracts for future tokenizer, training, inference, evaluation, and export work.
- **Brud Admin Dashboard** — a separate React operations interface for future data and model workflows.

The FastAPI backend and SQLite database provide shared APIs and persistence foundations while keeping each product modular.

## Project structure

```text
apps/                    React/Vite chatbot and admin applications
backend/                 FastAPI API, configuration, logging, and SQLite runtime
core_model/              Explicit, unimplemented model interfaces
data/                    Dataset stages and local SQLite storage
models/                  Future checkpoints, registry, active models, and exports
scripts/                 Setup and development launchers
tests/                   Backend, database, and core-model tests
docs/                    Architecture, development guide, and phase report
```

## Prerequisites

- Python 3.11 or newer
- Node.js and npm (current LTS recommended)
- Bash, Make, and curl for the documented commands

## Setup

```bash
./scripts/setup.sh
# or
make setup
```

Setup creates `venv`, installs Python and frontend dependencies, creates `.env` only when absent, and initializes the configured SQLite database.

## Run locally

```bash
make backend   # http://127.0.0.1:8000
make chatbot   # http://localhost:5173
make admin     # http://localhost:5174
make dev       # all three, with child-process cleanup
```

Interactive API docs are available at `http://127.0.0.1:8000/docs`.

## Test and quality commands

```bash
make test
make lint
make format
make db-init
```

Frontend production builds can be checked with `npm run build --prefix apps/chatbot` and `npm run build --prefix apps/admin-dashboard`.

## Configuration

Copying `.env.example` is handled by setup. All backend variables use the `BRUD_` prefix; see [docs/development.md](docs/development.md) for the complete table. Frontends use the Vite development proxy by default and may set `VITE_API_BASE_URL` for separately hosted environments.

## Current limitations

There is no authentication, message persistence UI, dataset management, training, evaluation, registry workflow, RAG, external model provider, or real inference. The chat response is deliberately labeled as a placeholder. SQLite is intended only for this foundation and local development.

## Phase 1 status

The backend, both frontend foundations, database schema, core-model contracts, scripts, tests, and documentation are implemented. Verified command results are recorded in [docs/phase_1_report.md](docs/phase_1_report.md).
