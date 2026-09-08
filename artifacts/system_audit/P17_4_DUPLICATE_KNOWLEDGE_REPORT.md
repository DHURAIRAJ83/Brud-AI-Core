# P17.4 Duplicate Knowledge Report: Brud Mini Brain Intelligence 2.0

**Audit Date**: 2026-09-06  
**Auditor**: Antigravity AI Engineering Assistant  
**Target Scope**: Phase 17.4 — Duplicate Knowledge Control Layer  
**Baseline Status**: 196 Historical & Prior Phase Tests PASS (100%)

---

## 1. Executive Summary

Phase 17.4 implements **Semantic Duplicate Knowledge Control** for the Brud Mini Brain / Admin Assistant Runtime.

The layer integrates seamlessly into the memory lifecycle, providing:
1. **Multi-State Similarity Classification**: Distinguishes `EXACT_DUPLICATE`, `NORMALIZED_DUPLICATE`, `SEMANTIC_DUPLICATE`, `RELATED_BUT_DISTINCT`, `POSSIBLE_CONFLICT`, and `DISTINCT`.
2. **64-Dimensional Local Vector Embedding Reuse**: Reuses `core_model.rag.embedding` (`local_custom_embedding`) with zero heavy ML/NLP frameworks.
3. **Scoped Candidate Retrieval**: Enforces strict participant scope, category, and purpose boundaries (max 20 candidates).
4. **Deterministic Canonical Selection**: Selects canonical records based on confidence, importance, evidence count, and provenance stability.
5. **Semantic Reinforcement**: Increments `evidence_count` without inserting duplicate rows in SQLite.
6. **Contradiction & Distinction Guard**: Classifies related but distinct facts as `RELATED_BUT_DISTINCT` and flags conflicting claims as `POSSIBLE_CONFLICT` for Phase 17.5.
7. **System / Admin Governance Boundary**: Enforces `REVIEW_REQUIRED` for sensitive categories before canonical mutation.
8. **G8 Secret Scrubbing**: Redacts secrets from embeddings, logs, and `SEMANTIC_REINFORCED` events.

---

## 2. Architecture & Decision Pipeline

```mermaid
flowchart TD
    Candidate[New Memory Candidate] --> G8Sanitize[1. G8 Secret Sanitization]
    G8Sanitize --> Norm[2. Normalization]
    Norm --> ExactCheck{3. Exact / Normalized Match in Scope?}
    ExactCheck -- Match Found --> ExactReinforce[4. Reinforce: evidence_count += candidate.evidence_count]
    ExactCheck -- No Match --> ScopedFetch[5. Scoped Candidate Retrieval (max 20 candidates)]
    ScopedFetch --> ComputeEmbed[6. Compute 64-Dim Local Embedding]
    ComputeEmbed --> CosineScore[7. Cosine Similarity Scoring]
    CosineScore --> Classify{8. Similarity Classification}
    
    Classify -- sim >= 0.88 (Compatible) --> SemDup[9. SEMANTIC_DUPLICATE]
    Classify -- 0.65 <= sim < 0.88 --> RelDistinct[10. RELATED_BUT_DISTINCT -> Store as Separate Memory]
    Classify -- Parameter Contradiction --> PossConflict[11. POSSIBLE_CONFLICT -> Flag for Phase 17.5]
    Classify -- sim < 0.65 --> Distinct[12. DISTINCT -> Store as New Memory]
    
    SemDup --> GovCheck{Category is SYSTEM / ADMIN?}
    GovCheck -- Yes --> ReviewReq[13. REVIEW_REQUIRED -> Admin Approval Gate]
    GovCheck -- No --> CanonSelect[14. Deterministic Canonical Selection]
    CanonSelect --> SemReinforce[15. Semantic Reinforcement: evidence_count += count, Log SEMANTIC_REINFORCED Event]
```
