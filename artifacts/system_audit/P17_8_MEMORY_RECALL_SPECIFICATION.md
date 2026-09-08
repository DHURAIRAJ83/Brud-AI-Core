# PHASE 17.8 — MEMORY RECALL & RETRIEVAL INTELLIGENCE SPECIFICATION
# ARCHITECTURAL SPECIFICATION & SYSTEM DESIGN

**Document ID**: `P17_8_MEMORY_RECALL_SPECIFICATION`  
**Phase**: Phase 17.8 (Brud Mini Brain — Memory Recall & Retrieval Intelligence)  
**Status**: SPECIFICATION COMPLETE (STAGE A)  
**Target Engine**: `core_model/mini_brain/intelligence/memory_recall.py`  
**Target Service Integration**: `backend/services/memory_service.py`  

---

## 1. Executive Overview

The purpose of Phase 17.8 (Memory Recall & Retrieval Intelligence) is to establish a deterministic, governed, multi-signal memory recall system for the Brud Mini Brain. Memory recall is not a naive keyword or raw SQL query; it is a multi-stage cognitive retrieval engine that synthesizes semantic relevance, lexical overlap, recency/freshness, confidence calibration, importance weighting, evidence strength, contextual topics, dispute safety locks, and consolidation provenance.

### Core Architectural Principles:
1. **CPU-First & Deterministic**: 100% deterministic mathematical scoring utilizing existing 64-dimensional character n-gram embeddings (`local_custom_embedding`). Zero GPU, PyTorch, or Transformer dependencies.
2. **Zero Schema Alterations**: 100% compatible with existing SQLite schema (`memory_items`, `memory_retrieval_profiles`, `memory_retrieval_runs`, `memory_retrieval_results`). Zero database migrations.
3. **Separation of Freshness and Truth**: Freshness is a ranking signal, not a truth validity determinant. Stale or aged memories retain historical truth validity.
4. **Consolidation Lineage & Anti-Duplication**: Canonical memories take precedence while preserving constituent provenance; raw constituent memories are suppressed from duplicate result flooding.
5. **Dispute Isolation & Warning Annotations**: Unresolved disputes (`DETECTED`, `PENDING_REVIEW`, `UNDER_REVIEW`) are strictly governed (excluded or tagged with mandatory advisory warnings).
6. **Strict Multi-Tenant Isolation (G5)**: Strict participant scope confinement (`participant_scope_key`). Zero cross-participant recall leakage.
7. **G1 Governance & G8 Secret Sanitization**: Elevated protection for SYSTEM and ADMIN memories; full redaction of credentials in retrieved text and query logs.

---

## 2. Capability Audit Matrix

| Component | Codebase Status | Existing Location | Target Phase 17.8 Role |
|---|---|---|---|
| **Access Filtering** | `EXISTS` | `core_model/conversation/memory_retrieval.py` | Filter by participant scope, status, category, purpose whitelists. |
| **Flat Vector Scoring** | `EXISTS` | `core_model/rag/vector_index.py` | Cosine similarity scoring over 64-dim embeddings. |
| **Local Custom Embeddings** | `EXISTS` | `core_model/rag/embedding.py` | Deterministic character 3-gram hashing trick embeddings. |
| **Keyword Token Match** | `EXISTS` | `backend/services/memory_service.py` | Token intersection and lexical overlap calculation. |
| **Combined Score Formula** | `PARTIAL` | `core_model/conversation/memory_ranking.py` | Requires consolidation and context intelligence integration. |
| **Context Boosts** | `EXISTS` | `core_model/mini_brain/intelligence/context_intelligence.py` | Topic & task transition tracking and keyword matching. |
| **Lifecycle & Freshness** | `EXISTS` | `core_model/mini_brain/intelligence/memory_lifecycle.py` | Category TTLs, age calculation, freshness penalty scale (0, 5, 15, 40). |
| **Consolidation Lineage** | `EXISTS` | `core_model/mini_brain/intelligence/memory_consolidator.py` | Canonical memory detection and source provenance linking. |
| **Dispute Conflict Gate** | `EXISTS` | `core_model/mini_brain/intelligence/conflict_detector.py` | Dispute detection, status tracking, and warning formatting. |
| **Pure Recall Domain Engine** | `MISSING` | Proposed `memory_recall.py` | Pure deterministic domain engine uniting all signals. |
| **Multi-Mode Retrieval** | `PROPOSED` | Proposed in `memory_recall.py` | `CURRENT`, `HISTORICAL`, `TASK`, `PREFERENCE` retrieval modes. |
| **Deduplication / Diversity** | `PROPOSED` | Proposed in `memory_recall.py` | Suppress constituent memories if canonical record is retrieved. |

---

## 3. Retrieval Modes Specification

Phase 17.8 formally specifies four distinct retrieval modes:

1. **`CURRENT` Mode (Default)**:
   - **Target**: Active, confirmed, and freshly relevant knowledge for real-time conversation.
   - **Allowed Statuses**: `active` only.
   - **Dispute Handling**: Unresolved disputes excluded or annotated based on profile policy.
   - **Freshness Policy**: FRESH and AGING prioritized; STALE penalized (-15); EXPIRED excluded or heavily penalized (-40).
   - **Consolidation**: Canonical memories prioritized; constituent source memories suppressed.

2. **`HISTORICAL` Mode**:
   - **Target**: Retrospective queries, audit investigations, timeline tracking, and historical fact retrieval.
   - **Allowed Statuses**: `active`, `superseded`, `expired`, `archived`.
   - **Dispute Handling**: Returns historical dispute states and resolution metadata.
   - **Freshness Policy**: Freshness penalty disabled or neutralized (evaluates historical validity).
   - **Consolidation**: Returns both canonical and constituent records with explicit lineage tags.

3. **`TASK` Mode**:
   - **Target**: Execution context, workflow progress, step-by-step task instructions.
   - **Allowed Categories**: `TASK`, `PROCEDURAL`.
   - **Freshness Policy**: Strict 1-day TTL decay; expired task items excluded.

4. **`PREFERENCE` Mode**:
   - **Target**: User formatting, tone, language, and project preferences.
   - **Allowed Categories**: `PREFERENCE`.
   - **Freshness Policy**: 180-day ultra-slow decay; preferences retained across long idle intervals.

---

## 4. Pure Domain Engine Contract (`MemoryRecallEngine`)

In Stage B, a pure domain engine `MemoryRecallEngine` will be created in `core_model/mini_brain/intelligence/memory_recall.py`:

```python
class MemoryRecallEngine:
    @classmethod
    def recall_memories(
        cls,
        *,
        query: str,
        candidates: list[dict[str, Any]],
        retrieval_mode: str = "CURRENT",
        active_topic: str | None = None,
        active_task: str | None = None,
        allowed_categories: list[str] | None = None,
        allowed_purposes: list[str] | None = None,
        conflict_policy: str = "prefer_recent",
        weights: MemoryRecallWeights | None = None,
        max_results: int = 10,
        max_tokens: int = 600,
        now_epoch: float | None = None,
    ) -> MemoryRecallResult:
        ...
```

The engine does NOT perform raw DB queries or writes. It processes candidate memory items, computes multi-signal scores, enforces eligibility, deduplicates against canonical records, and produces structured, ranked results with full provenance.
