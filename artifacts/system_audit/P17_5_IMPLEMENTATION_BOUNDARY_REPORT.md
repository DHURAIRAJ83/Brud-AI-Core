# Phase 17.5 Stage A: Implementation Boundaries & Stage B Plan

**Date**: 2026-09-06  
**Status**: ARCHITECTURAL SPECIFICATION & BOUNDARY MAP (Zero Production Changes)  
**Readiness Target**: Stage B Implementation Readiness

---

## 1. Scope & Ownership Boundaries

### What Phase 17.5 OWNS:
1. Pure domain conflict detection engine (`core_model/mini_brain/intelligence/conflict_detector.py`).
2. 6-category conflict taxonomy (`VALUE`, `NUMERIC`, `STATE`, `TEMPORAL`, `POLICY`, `VERSION`).
3. Conflict confidence calculation (0.0 to 100.0).
4. Dispute record data model and immutable event generation (`CONFLICT_DETECTED`, `CONFLICT_RESOLVED`).
5. Memory service integration for conflict detection upon proposal.
6. Retrieval conflict policy enforcement (`exclude_conflicting`, `prefer_user_confirmed`, `prefer_recent`).
7. Supervised human arbitration endpoints (`resolve_dispute`, `dismiss_dispute`).

### What Phase 17.5 DOES NOT OWN (Deferred to Future Phases):
1. **Phase 17.6 (Advanced Memory Governance)**: Complex multi-tenant approval hierarchies and role-based delegation.
2. **Phase 17.7 (Temporal Knowledge Management)**: Full temporal timeline graph querying and automated bi-temporal interval queries.
3. **Phase 17.8 (Long-Term Memory Optimization)**: Vector index compaction and cold-storage tiering.
4. **Autonomous Overwrites**: Fully autonomous truth declaration without human supervision remains strictly forbidden.

---

## 2. Stage B Implementation File Plan

When Stage B is approved, the following files will be created/modified:

### New Modules to Create:
1. `core_model/mini_brain/intelligence/conflict_detector.py`:
   - `ConflictType` enum
   - `DisputeRecord` dataclass
   - `ConflictDetectionResult` dataclass
   - `ConflictDetectionEngine` class
2. `tests/e2e/test_p17_5_conflict_detection.py`:
   - 21+ dedicated test cases validating all conflict categories, governance gates, retrieval policies, and security invariants.

### Files to Modify (Integration Only):
1. `core_model/mini_brain/intelligence/__init__.py`: Export `ConflictType`, `DisputeRecord`, `ConflictDetectionResult`, `ConflictDetectionEngine`.
2. `backend/services/memory_service.py`: Wire `ConflictDetectionEngine` into `propose_memory()` and implement `resolve_dispute()` / `dismiss_dispute()`.

---

## 3. Stage B Verification & Test Matrix

The Phase 17.5 test suite will validate:
1. **`test_p17_5_conf_001_value_conflict_detection`**: Contrasting string values flag `VALUE_CONFLICT`.
2. **`test_p17_5_conf_002_numeric_conflict_detection`**: Contradictory scalar quantities flag `NUMERIC_CONFLICT`.
3. **`test_p17_5_conf_003_state_polarity_conflict`**: Polarity flips (enabled vs disabled) flag `STATE_CONFLICT`.
4. **`test_p17_5_conf_004_temporal_interval_conflict`**: Incompatible schedules flag `TEMPORAL_CONFLICT`.
5. **`test_p17_5_conf_005_version_partitioning`**: Version-tagged statements handled without false alarm disputes.
6. **`test_p17_5_conf_006_related_distinct_protection`**: Related but distinct facts not misclassified as conflicts.
7. **`test_p17_5_conf_007_dispute_record_immutability`**: Dispute creation generates immutable event ledger records.
8. **`test_p17_5_conf_008_zero_autonomous_supersession`**: Unconfirmed statements cannot overwrite user-confirmed facts (G1).
9. **`test_p17_5_conf_009_scope_isolation_g5`**: Cross-participant candidates never compared.
10. **`test_p17_5_conf_010_secret_redaction_g8`**: Raw secrets scrubbed before conflict detection and logging.
11. **`test_p17_5_conf_011_retrieval_exclude_conflicting`**: Disputed memories excluded under strict retrieval policy.
12. **`test_p17_5_conf_012_retrieval_conflict_warning`**: Disputed memories annotated with conflict warnings.
13. **`test_p17_5_conf_013_admin_arbitration_supersede`**: Authorized admin supersession transitions old version to superseded.
14. **`test_p17_5_conf_014_admin_arbitration_retain`**: Authorized admin retention rejects competing candidate.
15. **`test_p17_5_conf_015_performance_and_bounds`**: Maximum 20 candidates evaluated in $< 2\text{ ms}$ on CPU.
16. **Full 213-test regression suite run**: Maintain 100% PASS across all historical tests.

---

## 4. Phase 17.5 Readiness Evaluation

| Area | Status | Notes |
| :--- | :--- | :--- |
| Architecture Design | **PASS** | Clear separation between detection and resolution. |
| Taxonomy Specification | **PASS** | 6 concrete categories with explicit guard conditions. |
| Governance & Safety | **PASS** | G1, G5, G8, G10/G11 strictly mapped and preserved. |
| Schema Impact | **PASS** | Leverages existing `memory_items`, `memory_item_events`, and `memory_item_versions` without breaking migrations. |
| Performance Feasibility | **PASS** | CPU-first, scalar calculations, zero heavy NLP dependencies. |
| **Overall Stage A Readiness** | **PASS (100% READY FOR STAGE B)** | |
