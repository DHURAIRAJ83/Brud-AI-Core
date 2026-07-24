# RAG API and CLI Surfaces

## API

`backend/api/routes/rag.py`, prefix `/api/admin/rag`, 63 routes, every
mutating route behind `require_admin` + CSRF (matching the
`InferenceRuntimeService`/`ModelReleaseService` convention). Route
groups: knowledge spaces, sources, source versions, chunk sets/chunks,
embedding models/runs, vector indexes, keyword indexes, retrieval
profiles, retrieval, grounded generation, RAG Chat Lab sessions,
evaluation suites/fixtures/runs/metrics, index comparisons, and the
knowledge-space manifest. All responses expose public IDs only —
`RagRepository.public_row()` strips every internal integer foreign key
(24 column names) before a row ever reaches an API response.

## CLI

`backend/rag_cli.py`, 16 subcommands, same typed-confirmation pattern as
`model_release_cli.py`/`inference_runtime_cli.py`:
`spaces`, `create-space`, `create-source`, `patch-source`,
`create-version`, `create-chunk-set`, `create-embedding-model`,
`run-embeddings`, `build-indexes` (requires typed confirmation —
activates a production-facing vector+keyword index pair, deprecating
any prior active index for the space), `create-retrieval-profile`,
`retrieve`, `grounded-answer`, `create-evaluation-suite`, `add-fixture`,
`run-evaluation`, `generate-manifest`, `verify-manifest`.

Verified end-to-end via the CLI directly against a scratch database:
space → source → approve → version → chunk-set → embedding model →
`run-embeddings` → `build-indexes` (typed confirmation) →
`create-retrieval-profile` → `retrieve` (real Tamil query, correct
result) → `create-evaluation-suite` → `add-fixture` → `run-evaluation`
→ `generate-manifest` → `verify-manifest` (`matches: true`).
