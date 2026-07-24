# Admin Dashboard — Knowledge & RAG

`apps/admin-dashboard/src/pages/RagPage.jsx`, registered as "Knowledge &
RAG" in the sidebar (`components/Sidebar.jsx`) and `App.jsx`, right after
"Inference Runtime". 17 tabs: Overview, Knowledge Spaces, Sources,
Source Versions, Chunking, Chunk Quality, Embedding Models, Embedding
Runs, Vector Indexes, Keyword Indexes, Retrieval Profiles, Retrieval
Lab, Grounded Generation, RAG Chat Lab, Evaluation, Index Comparison,
Manifest.

Required disclaimers shown on the page (matching the API's own
disclaimer strings):

- "Retrieval and grounded generation do not guarantee factual
  correctness. This is an admin-only diagnostic and evaluation
  workspace -- it does not affect the public chatbot." (header, always
  visible)
- "Phase 16 does not add any path to public-chat activation. The public
  chatbot remains the unchanged placeholder." (header, always visible)
- "Admin-only grounded diagnostic. This is not the public chatbot."
  (Grounded Generation and RAG Chat Lab tabs — identical string to
  `RagGenerationService.DIAGNOSTIC_DISCLAIMER`)
- A chunk-injection-quarantine notice (Chunk Quality and Retrieval Lab
  tabs)
- The FTS5 Tamil-tokenization limitation notice (Keyword Indexes tab)
- The manifest's no-raw-content/no-paths/no-secrets guarantee (Manifest
  tab)

All mutating actions (create/build/activate/validate) go through the
same `services/api.js` request helper used by every other page, which
automatically attaches the CSRF header on non-GET requests.

Verified via `npm run build` (production build succeeds, 383 KB bundle)
and by tracing every button's data flow against the same API responses
already exercised in `tests/backend/test_rag_api.py` and the manual
verification run — an interactive browser session was not performed in
this environment (no browser-automation tool was available), so this
should be treated as build-verified and data-flow-traced rather than
click-tested.
