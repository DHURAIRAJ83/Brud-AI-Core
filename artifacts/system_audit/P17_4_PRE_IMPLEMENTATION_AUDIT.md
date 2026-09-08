# P17.4 Pre-Implementation Audit: Semantic Duplicate Knowledge Control

**Audit Date**: 2026-09-06  
**Auditor**: Antigravity AI Engineering Assistant  
**Target Scope**: Phase 17.4 — Duplicate Knowledge Control (Semantic Deduplication)  
**Baseline Status**: 163 Historical + 18 Phase 17.2 + 15 Phase 17.3 = **196 / 196 Tests PASS (100%)**

---

## 1. Existing Deduplication & Embedding Architecture

| Component | File Path | Existing Capability | Classification |
|---|---|---|---|
| **Exact Deduplication** | `core_model/conversation/memory_deduplication.py` | Exact normalized string comparison for same category/purpose. | `EXISTING` / `REUSE` |
| **Canonical Reinforcement** | `backend/services/memory_service.py` | Exact duplicate match increments `evidence_count += 1` on canonical record without spawning duplicate rows. | `EXISTING` / `REUSE` |
| **Local 64-Dim Embedding Engine** | `core_model/rag/embedding.py` | Deterministic, CPU-only character-n-gram + token hashing vector embedding (`local_custom_embedding`). | `EXISTING` / `REUSE` |
| **Vector Similarity Scoring** | `core_model/rag/vector_index.py` | Cosine similarity scoring (`score_vectors`) and deterministic top-k ranking. | `EXISTING` / `REUSE` |
| **Semantic Deduplication Engine** | `core_model/mini_brain/intelligence/duplicate_detector.py` | **MISSING**: Scoped candidate search, multi-class semantic duplicate classification (`EXACT_DUPLICATE`, `NORMALIZED_DUPLICATE`, `SEMANTIC_DUPLICATE`, `RELATED_BUT_DISTINCT`, `POSSIBLE_CONFLICT`, `DISTINCT`), canonical selection, and semantic reinforcement ledger. | `NEW` (Target Phase 17.4) |

---

## 2. Capability Classification Matrix

| Capability Dimension | Classification | Status & Audit Findings |
|---|---|---|
| **Exact Deduplication** | `EXISTING` | Implemented in Phase 17.3; exact string match increments `evidence_count`. |
| **Normalized Deduplication** | `EXISTING` | Lowercase, whitespace, and punctuation normalization in `memory_normalization.py`. |
| **Local Embedding Generation** | `EXISTING` | `compute_embedding` (64-dim, `local_custom_embedding`) is CPU-first and zero-dependency. |
| **Cosine Vector Similarity** | `EXISTING` | `score_vectors` in `vector_index.py` verified and mathematically sound. |
| **Semantic Duplicate Classification** | `MISSING` | Multi-threshold classification (`SEMANTIC_DUPLICATE`, `RELATED_BUT_DISTINCT`, `POSSIBLE_CONFLICT`, `DISTINCT`) is missing. |
| **Scoped Candidate Retrieval** | `MISSING` | Scoped search filtering by `participant_scope_key`, `category`, and `purpose` before similarity scoring is missing. |
| **Deterministic Canonical Selection** | `MISSING` | Multi-factor canonical selection (confidence, importance, evidence count, provenance, ID tie-break) is missing. |
| **Semantic Evidence Reinforcement** | `MISSING` | Semantic duplicate merging with `SEMANTIC_REINFORCED` immutable event trail is missing. |
| **Related-But-Distinct Separation** | `MISSING` | Explicit boundary preventing merging of related but non-identical facts (e.g. backup schedule vs backup retention) is missing. |
| **Possible Conflict Boundary** | `MISSING` | Flagging conflicting values for Phase 17.5 without destructive overwriting is missing. |
| **Participant Isolation (G5)** | `EXISTING` | Isolated by `participant_scope_key` in all DB queries; must be strictly maintained. |
| **Secret Sanitization (G8)** | `EXISTING` | `message_sanitizer` must be enforced before embedding generation. |

---

## 3. Duplicate Logic & Overlap Detection

- **Deduplication Logic Consolidation**:
  - `memory_deduplication.py`'s `assess_conflict()` provides basic exact duplicate checking.
  - Phase 17.4 will introduce `core_model/mini_brain/intelligence/duplicate_detector.py` (`DuplicateKnowledgeEngine`) which acts as the comprehensive domain engine for:
    1. Exact / Normalized matching (delegating/reusing normalization).
    2. Embedding computation and scoped vector similarity comparison.
    3. Multi-tier classification.
    4. Canonical selection and reinforcement payload building.

---

## 4. Security, False-Positive, and Performance Risk Assessment

1. **False-Positive Merge Risk ("Similarity $\neq$ Truth")**:
   - *Risk*: Statements sharing high keyword overlap but stating different facts (e.g., "Backup schedule is 24h" vs "Backup retention is 30 days") could be falsely merged.
   - *Mitigation*: Multi-tier classification with calibrated thresholds (`SEMANTIC_DUPLICATE_THRESHOLD = 0.88`, `RELATED_THRESHOLD = 0.65`) and entity-predicate compatibility checks. Sub-threshold items are classified as `RELATED_BUT_DISTINCT` and kept separate.
2. **Contradiction Overwrite Risk**:
   - *Risk*: "Backup runs every 24 hours" vs "Backup runs every 12 hours" could be merged as duplicate.
   - *Mitigation*: Conflicting values are classified as `POSSIBLE_CONFLICT`, preventing automatic merging and preserving both for Phase 17.5 Conflict Detection.
3. **Autonomous Action & Governance Risk (G1)**:
   - *Risk*: Semantic deduplication could auto-update sensitive `SYSTEM`/`ADMIN` memories.
   - *Mitigation*: `SYSTEM` and `ADMIN` categories require explicit admin review before canonical update.
4. **Secret Leakage in Embeddings / Logs (G8)**:
   - *Risk*: Unsanitized credentials could be embedded or logged.
   - *Mitigation*: Mandatory `sanitize_message` and regex scrubbing before embedding generation, comparison, or event recording.
5. **Performance & Unbounded Scan Risk**:
   - *Risk*: $O(N)$ full database vector scans could degrade performance.
   - *Mitigation*: Scoped candidate retrieval (`MAX_CANDIDATES = 20`) restricted by participant scope and category; CPU-only flat scoring in $< 2\text{ ms}$.

---

## 5. Proposed Phase 17.4 Architecture & Workflow

```mermaid
flowchart TD
    NewMemory[New Memory Candidate] --> G8Sanitize[1. G8 Secret Sanitization]
    G8Sanitize --> Norm[2. Text & Script Normalization]
    Norm --> ExactCheck{3. Exact / Normalized Match in Scope?}
    ExactCheck -- Match Found --> ExactReinforce[4. Reinforce: evidence_count += candidate.evidence_count]
    ExactCheck -- No Match --> ScopedFetch[5. Scoped Candidate Retrieval (max 20 candidates)]
    ScopedFetch --> ComputeEmbed[6. Compute 64-Dim Candidate Embedding]
    ComputeEmbed --> CosineScore[7. Cosine Similarity Scoring against Active Memories]
    CosineScore --> Classify{8. Similarity Classification}
    
    Classify -- sim >= 0.88 (Same Predicate) --> SemDup[9. SEMANTIC_DUPLICATE]
    Classify -- 0.65 <= sim < 0.88 --> RelDistinct[10. RELATED_BUT_DISTINCT -> Store as Separate Memory]
    Classify -- Same Subject, Conflicting Value --> PossConflict[11. POSSIBLE_CONFLICT -> Flag for Phase 17.5]
    Classify -- sim < 0.65 --> Distinct[12. DISTINCT -> Store as New Memory]
    
    SemDup --> GovCheck{Category is SYSTEM / ADMIN?}
    GovCheck -- Yes --> ReviewReq[13. REVIEW_REQUIRED -> Admin Approval Gate]
    GovCheck -- No --> CanonSelect[14. Deterministic Canonical Selection]
    CanonSelect --> SemReinforce[15. Semantic Reinforcement: evidence_count += count, Log SEMANTIC_REINFORCED Event]
```
