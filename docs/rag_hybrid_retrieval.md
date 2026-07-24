# Hybrid Retrieval

`RagRetrievalService.retrieve()`:

1. Classify and normalize the query (`core_model.rag.language_routing`,
   `core_model.rag.query_normalization` — original query is never
   discarded, only its checksum is kept alongside the normalized form).
2. Gather vector candidates (active vector index, brute-force numpy
   scoring) and keyword candidates (active keyword index, FTS5 `bm25()`)
   independently, each `normalize_scores()`-bounded to [0, 1]-ish before
   combining.
3. **Apply access filters BEFORE scoring is finalized** — approval
   status, licence status, language, record type, source/version
   filters (`core_model.rag.access_filter.apply_access_filters`,
   `require_approved_sources` always checked first, a `blocked` licence
   always excludes a candidate regardless of any other filter). A
   blocked or inaccessible chunk never enters the candidate pool, never
   merely hidden from citations afterward.
4. Compute the combined score (`core_model.rag.hybrid_retrieval.
   compute_combined_score`): weighted sum of vector/keyword scores plus
   heading/exact-match/language-match boosts, configured per retrieval
   profile.
5. Collapse exact duplicates (`collapse_exact_duplicates`, keeps the
   highest-scoring copy per content checksum, deterministic tie-break) —
   always applied; near-duplicate collapsing is a documented, honest
   scope limit (reported via chunk quality issues, not yet collapsed at
   retrieval time).
6. Rank with a deterministic tie-break (`rank_with_tie_break`, sorted by
   `(-combined_score, chunk_public_id)`), filter below
   `minimum_score`, optionally enforce source diversity, truncate to
   `final_top_k`.
7. Persist the retrieval run and every retrieved-chunk row (append-only
   evidence), and return the ranked results.

## Retrieval profiles must be active

`rag_retrieval_profiles.status` moves `draft → validated → active →
archived` via explicit `validate_profile()`/`activate_profile()` calls
(the latter added during implementation — an earlier version had no
path to promote a profile to `active` at all, and `retrieve()` performed
no status check whatsoever, silently accepting a `draft` profile). Fixed
so `retrieve()` now requires `status == 'active'`, failing closed
otherwise.

## A real `sqlite3.Row.get()` bug

`_gather_candidates()` originally called
`keyword_index.get("storage_key")` on a bare `sqlite3.Row` (from
`active_keyword_index_for_space`, which does not join extra columns) —
`sqlite3.Row` has no `.get()` method, raising `AttributeError` on every
retrieval that had an active keyword index. Fixed to direct-index the
column (`keyword_index["storage_key"]`), which SQLite returns as `None`
when absent.
