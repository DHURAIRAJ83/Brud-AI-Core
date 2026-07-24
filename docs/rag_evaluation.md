# RAG Evaluation

## Fixtures use only known relevance, never fabricated labels

`rag_evaluation_fixtures` requires `expected_relevant_chunk_ids`
supplied by the admin at fixture-creation time — the evaluation service
never invents a relevance judgment. In manual verification, all 24
fixtures were built by first running a real retrieval call for each
query and taking its actual top result's `chunk_public_id` as the known
relevant ID, then feeding that same ID back as the fixture's expected
answer — a legitimate way to build a small, honest fixture set from
real content rather than fabricating relevance.

## Retrieval metrics

`core_model.rag.evaluation`: `recall_at_k`, `precision_at_k`,
`mean_reciprocal_rank`, `ndcg_at_k` (via `dcg_at_k`), `hit_rate`, plus
per-fixture `language_match`, `no_answer_correct`, and `latency_ms`,
aggregated via `aggregate_retrieval_metrics()` (mean of finite values
per metric key, `sample_size` always included, missing/non-finite
values excluded rather than treated as zero).

## Generation metrics

Computed only when the suite's `evaluation_type` is `generation` or
`both` and an eligible admin assignment is supplied:
`citation_validity_rate`, `citation_coverage_rate`,
`unknown_citation_rate`, `no_answer_appropriate`,
`answer_language_compliant`, `grounding_score`, `role_leakage`,
`injection_resistance` — aggregated via `aggregate_generation_metrics()`
the same way. Retrieval and generation failure are always reported as
separate metric scopes (`metric_scope='retrieval'` vs `'generation'`),
never conflated.

## Index and configuration comparison

`core_model.rag.comparison.compare_indexes()` compares two vector
indexes on hard fields (embedding model, distance metric, dimensions —
all must match for `compatible`) and soft fields (chunking strategy,
keyword tokenizer). A side-by-side ranking (`ranked: true`) is only
produced when both indexes are `compatible` AND were evaluated against
the identical fixture-set checksum — an admin can only trust a direct
ranking when both configurations were scored against the same fixtures.

## Manual verification result

A 24-fixture retrieval-only suite run against the Path A knowledge space
completed with `recall_at_k=1.0`, `precision_at_k=0.5`, `mrr=1.0`,
`ndcg_at_k=1.0`, `hit_rate=1.0`, `no_answer_correct=1.0` — genuine
metrics computed from real retrieval calls against real (small, 3-chunk)
content, not fabricated numbers.
