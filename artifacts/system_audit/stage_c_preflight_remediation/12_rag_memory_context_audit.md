# Stage C Remediation Report — 12: RAG, Memory & T=512 Context Budget Audit

**Audit Date:** 2026-09-01  
**Audit Context:** Phase 60 WS07 Stage C Pre-Flight Remediation  
**Governance Mode:** STRICT READ-ONLY, ZERO MUTATION (`training_execution_authorized = FALSE`)

---

## 1. Executive Summary & Context Budget Breakdown

Scaling context length from $T=128$ to $T=512$ tokens directly resolves the context truncation bottleneck for multi-turn dialogue memory and document RAG chunks.

### Context Window Allocation Model ($T=512$):

```text
Total Sequence Window: 512 Tokens
├── System Instructions & Control Tokens:   48 tokens ( 9.4%)
├── RAG Document Chunk (BM25 / n-gram):    250 tokens (48.8%)
├── Conversation History (SQLite memory):  110 tokens (21.5%)
└── User Query & Model Generation Target:   104 tokens (20.3%)
```

---

## 2. Separation of Bottleneck Causes

We distinguish three separate bottlenecks in the RAG & Memory pipeline:

1. **Context Window Limitation (RESOLVED BY E4 $T=512$):**
   - $T=128$ forcibly truncated document chunks > 60 words.
   - $T=512$ allows up to 250-word RAG document chunks without context overflow.

2. **Model Representational Capacity Limitation (RESOLVED BY E5 3.16M PARAMS):**
   - 528k parameters lacked capacity to extract facts from long context.
   - 3.16M parameters ($L=4, d_{model}=256$) provides representational capacity for grounded fact synthesis.

3. **Retrieval Quality Limitation (PLANNED FOR ROADMAP P2):**
   - The current n-gram character hashing approximation in `rag_service.py` handles exact keywords.
   - Dense bi-encoder embeddings will be introduced in Roadmap P2 to handle conceptual paraphrasing.
