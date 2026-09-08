# P17.3 Deduplication Boundary Report

**Target Scope**: Deduplication Boundary Specification between Phase 17.3 and Phase 17.4  
**Date**: 2026-09-06  

---

## 1. Boundary Matrix

| Capability / Function | Phase 17.3 Scope (Implemented) | Phase 17.4 Scope (Deferred) |
|---|---|---|
| **Exact Match Deduplication** | Canonical match on exact normalized string $\to$ `evidence_count += 1`. | Reused as base deterministic gate. |
| **Evidence Count Counter** | Handled natively in MemoryIntelligenceEngine and MemoryService. | Reused during cluster consolidation. |
| **Normalized Text Equality** | Casing, punctuation, and script normalization handled in Phase 17.3. | Extended to phonetic/sub-word tokens. |
| **Semantic Vector Clustering** | **NOT in Phase 17.3** (clean hook provided). | Deep cosine distance thresholding ($\ge 0.88$) and near-duplicate clustering. |
| **Near-Duplicate Graph Consolidation** | **NOT in Phase 17.3**. | Graph component merging with canonical exemplar selection. |
| **Conflict Detection** | **NOT in Phase 17.3**. | Phase 17.5 contradiction resolution. |

---

## 2. Invariant Verification

- **Zero Row Explosion**: Re-submitting the same fact 20 times produces exactly 1 database row with `evidence_count = 20`.
- **No Premature Semantic Clustering**: Phase 17.3 avoids heavy vector graph operations, preserving low latency and determinism.
