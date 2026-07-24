# Vector Index

`rag_vector_indexes.index_type` is `repository_flat` (no FAISS): vectors
already persisted in `rag_chunk_embeddings.vector_blob` are scored via
brute-force numpy at query time
(`core_model.rag.vector_index.score_vectors`, supporting `cosine`,
`inner_product`, `l2`). `storage_key` is a logical string
(`"sqlite:rag_chunk_embeddings"`), not an on-disk artifact path — no
FAISS index file is ever written. `resolve_confined_path` is reused
unchanged from Phase 14's `core_model.release.artifact_inventory` for
any future on-disk-artifact path confinement.

## Lifecycle

`building → validated → active/failed/archived → deprecated`.
`build_vector_index()` computes a mapping manifest (chunk public ID →
vector checksum, sorted deterministically) and its checksum;
`validate_vector_index()` recomputes the same manifest from the live
`rag_chunk_embeddings`/`rag_chunks` join and compares checksums, failing
if they diverge; `activate_vector_index()` deprecates any prior active
index in the same knowledge space and sets `activated_at`. An `active`
index is immutable — rebuilding it is rejected outright
("an active vector index is immutable and cannot be rebuilt").

A real bug was caught and fixed during implementation:
`validate_vector_index()` originally built its comparison manifest using
the raw internal integer `chunk_id` FK instead of the chunk's real
`public_id`, which would have made the checksum comparison always
diverge from the one `build_vector_index()` correctly computed. Fixed
by adding the same `rag_chunks.public_id` join `build_vector_index()`
already used.

## Retrieval-time scoring

`RagRetrievalService._gather_candidates()` loads all embeddings for the
active index's embedding run, computes the query embedding with the
same provider/dimensions as the index's registered model, scores every
candidate, and takes `normalize_scores()` (bounded min-max, never
claimed as calibrated probability) before combining with the keyword
score. See `docs/rag_hybrid_retrieval.md`.
