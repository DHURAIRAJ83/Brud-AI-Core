# Database Schema v16 (Phase 16)

Migration `016_phase16_rag_grounded_answering` upgrades schema version
15 → 16. It is a separate, independent migration function (`_apply_v16`)
from migration 015 — Phase 15's `_apply_v15` is unchanged in behavior
and content.

## New tables

| Table | Purpose | Mutability |
|---|---|---|
| `rag_knowledge_spaces` | A named collection of approved sources sharing one retrieval configuration and lifecycle. | Mutable lifecycle row |
| `rag_knowledge_sources` | A registered source (8 types) with approval/licence status. | Mutable lifecycle row |
| `rag_source_versions` | Immutable content snapshot per source; a new checksum always produces a new version row, never an in-place update. | Mutable lifecycle row (status only: `processing→ready→superseded/failed/archived`) |
| `rag_chunk_sets` | One deterministic chunking pass over a source version. | Mutable lifecycle row |
| `rag_chunks` | Individual chunk text, quality status, injection status, location. | Append-only |
| `rag_embedding_models` | Registered embedding provider (`local_sentence_transformer`, `local_custom_embedding`, `deterministic_test_embedding`). | Mutable lifecycle row |
| `rag_embedding_runs` | One embedding computation pass over a chunk set (two-phase draft→running→completed). | Mutable lifecycle row |
| `rag_chunk_embeddings` | Packed float32 vector per eligible chunk. | Append-only |
| `rag_vector_indexes` | Versioned, checksum-tracked vector index (`repository_flat` — no FAISS dependency); immutable once `active`. | Mutable lifecycle row |
| `rag_keyword_indexes` | Versioned FTS5-backed keyword index. | Mutable lifecycle row |
| `rag_retrieval_profiles` | Hybrid vector+keyword weighting, boosts, budgets, and no-answer threshold. | Mutable lifecycle row |
| `rag_retrieval_runs` | One retrieval execution (query checksum, filters, top-k config, timing). | Append-only |
| `rag_retrieved_chunks` | Per-run ranked candidate scores. | Append-only |
| `rag_context_assemblies` | The token-budget accounting for one grounded-generation prompt. | Append-only |
| `rag_grounded_requests` | One grounded-generation request; created `accepted`, updated in place to its terminal status (`completed`/`insufficient_evidence`/`retrieval_failed`/`generation_failed`/`blocked_evidence`) — see note below. | **Mutable** (deliberate deviation, see below) |
| `rag_grounded_answers` | Answer checksum (never raw text), status, leakage/unicode flags. | Append-only |
| `rag_answer_citations` | Per-citation-label validation outcome. | Append-only |
| `rag_grounding_issues` | Fixed 23-code grounding issue evidence. | Append-only |
| `rag_evaluation_suites` | A named, versioned fixture collection. | Mutable lifecycle row |
| `rag_evaluation_fixtures` | Hand-composed query + known relevant chunk/source IDs — never fabricated relevance labels. | Append-only |
| `rag_evaluation_runs` | One evaluation execution (two-phase draft→running→completed). | Mutable lifecycle row |
| `rag_evaluation_metrics` | Per-run, per-scope (retrieval/generation) named metric values. | Append-only |
| `rag_index_comparisons` | Field-diff + compatibility verdict between two indexes. | Append-only |
| `rag_manifests` | Deterministic RAG manifest JSON + SHA-256 checksum per knowledge space. | Append-only |

24 tables total: 12 mutable lifecycle rows, 12 append-only evidence
tables.

## `rag_grounded_requests` is mutable, not append-only

Its evidence-adjacent name suggests append-only, but a request is
created once retrieval succeeds (`status='accepted'`) and must be moved
to a terminal status as generation proceeds — a genuine two-phase
create-then-resolve lifecycle, exactly like `rag_embedding_runs` and
`rag_evaluation_runs` (both also mutable for the same reason). This
mirrors Phase 13's own precedent of documenting `model_evaluation_runs`
as a "Mutable lifecycle row" despite sitting among append-only evidence
tables. The truly immutable evidence — the answer's checksum, its
citations, and any grounding issues raised against the request — still
lives in genuine append-only tables (`rag_grounded_answers`,
`rag_answer_citations`, `rag_grounding_issues`).

This was caught as a real bug during implementation: an earlier version
of the migration marked `rag_grounded_requests` append-only, which made
every grounded-answer call fail with `sqlite3.IntegrityError: grounded
requests are append-only` the moment the service tried to update the
request's terminal status. Fixed by removing the `BEFORE
UPDATE`/`BEFORE DELETE` triggers for this table only.

## Reused `admin_diagnostic` assignment scope

Phase 16 does not add a new `admin_rag_lab` value to
`inference_assignment_scopes.scope_key`'s CHECK constraint. SQLite's
`foreign_keys` pragma cannot be toggled mid-transaction (verified
directly), and `initialize_database()` applies every migration inside
one shared transaction, so a table rebuild to widen that CHECK
constraint cannot safely happen inside `_apply_v16`. RAG generation
instead reuses the existing `admin_diagnostic` scope value; all
RAG-specific eligibility requirements (active knowledge space, active
indexes, active retrieval profile, non-registry-fixture,
non-evaluation-blocked release) are enforced entirely inside
`RagGenerationService`, not via a new schema-level scope value. See
`backend/database/schema.py`'s comment directly above `PHASE16_SCHEMA`.

## No FAISS, no sentence-transformers

Neither package is installed in this environment, and Phase 16 does not
add them as new dependencies (per the phase constraint against silently
downloading a model). `rag_vector_indexes.index_type` defaults to
`repository_flat`: vectors are packed float32 BLOBs stored directly in
`rag_chunk_embeddings.vector_blob`, scored via brute-force numpy at
query time. `local_custom_embedding` is a real, deterministic, CPU-only
hashing-trick embedding (character 3-grams + word tokens, L2-normalized)
computed with only `numpy`; `local_sentence_transformer` is registered
at the schema/enum level for future use but raises `NotImplementedError`
if invoked, with an honest message. See `docs/rag_embeddings.md`.

## Verification performed

- Fresh database initialization reaches schema version 16 with all 24
  `rag_%` tables present, `PRAGMA integrity_check` returns `ok`, and
  `PRAGMA foreign_key_check` returns no rows.
- Upgrading a v15 database preserves all Phase 1-15 data (verified with
  a planted `dataset_sources` row surviving the v15→v16 upgrade).
- Migration 016 is idempotent (`initialize_database()` called 3× records
  exactly one `schema_migrations` row for version 16).
- Migration 015 is unaffected in isolation.
- All 24 tables, their indexes, and their triggers are byte-for-byte
  deterministic across two independently initialized fresh databases.
- Every append-only table rejects `UPDATE` and `DELETE` with
  `sqlite3.IntegrityError`; every mutable table accepts in-place status
  transitions.

See `tests/database/test_phase16_migration.py` (9 tests, all passing).
