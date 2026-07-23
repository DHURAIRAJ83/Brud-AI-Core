# Brud AI

Brud AI is a standalone foundation for a small AI system intended to understand and respond to Tamil, English, Tanglish, and mixed-language input. Phase 9 added bounded CPU base-pretraining infrastructure for Brud Core; Phase 10 adds training reliability, crash recovery, dataset coverage, and quality gating on top of it; Phase 11 adds representative multilingual base-pretraining experiments and honest learning evaluation (dataset profiling, tokenizer suitability, per-language metrics, generalization/memorization checks, candidate selection, reproducibility manifests) on top of the same worker and services; Phase 12 adds supervised instruction tuning (response-only label masking, instruction templates, per-language response-loss evaluation, leakage/repetition/memorization checks, bounded admin-only diagnostic generation, candidate selection) on top of the same trainer and worker, reused via a sibling trainer function rather than a second training loop. No phase connects a model to the public chatbot, which remains a placeholder.

## Products

- **Brud Chatbot** — a responsive React chat client with language selection and backend status.
- **Brud Core Model** — PyTorch decoder-only Transformer architecture, validation, checkpoints, smoke tests, and bounded base-pretraining jobs.
- **Brud Admin Dashboard** — an authenticated React interface for dataset sources, records, imports, documents, quality review, versions, tokenizer workflows, core model workflows, exports, and system status.

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

There is no public registration, remote import, instruction tuning, chat inference, RAG, external model provider, distributed training, quantization, GGUF export, or billing. Authentication is local-only and has no role hierarchy or production identity provider. The chat response remains deliberately labeled as a placeholder.

## Phase 9 status

Schema v9 adds bounded pretraining jobs, metrics, checkpoints, evaluations, job events, and worker leases. The local worker is explicit (`python -m backend.training_worker`) and trains only from registered immutable dataset versions, verified tokenizer metadata, and architecture-verified Brud Core versions. Verification is recorded in [docs/phase_9_report.md](docs/phase_9_report.md).

## Phase 10 status

Schema v10 adds worker heartbeats, lease-generation fencing, verified recovery, dataset coverage, stream manifests, run summaries, training-process quality gates, and checkpoint/run comparisons — all on top of the existing Phase 9 worker and service, with no second training loop. A resumed job is never restarted from an unverified checkpoint. Promotion is blocked by any integrity issue and requires a comment to override a warning-level one. See [docs/phase_10_report.md](docs/phase_10_report.md) and [docs/architecture.md](docs/architecture.md).

## Phase 11 status

Schema v11 adds base-training experiments, experiment runs, dataset profiles, per-language metrics, learning checks, candidate selections, and reproducibility manifests, all referencing existing dataset/tokenizer/core-model/pretraining tables — no second trainer, no second quality gate. Phase 11 asks whether a run shows genuine evidence of learning, not just decreasing training loss: it profiles the representative dataset, decides tokenizer suitability, evaluates completed runs per language (Tamil/English/Tanglish/Mixed/Overall) against fixed held-out fixtures that are never trained on, classifies generalization honestly (`not_assessed` / `optimization_success_only` / `limited_generalization_evidence`), and only then selects a candidate — which remains `not_instruction_tuned` and `not_chat_ready`, and is never assigned to the public chatbot. See [docs/phase_11_report.md](docs/phase_11_report.md) and [docs/architecture.md](docs/architecture.md).

## Phase 12 status

Schema v12 adds instruction-tuning experiments, runs, dataset profiles, instruction templates, per-step metrics, evaluations/evaluation results, learning checks, candidate selections, and reproducibility manifests, all referencing existing tables — no second trainer, no second quality gate. Phase 12 teaches an eligible Phase 11 base-pretrained candidate to follow instructions via a response-only masked supervised fine-tuning loop (`core_model.training.trainer.run_instruction_tuning`, a sibling of the base-pretraining trainer, not a replacement): system/user/padding tokens never contribute to loss, only assistant-response tokens do — proven directly by test, not by convention. A dedicated worker-dispatch guard means the base-pretraining worker can never claim an instruction-tuning job and vice versa. Candidates are evaluated per language against fixed held-out fixtures via bounded, admin-only greedy generation (never the public chatbot), checked for role/prompt-token leakage, repetition, and memorization, and selected only as `instruction_tuned_candidate` or `instruction_tuned_with_warnings` — remaining `evaluation_required` and `not_public_chat_ready`. See [docs/phase_12_report.md](docs/phase_12_report.md) and [docs/architecture.md](docs/architecture.md).
