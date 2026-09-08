# Phase 61 Report — 22: Strict RAG Corpus Separation

## Isolation Rules
- RAG documents indexed for search MUST NOT automatically pollute the Foundation Pretraining Corpus.
- A clear filesystem boundary is maintained: `data/registry/rag/` vs `data/registry/foundation/`.
