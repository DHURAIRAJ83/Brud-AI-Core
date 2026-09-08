# Phase 17.7 — Implementation Boundary & Stage B Plan
**Brud Mini Brain: File Boundaries, Schema Integrity & Future Implementation**

## 1. Proposed Stage B File Boundaries

### Proposed New Files (Stage B):
1. `core_model/mini_brain/intelligence/memory_lifecycle.py`
   - `MemoryLifecycleEngine`: Pure domain engine for freshness calculation, decay score penalties, reinforcement mathematics, and transition validation.
   - `FreshnessEvaluationResult`: Structured dataclass for dynamic freshness results.
2. `tests/e2e/test_p17_7_memory_lifecycle.py`
   - Complete 35-point E2E verification test suite.

### Proposed Modified Files (Stage B):
1. `core_model/mini_brain/intelligence/__init__.py`
   - Export `MemoryLifecycleEngine`, `FreshnessEvaluationResult`.
2. `backend/services/memory_service.py`
   - Add `evaluate_memory_freshness(public_id)`
   - Add `archive_memory(public_id, admin_id)`
   - Add `reactivate_memory(public_id, admin_id)`
   - Add `run_lifecycle_sweep(participant_scope_key, admin_id, batch_size=50)`

### Strictly Untouched Files:
- `backend/database/schema.py` (Zero schema modifications)
- `backend/database/migrations.py` (Zero migrations required)
- `context_intelligence.py`, `duplicate_detector.py`, `conflict_detector.py`, `memory_consolidator.py`
- All frontend and UI assets

---

## 2. Database Schema & Dependency Analysis
- **Zero Schema Migrations**: The existing `memory_items.status` column already natively supports `'active'`, `'expired'`, `'archived'`, `'consolidated'`, `'superseded'`.
- **Zero New Dependencies**: Pure Python and NumPy; no Torch, Transformers, or external daemons required.
