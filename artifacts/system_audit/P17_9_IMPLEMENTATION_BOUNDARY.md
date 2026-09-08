# Phase 17.9: Stage B Implementation Boundary

## 1. Approved Implementation Scope

### Files to CREATE (Stage B only upon authorization)
1. `core_model/mini_brain/intelligence/memory_reasoner.py`
   - Contains pure domain classes: `MemoryReasoningEngine`, `MemoryReasoningPacket`, `EvidenceCluster`, `ProceduralStep`, `PreferenceResolution`.
2. `tests/e2e/test_p17_9_memory_reasoning.py`
   - Contains minimum 35 E2E test scenarios (`P17_9-001` through `P17_9-035`).

### Files to MODIFY
1. `core_model/mini_brain/intelligence/__init__.py`
   - Export `MemoryReasoningEngine`, `MemoryReasoningPacket`, `EvidenceCluster`, `ProceduralStep`, `PreferenceResolution`.
2. `backend/services/memory_service.py` (or optional retrieval wrapper)
   - Expose `reason_over_memories()` method consuming `retrieve()` outputs and returning `MemoryReasoningPacket`.

### Files to REMAIN UNTOUCHED
- `backend/database/schema.py`
- `backend/database/migrations.py`
- `core_model/mini_brain/intelligence/context_intelligence.py`
- `core_model/mini_brain/intelligence/duplicate_detector.py`
- `core_model/mini_brain/intelligence/conflict_detector.py`
- `core_model/mini_brain/intelligence/memory_consolidator.py`
- `core_model/mini_brain/intelligence/memory_lifecycle.py`
- `core_model/mini_brain/intelligence/memory_recall.py`
- All frontend/UI code and unrelated backend services.

---

## 2. Database Schema Decision
- **DATABASE SCHEMA CHANGES**: **0 (Zero)**
- All reasoning models operate purely in memory over query-time retrieved candidates and existing SQLite WAL metadata.
