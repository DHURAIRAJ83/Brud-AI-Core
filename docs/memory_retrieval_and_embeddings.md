# Memory Retrieval and Embeddings

## Retrieval profiles

`memory_retrieval_profiles`: `keyword_weight`, `vector_weight`,
`recency_weight`, `user_confirmed_boost`, `maximum_results`,
`minimum_score`, `maximum_memory_tokens`, `conflict_policy`
(`prefer_recent|prefer_user_confirmed|exclude_conflicting`), plus
`allowed_categories`/`allowed_purposes` allow-lists. Must be
`validated` then `activated` before use, same lifecycle as every
other profile-shaped resource in this codebase.

## Retrieval flow

`MemoryService.retrieve()`:

1. Loads only `active` memory items for the requesting
   `participant_scope_key` — the participant filter is applied at the
   SQL query itself, before any scoring, which is what makes
   cross-participant leakage structurally impossible rather than
   merely unlikely (verified directly in manual verification Path H).
2. Computes a keyword (word-overlap) score and a vector (cosine
   similarity) score per candidate, combined via
   `compute_combined_score()`.
3. Applies the profile's `minimum_score` threshold and
   `maximum_results` cap.
4. Records the run as an append-only `memory_retrieval_runs` /
   `memory_retrieval_results` pair — every retrieval is itself
   auditable and reproducible.

## Embeddings: real, reused, never a second implementation

Vector scoring reuses Phase 16's
`core_model.rag.embedding.compute_embedding`/`pack_vector`/
`unpack_vector` and `core_model.rag.vector_index.score_vectors`
unchanged — there is no second embedding algorithm or vector-index
implementation anywhere in this phase.

`MemoryService._ensure_embedding_model_id()` find-or-creates exactly
one row, `memory_local_embedding` v1 (`local_custom_embedding`
provider, 64 dimensions), directly in Phase 16's own
`rag_embedding_models` table — reused, not duplicated, the first time
any embedding is needed. Every memory item version gets an embedding
computed and stored automatically inside `_record_version()`, into
append-only `memory_embeddings` (no `is_active` column — eligibility
is always derived by joining to `memory_items.status='active'` at
query time).

## Why this needed a real fix during implementation

Early in this phase, the deterministic (hashing-trick) embedding was
wired in but effectively untested against a real query: an
`assistant_inferred`, human-confirmed memory item ("wants to learn
Tamil grammar") failed to retrieve at all under keyword-overlap
scoring alone, because the query and the stored phrase shared no
tokens. Adding real embedding-based scoring resolved every case with
genuine token or semantic overlap; the one remaining case (near-zero
overlap between very differently-phrased text) is an honest precision
limit of an untrained hashing embedding at this scale, not a bug — the
same category of limitation Phase 16 already documented for its own
embeddings.
