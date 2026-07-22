# Brud AI

Brud AI is a standalone foundation for a small AI system intended to understand and respond to Tamil, English, Tanglish, and mixed-language input. Phase 3 adds authenticated local dataset administration; it does not train or run an AI model.

## Products

- **Brud Chatbot** — a responsive React chat client with language selection and backend status.
- **Brud Core Model** — Python contracts for future tokenizer, training, inference, evaluation, and export work.
- **Brud Admin Dashboard** — an authenticated React interface for manual dataset sources, records, reviews, duplicates, and system status.

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

Create the first local administrator interactively, then sign in at `http://localhost:5174/#Login`:

```bash
. venv/bin/activate
python -m backend.admin_cli create-admin
python -m backend.admin_cli list-admins
```

Account recovery commands are `disable-admin`, `enable-admin`, and `reset-password`. Password entry is always interactive and never accepted as a command-line argument.

## Test and quality commands

```bash
make test
make lint
make format
make db-init
make db-status
make db-verify
make db-backup
make db-upgrade
```

Frontend production builds can be checked with `npm run build --prefix apps/chatbot` and `npm run build --prefix apps/admin-dashboard`.

## Configuration

Copying `.env.example` is handled by setup. All backend variables use the `BRUD_` prefix; see [docs/development.md](docs/development.md) for the complete table. Frontends use the Vite development proxy by default and may set `VITE_API_BASE_URL` for separately hosted environments.

## Current limitations

There is no public registration, file import/upload, dataset-version building, training execution, evaluation workflow, RAG, external model provider, or real inference. Authentication is local-only and has no role hierarchy or production identity provider. The chat response remains deliberately labeled as a placeholder.

## Phase 3 status

Schema v3 adds local admin accounts and hashed server sessions. Cookie authentication, CSRF protection, lockout, manual source/record management, lifecycle review, duplicate detection, statistics, immutable review history, and audit evidence are implemented while retaining earlier behavior. Verification is recorded in [docs/phase_3_report.md](docs/phase_3_report.md).
