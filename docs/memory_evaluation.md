# Conversation Memory Evaluation

`MemoryEvaluationService` mirrors Phase 16's `RagEvaluationService`
structure: named/versioned `memory_evaluation_suites`, hand-composed
`memory_evaluation_fixtures` (participant scope key, query,
`expected_retrieved_memory_ids`, optional `expected_excluded_memory_ids`,
`expected_language`, `expected_rag_use`,
`expected_no_memory_behavior`), a `memory_evaluation_runs` row per
execution (mutable — see `docs/database_schema_v17.md` for why), and
per-fixture append-only `memory_evaluation_metrics`.

## Metrics

`core_model/conversation/evaluation.py` re-exports
`dcg_at_k`/`hit_rate`/`mean_reciprocal_rank`/`ndcg_at_k`/
`precision_at_k`/`recall_at_k`/`finite_or_none` from
`core_model.rag.evaluation` unchanged — the same ranking-quality
metrics, applied here to memory retrieval instead of chunk retrieval.
`owner_filter_accuracy` is computed against the participant's actual
owned-and-active memory item IDs read from the database at evaluation
time, never a hand-waved expression — this was a genuine bug found and
fixed during implementation (an earlier version trivially returned
100% regardless of correctness).

## Fixtures must reflect real retrieval, never fabrication

Every fixture's `expected_retrieved_memory_ids` is taken from an
actual `active` memory item created and retrievable in the same suite
run — never a fabricated ID or a guessed expectation, matching the
discipline established in Phase 16's own evaluation fixtures.

## Execution

`POST .../evaluation-suites/{id}/runs` creates a `draft` run; `POST
.../evaluation-runs/{id}/execute` runs every fixture's query against
the configured retrieval profile, scores it, and transitions the run
to `completed` — the two-phase flow that required
`memory_evaluation_runs` to be mutable in the first place.
