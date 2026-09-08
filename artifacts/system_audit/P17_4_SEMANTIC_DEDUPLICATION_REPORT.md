# Phase 17.4 — Semantic Deduplication Report

## 1. Executive Summary
Phase 17.4 enhances the Brud Mini Brain memory subsystem from exact/normalized duplicate matching to a governed multi-tier knowledge deduplication pipeline:
1. **EXACT_DUPLICATE**: Case-sensitive and whitespace-exact text match (`similarity = 1.0`).
2. **NORMALIZED_DUPLICATE**: Case-insensitive and whitespace-collapsed text match (`similarity = 0.99`).
3. **SEMANTIC_DUPLICATE**: Cosine similarity $\ge 0.88$ computed over CPU-only 64-dimensional character n-gram local embeddings with entity/predicate compatibility verification.
4. **RELATED_BUT_DISTINCT**: Cosine similarity between $0.65$ and $0.88$ or differing predicates/attributes; records are preserved as separate memories.
5. **POSSIBLE_CONFLICT**: Numerical, interval, or parameter contradictions; flagged for Phase 17.5 review without destructive overwrites.
6. **DISTINCT**: Cosine similarity $< 0.65$ or unshared topics/scopes.

---

## 2. Multi-Tier Deduplication Pipeline

```
Raw Candidate
    │
    ▼
[Step 1: G8 Secret Sanitization (sanitize_message)]
    │
    ▼
[Step 2: G5 Scope Filtering (participant_scope_key, category, purpose)]
    │  (Candidate pool capped at MAX_CANDIDATES = 20)
    │
    ▼
[Step 3: Exact / Normalized Match Guard]
    ├─► EXACT / NORMALIZED MATCH ──► Canonical Reinforcement (evidence_count += delta)
    │
    ▼ (Only if no exact/normalized match)
[Step 4: Local 64-Dim Vector Embedding (core_model.rag.embedding)]
    │
    ▼
[Step 5: Cosine Similarity Scoring (core_model.rag.vector_index)]
    │
    ▼
[Step 6: Predicate Contradiction & Parameter Check]
    │
    ├─► sim >= 0.88 & no contradiction ──► SEMANTIC_DUPLICATE ──► Canonical Reinforcement
    ├─► sim >= 0.88 & contradiction    ──► POSSIBLE_CONFLICT  ──► Quarantine & Review Flag
    ├─► 0.65 <= sim < 0.88              ──► RELATED_BUT_DISTINCT──► Store Separate Record
    └─► sim < 0.65                      ──► DISTINCT           ──► Store New Record
```

---

## 3. Technical Implementation & Invariants

| Dimension | Specification | Verification Status |
|---|---|---|
| **Embedding Engine** | `core_model/rag/embedding.py` (`local_custom_embedding`, 64-dim) | **VERIFIED** |
| **Vector Scorer** | `core_model/rag/vector_index.py` (`score_vectors`, cosine metric) | **VERIFIED** |
| **Semantic Threshold** | $\ge 0.88$ | **VERIFIED** |
| **Related Threshold** | $0.65 \le \text{sim} < 0.88$ | **VERIFIED** |
| **Max Candidates** | $\le 20$ | **VERIFIED** |
| **External Dependencies** | Zero external ML / NLP / Torch dependencies | **VERIFIED** |

---

## 4. Verification Status
- **Duplicate Knowledge Engine**: `core_model/mini_brain/intelligence/duplicate_detector.py` [VERIFIED]
- **Memory Service Integration**: `backend/services/memory_service.py` [VERIFIED]
- **Unit & E2E Tests**: 19 / 19 PASS [VERIFIED]
