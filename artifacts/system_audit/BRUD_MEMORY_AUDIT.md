# BRUD AI — MEMORY SYSTEM AUDIT (WS06)
**Audit Date:** 2026-09-07

---

## OWNERSHIP ANALYSIS

| Responsibility | Owner | Other Implementations | Status |
|----------------|-------|----------------------|--------|
| Memory Storage | `ConversationMemoryRepository` | None | SINGLE OWNER |
| Memory Retrieval | `MemoryService.retrieve()` | None | SINGLE OWNER |
| Memory Reasoning | `MemoryReasoningEngine` | None | SINGLE OWNER |
| Memory Writes | `MemoryService.create_item()` | None | SINGLE OWNER |
| Memory Lifecycle | `MemoryLifecycleEngine` | None | SINGLE OWNER |
| Memory Deduplication | `DuplicateKnowledgeEngine` | None | SINGLE OWNER |
| Memory Conflict | `ConflictKnowledgeEngine` | None | SINGLE OWNER |
| Memory Consolidation | `MemoryConsolidatorEngine` | None | SINGLE OWNER |
| Memory Intelligence | `MemoryIntelligenceEngine` | None | SINGLE OWNER |
| Memory Recall | `MemoryRecallEngine` | None | SINGLE OWNER |

---

## EXECUTION GRAPH

```
MemoryService (backend/services/memory_service.py — 82 KB)
    ↓
ConversationMemoryRepository (database/repositories/conversation_memory.py — 41 KB)
    ↓
SQLite: conversation_memory_* tables
    ↑
Intelligence Layer (core_model/mini_brain/intelligence/):
    ├─ MemoryIntelligenceEngine (memory_intelligence.py)
    ├─ DuplicateKnowledgeEngine (duplicate_detector.py)
    ├─ ConflictKnowledgeEngine (conflict_detector.py)
    ├─ MemoryConsolidatorEngine (memory_consolidator.py)
    ├─ MemoryLifecycleEngine (memory_lifecycle.py)
    ├─ MemoryRecallEngine (memory_recall.py)
    └─ MemoryReasoningEngine (memory_reasoner.py)
```

---

## MEMORY TYPES

The system supports:
- **Episodic Memory** — conversation turns/sessions
- **Semantic Memory** — factual memory items (via MemoryItemCreate)
- **Procedural Memory** — via ProceduralStep in memory_reasoner
- **Preference Memory** — via PreferenceResolution in memory_reasoner
- **Long-term Memory** — consent-gated, purpose-bound items
- **Short-term Memory** — conversation session turns

---

## CONSENT & SAFETY

- Memory items require active consent to become `active`
- `category_is_allowed()` and `purpose_is_bounded()` gates
- `assess_memory_safety()` safety scan
- Memory is consent-aware: `may_become_active()` checks all gates
- **Status:** ACTIVE and fully enforced

---

## MEMORY RETRIEVAL PIPELINE

```
MemoryService.retrieve(MemoryRetrieveRequest)
    ↓
apply_access_filters() [core_model/conversation/memory_retrieval.py]
    ↓
compute_embedding() [local 64-dim embedding]
    ↓
score_vectors() [cosine similarity]
    ↓
rank_with_tie_break() + compute_combined_score() [memory_ranking.py]
    ↓
MemoryRecallEngine.recall() [memory_recall.py]
    ↓
Ranked memory items
```

---

## MEMORY EMBEDDING

- Dimensions: 64 (MEMORY_EMBEDDING_DIMENSIONS)
- Model: "memory_local_embedding" v1
- Not a full embedding model — simple local implementation
- **Status:** ACTIVE (simplified embedding, not neural)

---

## MEMORY EVALUATION SERVICE

`backend/services/memory_evaluation_service.py` (16 KB)
- Evaluates memory quality and coverage
- Status: ACTIVE

---

## DATABASE TABLES (from schema.py)

Memory tables include:
- `memory_policies` — consent policies
- `memory_consents` — per-user consents
- `memory_items` — actual memory entries
- `memory_item_versions` — version history
- `memory_item_events` — lifecycle events
- `retrieval_profiles` — retrieval configuration
- `conversation_sessions` — session management
- `conversation_turns` — turn history
- `chat_orchestration_runs` — orchestration audit
- `chat_grounded_responses` — grounded response audit

---

## DUPLICATE ANALYSIS

| Finding | Status |
|---------|--------|
| No duplicate MemoryService | CLEAN |
| No duplicate ConversationMemoryRepository | CLEAN |
| No duplicate memory reasoning engine | CLEAN |
| Memory is used by both PublicChat and AdminAssistant | EXPECTED — via different scope keys |

---

## FINDINGS

1. **COMPLETE:** Full memory system implemented (Phases 17.2–17.9)
2. **COMPLETE:** Consent and safety gates active
3. **COMPLETE:** Memory reasoning with provenance, confidence, evidence
4. **COMPLETE:** Memory recall with ranking and tie-breaking
5. **SINGLE OWNER:** All memory responsibilities have clear single owners
6. **PARTIAL:** Embedding is simplified (64-dim local), not neural
7. **NO DUPLICATES DETECTED**

---
*WS06 Complete*
