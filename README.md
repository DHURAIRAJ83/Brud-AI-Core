# Brud AI

Brud AI is a standalone foundation for a small AI system intended to understand and respond to Tamil, English, Tanglish, and mixed-language input. Phase 9 added bounded CPU base-pretraining infrastructure for Brud Core; Phase 10 adds training reliability, crash recovery, dataset coverage, and quality gating on top of it; Phase 11 adds representative multilingual base-pretraining experiments and honest learning evaluation (dataset profiling, tokenizer suitability, per-language metrics, generalization/memorization checks, candidate selection, reproducibility manifests) on top of the same worker and services; Phase 12 adds supervised instruction tuning (response-only label masking, instruction templates, per-language response-loss evaluation, leakage/repetition/memorization checks, bounded admin-only diagnostic generation, candidate selection) on top of the same trainer and worker, reused via a sibling trainer function rather than a second training loop; Phase 13 adds multilingual evaluation, safety validation, and chat-readiness assessment for an eligible Phase 12 instruction-tuned candidate (admin-authored versioned fixture suites, bounded greedy generation over every fixture, language/instruction-following/relevance/factual-support/safety/leakage/repetition checks, human review with visible disagreement, run comparison, reproducibility manifests, and a final evidence-based `evaluation_passed_with_limits`/`evaluation_warning`/`evaluation_blocked` readiness gate); Phase 14 adds a model registry and release-management system on top (release families, release candidates collected/verified from registered artifacts, deterministic release eligibility across 14 dimensions, versioned model cards, immutable release manifests, configurable multi-role approvals, semantic-style release versioning, safe export bundles, release comparison, and metadata-only rollback) — an evaluation-blocked candidate is structurally unable to become a deployable release, and registry/release status is always kept separate from public-chat assignment; Phase 15 adds a bounded local inference runtime on top of the release registry (runtime profiles/instances, a 14-dimension release/runtime compatibility assessment, a fail-closed resource guard, registered-artifact-only model loading with checksum/vocabulary/special-token verification, deterministic context building and bounded generation reused from Phase 12's greedy loop, scope-specific model assignment with versioning and non-overridable eligibility, admin-only diagnostics and chat lab, an explicit fixture-based canary, assignment-level rollback, and a runtime manifest) — loading a model into the runtime is never the same as assigning it, assigning it is never the same as public-chat activation, and the public-chat activation gate is never auto-passed; Phase 16 adds admin-only grounded retrieval (RAG) on top of that runtime (approved-source knowledge spaces, immutable checksummed source versions, deterministic chunking with quality and prompt-injection filtering, registered embedding models, versioned vector and FTS5 keyword indexes, hybrid retrieval with access filtering applied before scoring, context-budgeted grounded generation with deterministic never-fabricated citations, a five-status safe no-answer policy, an admin RAG Chat Lab with fresh retrieval every turn, retrieval/generation evaluation against known-relevance fixtures only, index comparison, and a RAG manifest) — RAG generation reuses the existing controlled inference runtime and the `admin_diagnostic` assignment scope rather than a second runtime, and the public chatbot remains the unchanged placeholder throughout. No phase connects a model to the public chatbot, which remains a placeholder.

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

## Phase 13 status

Schema v13 adds evaluation suites, fixture sets, fixtures, evaluation runs, outputs, metrics, issues, human reviews, comparisons, chat-readiness assessments, and reproducibility manifests, all referencing existing candidate/checkpoint/tokenizer tables — no second trainer, no second quality gate. Phase 13 asks how well a Phase 12 instruction-tuned candidate actually behaves across supported languages and safety conditions, never confusing low validation loss with useful assistant behavior. Admin-authored, versioned fixture suites (never hardcoded content) are executed via bounded, deterministic greedy generation (`core_model.instruction_tuning.generation.generate_greedy`, reused unchanged) against every fixture; responses are scored for language compliance, instruction following, surface relevance (explicitly not factual correctness), unsupported-claim risk (a bounded heuristic, not comprehensive hallucination detection), safety/refusal behavior (conservative, keyword-based), and leakage/repetition/degeneration. Human review is append-only with visible disagreement, never silently averaged away. The final chat-readiness gate is conservative and evidence-based — any blocking issue (unsafe compliance, role-token leakage, unverified checkpoint, zero Tamil coverage, no instruction-following evidence) forces `evaluation_blocked` regardless of other scores — and every candidate remains `not_public_chat_ready` no matter the outcome. See [docs/phase_13_report.md](docs/phase_13_report.md) and [docs/architecture.md](docs/architecture.md).

## Phase 14 status

Schema v14 adds release families, release candidates, artifacts, manifests, model cards, eligibility assessments, issues, approvals, releases, comparisons, rollback plans/events, and bundles, all referencing existing core-model/checkpoint/tokenizer/dataset/instruction-tuning/evaluation tables — no second registry, no second checkpoint verifier, no second evaluation system. Phase 14 asks whether an already-evaluated candidate is safe and complete enough to become a governed release — never whether it should be deployed. A candidate's checkpoint is resolved automatically from the existing registry (never a raw path), its artifacts are collected and verified with strict path confinement and checksum matching, and its release eligibility is assessed across 14 deterministic dimensions where any blocking condition (a missing/corrupt checkpoint, a vocabulary mismatch, `evaluation_blocked` status, a missing manifest, an unresolved safety issue) is never overridable by approval. Model cards are generated from registered data only, and one describing an evaluation-blocked model as capable or production-ready fails validation. Release manifests are immutable and scanned for accidental secrets/paths before being persisted; approvals are role-based, append-only, and become stale the moment a candidate's evidence changes; releases use semantic-style versioning and a separate `deployable`/`deployable_with_warnings`/`not_deployable` field, kept distinct from release status; safe export bundles exclude the database, `.env`, sessions, and raw datasets by construction; and rollback is metadata-only — it changes a family's current-release pointer and nothing on disk. The current Phase 13 evaluation-blocked harness candidate is registrable but structurally cannot reach `approved` or `released`. See [docs/phase_14_report.md](docs/phase_14_report.md) and [docs/architecture.md](docs/architecture.md).

## Phase 15 status

Schema v15 adds runtime profiles/instances, runtime health checks, release/runtime compatibility assessments, assignment scopes/assignments/versions/approvals/events, admin chat-lab sessions, inference requests/results/failures, canary runs/results, and runtime manifests, all referencing existing release/core-model/checkpoint/tokenizer tables — no second registry, no second tokenizer registry, no second checkpoint verifier, no new model architecture, no duplicate public chat endpoint, no deployment orchestrator. Phase 15 asks whether an already-released, already-eligible model can be loaded into a bounded local runtime and safely used for admin testing — never whether it is ready for the public. Only releases marked `released` with deployment eligibility `deployable`/`deployable_with_warnings` and evaluation status other than `evaluation_blocked`/`not_assessed` may be assigned, re-derived live from the current evaluation evidence at every check rather than trusted from a stale snapshot; a registry-workflow fixture (Phase 14's own `registry_workflow_fixture`/`not_production_model` markers) can never be assigned to `internal_canary` or `public_chat`, and only to `admin_diagnostic` behind an explicit, default-off test-only setting. Model loading follows one fixed verify-then-load pipeline (manifest, artifacts, checkpoint, tokenizer, model config, resource guard, then load, then health check) against registered artifacts only — never an arbitrary path. Bounded generation reuses Phase 12's greedy loop shape, extended with cooperative cancellation and mid-generation role-token-leakage detection. Assignment configuration is immutable once approved; any change reopens validation and produces a new immutable version, never an in-place edit. Canary execution is explicit-fixture-only, append-only, with conservative auto-stop thresholds. Rollback is assignment-level, restores the target version's full configuration snapshot (not just its release pointer), and never touches an artifact on disk — verified directly by a byte-for-byte checkpoint-directory comparison before and after a real rollback. The public-chat activation gate requires a release's full readiness, runtime health, successful canary, all required approvals, and a verified rollback target, and rejects outright when any is missing; Phase 15 does not fabricate a passing release to exercise it, so public activation remains rejected/disabled against real development data. See [docs/phase_15_report.md](docs/phase_15_report.md) and [docs/architecture.md](docs/architecture.md).

## Phase 16 status

Schema v16 adds knowledge spaces/sources/versions, chunk sets/chunks, embedding models/runs/chunk embeddings, vector/keyword indexes, retrieval profiles/runs/retrieved chunks, context assemblies, grounded requests/answers/citations, grounding issues, evaluation suites/fixtures/runs/metrics, index comparisons, and RAG manifests — 24 tables, all referencing existing dataset/document/release/inference-runtime tables — no second inference runtime, no second model loader, no duplicate public chat endpoint. Phase 16 asks whether an already-controlled runtime can answer a question using only retrieved, approved evidence with every citation traceable — never whether retrieval guarantees a correct answer. Only `approved` sources' chunks are ever eligible for embedding or keyword indexing; a chunk flagged by the bounded, context-aware prompt-injection filter is structurally excluded from every index, not merely hidden afterward (verified directly: a two-section fixture with one benign and one injection-style paragraph produced exactly one indexed, clean chunk). Access filters (approval, licence, language, source/version) are applied before scoring, never after. Retrieval is hybrid vector+keyword with deterministic tie-breaking; the vector index is a repository-backed flat store (no FAISS dependency) and the keyword index is FTS5-backed, both versioned and immutable once active. Citations are assigned deterministically from retrieved evidence only and validated against four outcomes (`valid`/`valid_with_warning`/`invalid`/`not_present`) — never invented by the model. Insufficient evidence, retrieval failure, generation failure, and blocked evidence each produce an explicit, safe no-answer result rather than a fabricated one, verified directly against an empty knowledge space and against a rejected/unapproved source whose chunks could never enter an index at all. RAG generation reuses the existing controlled inference runtime and the `admin_diagnostic` assignment scope rather than a second runtime; the public chatbot remains the unchanged placeholder throughout, verified directly after every grounded-answer and RAG Chat Lab call exercised in this phase. See [docs/phase_16_report.md](docs/phase_16_report.md) and [docs/architecture.md](docs/architecture.md).
