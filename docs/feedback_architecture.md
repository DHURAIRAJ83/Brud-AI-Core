# Phase 18 Feedback Improvement Pipeline Architecture Overview

A privacy-safe, auditable feedback and human-review pipeline that
converts useful administrator feedback into controlled dataset
candidates and regression-evaluation evidence — never into training
data automatically.

## Core principle

Phase 17 established conversation + consented memory + RAG evidence +
controlled inference. Phase 18 adds:

```
model response
    -> privacy-safe feedback
    -> human review
    -> validated correction
    -> approved dataset candidate
    -> future training/evaluation input (a separate, later phase)
```

The system never does:

```
feedback received -> automatically train model
```

Instead:

```
feedback received -> review -> privacy/licence/safety validation
    -> deduplication and contamination checks -> explicit approval
    -> dataset candidate only
```

## Pipeline

```
feedback subject snapshot (checksums + public IDs only)
  -> feedback event (thumbs_up/down, rating, issue/citation/safety/
     language/memory/retrieval report, correction) + classification(s)
  -> deterministic triage -> review queue -> review assignment
  -> human review(s) (append-only, disagreement measured explicitly)
  -> corrected response (immutable proposal, own draft/validated/
     rejected/superseded lifecycle, never overwrites the original output)
  -> dataset candidate (privacy/safety/licence/dedup/contamination
     checked) -> explicit approval -> export through the EXISTING
     Phase 3 dataset-record pipeline (never a direct finalized-version write)
  -> regression fixture (evaluation-only, never exported to training)
  -> regression run against the existing Phase 15 runtime
  -> model comparison (compatible evidence only) -> improvement report
```

## Package layout

- `core_model/feedback/` — 14 pure-function modules, no I/O, no
  `Settings` dependency, unit-tested in
  `tests/core_model/test_phase18_feedback.py`.
- `backend/models/feedback.py` — Pydantic request/response schemas.
- `backend/database/repositories/feedback.py` — the 23-table
  repository, `public_row()`/`INTERNAL`-stripping pattern identical to
  every prior phase's repository.
- `backend/services/feedback_service.py` — policies, subject-lineage
  resolution, feedback submission, classification, triage,
  privacy/safety scanning.
- `backend/services/feedback_review_service.py` — review queues,
  assignments, human reviews, corrected responses.
- `backend/services/feedback_dataset_service.py` — dataset-candidate
  creation, quality assessment, approval, export (hands off to the
  existing dataset pipeline).
- `backend/services/regression_evaluation_service.py` — regression
  suites/fixtures/runs/results, model comparisons, improvement
  reports, manifest.
- `backend/api/routes/feedback.py` — routes under `/api/admin/feedback`,
  every mutation behind `require_admin` + CSRF.
- `backend/feedback_cli.py` — 18 operator subcommands.
- `apps/admin-dashboard/src/pages/FeedbackPage.jsx` — 16-tab admin UI.

## Reuse, never duplication

- Regression execution reuses Phase 15's
  `InferenceRuntimeService.run_generation()` and
  `ModelAssignmentService.ensure_instance_loaded()` unchanged — no
  second inference runtime.
- Safety/leakage checks reuse Phase 12/13's
  `core_model.instruction_tuning.evaluation` (role-token leakage,
  prompt/system leakage, repetition) and Phase 16's
  `core_model.rag.injection_filter` unchanged.
- Near-duplicate detection reuses Phase 16's
  `core_model.rag.chunk_validation.near_duplicate_ratio`
  (`difflib.SequenceMatcher`-based) unchanged.
- Dataset export reuses Phase 3's `DatasetService.create_record()`
  unchanged — an approved candidate becomes a `draft` `dataset_records`
  row subject to the exact same quality/duplicate review every other
  record goes through, never a direct write into a finalized
  `dataset_versions` row.
- The manifest module re-exports Phase 14's checksum/scan
  implementation unchanged (via Phase 16/17's own re-export).

## What Phase 18 deliberately does not do

- No automatic self-training, automatic fine-tuning, or automatic
  dataset approval — every dataset candidate requires an explicit
  admin approval action, confirmed directly in
  `feedback_dataset_service.py` and exercised in manual verification
  Paths A/B (positive feedback never creates a candidate; a reviewed,
  corrected candidate remains pending until explicitly approved).
- No reward-model training, RLHF, DPO, or preference optimization —
  preference candidates are structurally blocked from
  `export_candidate()`.
- No automatic public-chat activation — `POST /api/chat` is unchanged
  and still returns `{"model": "placeholder"}` after every feedback
  operation exercised in this phase's tests and manual verification.
- No autonomous agents, external model providers, web search, tool
  execution, or production deployment.

See `docs/database_schema_v18.md` for the schema, and the
per-subsystem docs for detail.
