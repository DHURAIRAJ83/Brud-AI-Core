# BRUD AI — RAG SYSTEM AUDIT (WS07)
**Audit Date:** 2026-09-07

---

## RAG PIPELINE

```
Document Input
    ↓
RagIngestionService (backend/services/rag_ingestion_service.py — 46 KB)
    ↓
Chunking (core_model/rag/chunking.py)
    ↓
Embedding (core_model/rag/embedding.py)
    ↓
Vector storage (SQLite via RagRepository)
    ↓ [on query]
RagRetrievalService (backend/services/rag_retrieval_service.py — 21 KB)
    ↓
HybridRetrieval (core_model/rag/hybrid_retrieval.py)
    ├─ VectorIndex (core_model/rag/vector_index.py)
    └─ KeywordIndex (core_model/rag/keyword_index.py)
    ↓
Reranking (core_model/rag/reranking.py)
    ↓
RagGenerationService (backend/services/rag_generation_service.py — 29 KB)
    ↓
InferenceRuntimeService (Phase 15 core model)
    ↓
Answer with citations
```

---

## RAG COMPONENTS

### Core Logic (core_model/rag/)
| File | Status | Purpose |
|------|--------|---------|
| `chunking.py` | ACTIVE | Text chunking |
| `chunk_validation.py` | ACTIVE | Chunk validation |
| `embedding.py` | ACTIVE | compute_embedding(), pack/unpack_vector |
| `vector_index.py` | ACTIVE | score_vectors() cosine similarity |
| `keyword_index.py` | ACTIVE | BM25-style keyword search |
| `hybrid_retrieval.py` | ACTIVE | Combined vector + keyword |
| `reranking.py` | ACTIVE | Result reranking |
| `context_builder.py` | ACTIVE | Context construction |
| `context_budget.py` | ACTIVE | Context window budget |
| `citation_builder.py` | ACTIVE | Citation construction |
| `language_routing.py` | ACTIVE | Language classification |
| `access_filter.py` | ACTIVE | Scope-based access control |
| `answer_policy.py` | ACTIVE | Answer policy rules |
| `grounding_checks.py` | ACTIVE | Grounding verification |
| `injection_filter.py` | ACTIVE | Prompt injection protection |
| `query_normalization.py` | ACTIVE | Query preprocessing |
| `text_normalization.py` | ACTIVE | Text normalization |
| `evaluation.py` | ACTIVE | RAG quality evaluation |
| `manifest.py` | ACTIVE | RAG manifest |
| `comparison.py` | ACTIVE | Comparison utilities |
| `language_routing.py` | ACTIVE | Tamil/English/Tanglish routing |

### Backend Services (rag_*.py)
| Service | Size | Status |
|---------|------|--------|
| `rag_ingestion_service.py` | 46 KB | ACTIVE |
| `rag_retrieval_service.py` | 21 KB | ACTIVE |
| `rag_generation_service.py` | 29 KB | ACTIVE |
| `rag_evaluation_service.py` | 4.7 KB | ACTIVE |
| `rag_release_service.py` | 3.5 KB | ACTIVE |

### RAG Sandbox
| Service | Size | Status |
|---------|------|--------|
| `rag_sandbox_answer_service.py` | 10 KB | ACTIVE |
| `rag_sandbox_corpus_service.py` | 19 KB | ACTIVE |
| `rag_sandbox_deletion_service.py` | 7 KB | ACTIVE |
| `rag_sandbox_eligibility_service.py` | 20 KB | ACTIVE |
| `rag_sandbox_evaluation_service.py` | 13 KB | ACTIVE |
| `rag_sandbox_index_service.py` | 12 KB | ACTIVE |
| `rag_sandbox_retrieval_service.py` | 9 KB | ACTIVE |
| `rag_sandbox_report_service.py` | 15 KB | ACTIVE |
| `rag_sandbox_acceptance_service.py` | 5 KB | ACTIVE |
| `rag_sandbox_query_set_service.py` | 5 KB | ACTIVE |
| `rag_sandbox_human_review_service.py` | 3.7 KB | ACTIVE |

---

## VECTOR DATABASE

**Primary:** SQLite (via RagRepository)
- No external vector DB (no Qdrant, no Pinecone, no Weaviate)
- Vectors stored as BLOB in SQLite
- Similarity computed in-process via `score_vectors()`

**Status:** ACTIVE — fully SQLite-based, no external vector DB

---

## RAG CONTROLLED INGESTION

`controlled_rag_ingestion_service.py` (9.7 KB) — ACTIVE
- Governed ingestion with approval gates
- Connected to RAG sandbox acceptance

---

## RAG SANDBOX (Test/Preview Environment)

The RAG Sandbox allows testing RAG responses before production release:
1. Upload corpus to sandbox
2. Create query set
3. Run sandbox retrieval + generation
4. Evaluate results
5. Human review
6. Accept or reject for production promotion

**Status:** COMPLETE — full workflow implemented

---

## SEMANTIC CHUNKING

`backend/services/semantic_chunk_service.py` (45 KB) — ACTIVE
`core_model/semantic_chunk/` — ACTIVE

This is in addition to the standard RAG chunking. Used for more sophisticated document segmentation.

---

## POSSIBLE DUPLICATE: RAG vs. RAG SANDBOX

| System | Purpose | Scope |
|--------|---------|-------|
| Production RAG | Live retrieval | Production |
| RAG Sandbox | Pre-production testing | Isolated |

**VERDICT:** Not a duplicate — different scopes. Sandbox is a preview environment.

---

## FINDINGS

1. **COMPLETE:** Full RAG pipeline implemented
2. **COMPLETE:** Hybrid retrieval (vector + keyword)
3. **COMPLETE:** RAG Sandbox for pre-production testing
4. **ACTIVE:** Semantic chunking with validation
5. **SINGLE VECTOR DB:** SQLite only — no external vector store
6. **NO DUPLICATE RAG ENGINES** detected
7. **LIMITATION:** In-memory vector scoring (no HNSW) — performance bottleneck at scale

---
*WS07 Complete*
