# Phase 16 RAG Architecture Overview

Retrieval-augmented grounded answering, admin-only, built entirely on
top of existing Phase 1-15 infrastructure. No new inference runtime, no
new model loader, no public-facing endpoint.

## Pipeline

```
knowledge source (approved) -> source version (immutable, checksummed)
  -> chunk set (deterministic chunking + quality/injection assessment)
  -> embedding run (eligible chunks only) -> vector index (versioned, immutable once active)
                                          -> keyword index (FTS5, versioned)
retrieval profile (vector+keyword weights, boosts, budgets)
  -> retrieve() = access filter -> hybrid score -> dedupe -> rank -> diversity -> top-k
  -> context budget -> grounded prompt -> existing InferenceRuntimeService.run_generation()
  -> citation extraction/validation -> grounding quality -> answer status
```

## Package layout

- `core_model/rag/` — 20 pure-function modules, no I/O, no `Settings`
  dependency, fully unit-tested in `tests/core_model/test_phase16_rag.py`.
- `backend/models/rag.py` — Pydantic request/response schemas.
- `backend/database/repositories/rag.py` — the 24-table repository,
  `public_row()`/`INTERNAL`-stripping pattern identical to every prior
  phase's repository.
- `backend/services/rag_ingestion_service.py` — spaces, sources,
  versions, chunk sets, embedding models/runs, vector/keyword indexes.
- `backend/services/rag_retrieval_service.py` — retrieval profiles and
  the hybrid `retrieve()` flow.
- `backend/services/rag_generation_service.py` — grounded answers and
  the admin RAG Chat Lab, built on Phase 15's `InferenceRuntimeService`
  and `ModelAssignmentService`.
- `backend/services/rag_evaluation_service.py` — evaluation suites,
  fixtures, runs, metrics, index comparison, and the RAG manifest.
- `backend/api/routes/rag.py` — 63 routes under `/api/admin/rag`, every
  mutation behind `require_admin` + CSRF.
- `backend/rag_cli.py` — 16 operator subcommands.
- `apps/admin-dashboard/src/pages/RagPage.jsx` — 17-tab admin UI.

## What Phase 16 deliberately does not do

- No automatic public chatbot activation. `POST /api/chat` is unchanged
  and still returns `{"model": "placeholder"}` after every RAG operation
  exercised in this phase's tests.
- No web search, no external model providers, no tool calling.
- No claim that retrieval or grounding guarantees factual correctness —
  every user-facing surface (API disclaimers, admin UI notices, the
  manifest's `known_limitations` field) states this explicitly.
- No second inference runtime or model loader: `RagGenerationService`
  calls `ModelAssignmentService.ensure_instance_loaded()` (a new public
  entrypoint added to Phase 15's own service, exposing the existing
  private load pipeline) and `InferenceRuntimeService.run_generation()`
  unchanged.

See `docs/database_schema_v16.md` for the schema, and the per-subsystem
docs (`rag_knowledge_ingestion.md`, `rag_chunking.md`,
`rag_hybrid_retrieval.md`, `rag_citations_and_grounding.md`,
`rag_evaluation.md`) for detail.

## Phase 17 addendum

Phase 17's `ChatOrchestrationService` calls
`RagRetrievalService.retrieve()` unchanged to supply RAG evidence
alongside conversation memory evidence in one bounded, orchestrated
context — no second retrieval implementation, no second vector/keyword
index. See `docs/chat_orchestration_architecture.md` and
`docs/context_orchestration.md`.
