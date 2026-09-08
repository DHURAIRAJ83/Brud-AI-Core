# Stage C Pre-Flight Audit — 12: RAG & Context Compatibility

**Audit Date:** 2026-09-01  
**Audit Context:** Phase 60 WS07 Stage C Pre-Flight  
**Governance Mode:** STRICT READ-ONLY, ZERO MUTATION (`training_execution_authorized = FALSE`)

---

## 1. Context Budget Analysis ($T=512$)

Scaling sequence context from $T=128$ to $T=512$ tokens directly enables full Retrieval-Augmented Generation (RAG) and multi-turn conversation memory integration.

### Token Allocation Budget for $T=512$:

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        TOTAL CONTEXT BUDGET = 512 TOKENS               │
├───────────────────┬───────────────────┬───────────────────┬────────────┤
│ System Prompt     │ Retrieved RAG     │ Conversation      │ User Query │
│ & Formatting      │ Document Chunk    │ Memory History    │ & Response │
│ (48 tokens)       │ (250 tokens)      │ (110 tokens)      │ (54 tok)   │
└───────────────────┴───────────────────┴───────────────────┴────────────┘
```

---

## 2. RAG Bottleneck Analysis: Context Length vs Semantic Embeddings

We analyzed whether the primary RAG bottleneck is **Context Length** ($T$) or **Retrieval Quality**:

1. **Context Length Bottleneck (REMOVED BY E4):**
   - At $T=128$, a single RAG document chunk (typically 150–200 words) overflowed the context window, causing catastrophic truncation of user query or generation response.
   - At $T=512$, a 250-token RAG chunk fits comfortably with room for history and system instructions.

2. **Semantic Retrieval Quality Bottleneck (PLANNED FOR ROADMAP P2):**
   - The current RAG search engine in `backend/services/rag_service.py` relies on a hybrid BM25 + character n-gram hashing approximation.
   - While effective for exact keyword and Tamil root matching, character n-gram hashing cannot resolve conceptual paraphrases.
   - **Pre-Flight Verdict:** $T=512$ completely resolves the context window bottleneck. Roadmap P2 will upgrade the retriever from n-gram hashing to a trained dense bi-encoder model.
