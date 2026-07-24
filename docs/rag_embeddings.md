# Embedding Models and Runs

## Provider types

`local_sentence_transformer`, `local_custom_embedding`,
`deterministic_test_embedding`. Neither `sentence-transformers` nor
`faiss` is installed in this environment, and Phase 16 does not add
either as a new dependency (no silent model download).

- `local_custom_embedding` is the real, functional default: a
  deterministic, CPU-only hashing-trick embedding built from character
  3-grams and whitespace-delimited word tokens (SHA-256-derived bucket +
  sign per feature), L2-normalized. Verified to produce meaningfully
  higher cosine similarity between related sentences (~0.54) than
  unrelated ones (~0.03) — not a stub, a genuinely discriminative
  (if simple) embedding.
- `deterministic_test_embedding` is a SHA-256-digest-derived embedding,
  explicitly test-only.
- `local_sentence_transformer` is registered at the schema/enum level
  for future use but raises `NotImplementedError` with an honest message
  if invoked — it is never silently substituted with something else.

## Embedding runs

Two-phase lifecycle: `create_embedding_run` computes the eligible chunk
set (accepted + clean only, see `docs/rag_chunking.md`) and creates a
`draft` row; `execute_embedding_run` computes and persists one packed
float32 vector per eligible chunk (`core_model.rag.embedding.pack_vector`
/ `unpack_vector`), then marks the run `completed` (or
`completed_with_warnings`/`failed`). This mirrors the same
create-then-execute two-phase pattern already used for pretraining and
evaluation runs in earlier phases — hence `rag_embedding_runs` is a
mutable lifecycle table, not append-only, deviating from a literal
reading of the original table list for the same reason documented for
`rag_grounded_requests` (see `docs/database_schema_v16.md`).

Each run records an `input_checksum_sha256` (over the eligible chunk
IDs) and `output_manifest_checksum_sha256` (over the resulting vectors'
per-chunk checksums), independently re-verifiable via
`verify_embedding_run()`.
