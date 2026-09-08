# Master Brud AI System Audit — 06: RAG Audit

**Audit Date:** 2026-09-01  
**Auditor:** Principal AI Systems Architect & Search Engineer  
**Confidence Rating:** HIGH CONFIDENCE (Verified by source code inspection of `core_model/rag/` and `backend/services/rag_*.py`)  

---

## 1. RAG Subsystem Operational Breakdown

| Subsystem Component | Actual Implementation | Source File | Dependencies | Operational Status |
|---|---|---|---|---|
| **Document Ingestion** | Markdown, text, and PDF extraction with metadata extraction | `backend/services/document_service.py` | PyPDF2, SQLite | ✅ **OPERATIONAL** |
| **Chunking Engine** | Semantic and windowed text chunking with overlap | `core_model/rag/chunking.py` | Regex, Python stdlib | ✅ **OPERATIONAL** |
| **Chunk Validation** | Minimum length, repetition ratio, encoding, and injection checks | `core_model/rag/chunk_validation.py` | Python stdlib | ✅ **OPERATIONAL** |
| **Embedding Generation** | Deterministic CPU character n-gram hashing trick (`local_custom_embedding`) | `core_model/rag/embedding.py` | NumPy, SHA-256 | ✅ **OPERATIONAL** (Heuristic) |
| **External Embeddings** | `local_sentence_transformer` stub | `core_model/rag/embedding.py` | `sentence-transformers` | 🔴 **NOT WIRED** (Raises error if invoked) |
| **Vector Storage** | Brute-force CPU flat vector index over SQLite stored vectors | `core_model/rag/vector_index.py` | NumPy dot product | ✅ **OPERATIONAL** (CPU-flat) |
| **Vector DB (FAISS / Milvus / Chroma)**| Dedicated ANN Vector Database | None | External daemon | 🔴 **MISSING** (No FAISS/Chroma installed) |
| **Keyword Search** | BM25 / token-frequency keyword index with Tamil root matching | `core_model/rag/keyword_index.py` | Python stdlib | ✅ **OPERATIONAL** |
| **Hybrid Retrieval** | Weighted fusion of vector score and keyword score | `core_model/rag/hybrid_retrieval.py` | NumPy | ✅ **OPERATIONAL** |
| **Reranking** | Score rebalancing with recency and citation boost | `core_model/rag/reranking.py` | Python stdlib | ✅ **OPERATIONAL** |
| **Injection Filtering** | Prompt-injection guard filtering adversarial chunks | `core_model/rag/injection_filter.py` | Regex, pattern rules | ✅ **OPERATIONAL** |
| **Citation Builder** | Bracketed citation identifiers `[cite:doc_id:chunk_id]` | `core_model/rag/citation_builder.py` | Python stdlib | ✅ **OPERATIONAL** |
| **Source Tracking** | Document lineage, sha256 checksums, and version IDs | `backend/database/repositories/rag.py` | SQLite schema | ✅ **OPERATIONAL** |
| **Tenant / Scope Isolation** | Scopes: `admin_diagnostic`, `public_chat`, `sandbox` | `backend/services/public_rag_scope_resolver.py` | SQLite | ✅ **OPERATIONAL** |
| **Admin Controls & Sandbox** | Admin RAG sandbox for query inspection and retrieval testing | `backend/api/routes/rag_sandbox.py` | FastAPI | ✅ **OPERATIONAL** |

---

## 2. Critical Evaluation of the Current RAG Architecture

1. **What is Real and Operational:**
   - The entire RAG pipeline from document upload to chunking, validation, hybrid retrieval, injection filtering, and citation generation is **100% operational in code and covered by tests**.
   - It runs with zero external services (no remote vector database or cloud API required).
2. **Key Limitations & Missing Pieces:**
   - **No Deep Neural Embeddings:** The active embedding model (`local_custom_embedding`) is an n-gram hashing trick, not a trained neural bi-encoder (like BAAI/bge or multilingual E5). While deterministic and fast on CPU, semantic similarity matching on complex cross-lingual queries is limited.
   - **No Approximate Nearest Neighbors (ANN):** The vector search is an $O(N)$ flat brute-force dot product in NumPy. This works well up to ~50,000 chunks, but will not scale to millions of chunks without FAISS, HNSW, or pgvector.
   - **RAG Generation Constraint:** Even when relevant chunks are retrieved, the 528k parameter model often struggles to synthesize multi-paragraph grounded answers from context without copying verbatim or hallucinating.
