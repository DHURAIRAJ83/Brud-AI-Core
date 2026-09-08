# PHASE 17.8 — IMPLEMENTATION BOUNDARY & CHANGE SET
# CONTROLLED STAGE B FILE INVENTORY

**Document ID**: `P17_8_IMPLEMENTATION_BOUNDARY`  
**Phase**: Phase 17.8 (Brud Mini Brain — Memory Recall & Retrieval Intelligence)  
**Status**: SPECIFICATION COMPLETE (STAGE A)  

---

## 1. Stage B Proposed Change Set

To maintain maximum safety, avoid duplication, and guarantee zero regressions, the Stage B implementation footprint is strictly bounded to the following files:

### Files to CREATE:
1. `core_model/mini_brain/intelligence/memory_recall.py`
   - **Purpose**: Pure domain intelligence engine for memory recall (`MemoryRecallEngine`, `MemoryRecallWeights`, `MemoryRecallResult`, `RetrievalMode`).
   - **Why Required**: Provides pure mathematical ranking, consolidation deduplication, context intelligence boosts, and multi-mode eligibility without direct database coupling.
   - **Dependencies**: `core_model.rag.embedding`, `core_model.mini_brain.intelligence.memory_intelligence`, `core_model.mini_brain.intelligence.memory_lifecycle`, `core_model.mini_brain.intelligence.conflict_detector`.
   - **Risk**: Minimal (new pure module, fully isolated).

2. `tests/e2e/test_p17_8_memory_recall.py`
   - **Purpose**: Comprehensive 35-test verification suite covering all Phase 17.8 scenarios.
   - **Why Required**: Mandatory test validation for Stage B certification.
   - **Risk**: None (test file only).

### Files to MODIFY (Minimal Extension Only):
3. `core_model/mini_brain/intelligence/__init__.py`
   - **Purpose**: Export `MemoryRecallEngine`, `MemoryRecallWeights`, `MemoryRecallResult`, `RetrievalMode`.
   - **Why Required**: Consistent module exposure across intelligence layer.
   - **Risk**: None.

4. `backend/services/memory_service.py`
   - **Purpose**: Upgrade `retrieve()` method to call `MemoryRecallEngine.recall_memories()`, pass context topic/task signals, and record structured results in existing database tables.
   - **Why Required**: Connects domain recall engine to live service and database transactions.
   - **Risk**: Low (preserves existing method signatures and return dictionary format).

---

## 2. Files That Must Remain UNTOUCHED

The following files must NOT be modified in Phase 17.8 Stage B:
- `backend/database/schema.py` (Zero schema modifications)
- Database migration files (Zero migrations)
- `core_model/mini_brain/intelligence/memory_lifecycle.py` (Preserved intact)
- `core_model/mini_brain/intelligence/memory_consolidator.py` (Preserved intact)
- `core_model/mini_brain/intelligence/conflict_detector.py` (Preserved intact)
- `core_model/mini_brain/intelligence/duplicate_detector.py` (Preserved intact)
- `core_model/mini_brain/intelligence/context_intelligence.py` (Preserved intact)
- `core_model/rag/embedding.py` (Preserved intact)
- `core_model/rag/vector_index.py` (Preserved intact)
- Frontend / UI source code (Preserved intact)
- All external dependencies and libraries (Zero new packages)
