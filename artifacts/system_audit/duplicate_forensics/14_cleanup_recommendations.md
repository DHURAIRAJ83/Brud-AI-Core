# WS08 Duplicate Forensic Audit — 14: Cleanup Recommendations

**Audit Date:** 2026-09-01  
**READ-ONLY AUDIT — DO NOT IMPLEMENT**

---

## P0 — Must Handle Before E4/E5

### P0-01: BrudSmallV2Model shared module creation

**Problem:** 4 production runners each define their own local copy of `BrudSmallV2Model`. The WS05 runner uses `persistent=True` on PE buffer (default), generating a checkpoint with a `pe` key. Future E4/E5 runners loading this checkpoint with `strict=True` will fail with `RuntimeError: Unexpected key(s) in state_dict: 'pe'`.

**DO NOT implement during this audit.**

**Recommendation (for E4/E5 design):**
1. Create `core_model/architecture/brud_small_v2.py` as the single canonical model module
2. All future runners import from this module
3. Define the new E4/E5 class here as `BrudSmallV4Model` (or with updated hyperparams)
4. When loading WS05 checkpoint in E4/E5: use `strict=False` OR strip `pe` key before loading

**Priority: P0 — MUST address before E4/E5 training begins**  
**SAFE_TO_REMOVE_OLD: NO — each runner still needed for phase audit trail**

---

### P0-02: No shared training engine module

**Problem:** Each training runner is a standalone script. If E4/E5 introduces a copy-paste error in the training loop, there is no canonical module to catch inconsistency.

**Recommendation:**
1. Create `core_model/training/brud_training_engine.py` with the canonical training loop
2. Extract from `run_e3_experiments.py` (current canonical runner)
3. Future runners import from this module

**Priority: P0 — MUST address before E4/E5 training**  
**SAFE_TO_REMOVE_OLD: NO — old runners preserved for phase audit trail**

---

## P1 — Should Address Before E4/E5 Production Use

### P1-01: HardwareProbeResponse — True Duplicate

**Locations:**
- `backend/models/local_setup.py` (line 49)  
- `backend/models/mini_brain_runtime_manager.py` (line 42)

Same implementation hash — identical code. Neither is imported by the other.

**Recommendation:** Consolidate into `backend/models/shared.py`. Update imports in both files.  
**SAFE_TO_REMOVE: YES — after verification that both import sites are updated**

### P1-02: IngestProviderResultsRequest + ProviderOutput — True Duplicates

**Locations:**
- `backend/models/mini_brain_continuous_learning_center.py`
- `backend/models/mini_brain_research_center.py`

Identical implementation in both.

**Recommendation:** Consolidate into `backend/models/shared.py`.  
**SAFE_TO_REMOVE: YES — after updating both import sites**

### P1-03: RagAdminReviewRequest — True Duplicate

**Locations:**
- `backend/models/mini_brain_dataset_evolution.py`
- `backend/models/mini_brain_research_center.py`

Identical.

**Recommendation:** Consolidate into `backend/models/shared.py`.  
**SAFE_TO_REMOVE: YES — after updating import sites**

### P1-04: AdminReviewRequest — Consolidation Opportunity

**11 files** share the same implementation (`446c38f42e00f781`). These could be consolidated into `backend/models/shared.py` with a single definition, and the 3-file variant (`c59e92d40d9b2d1b`) kept in its own modules (release pipeline / learning supervisor).

**Recommendation:** Extract the 11-copy version to `backend/models/shared.py::AdminReviewRequest`. Create `backend/models/shared.py::AdminReviewRequestExtended` for the 3-file variant.  
**SAFE_TO_REMOVE: YES — after updating all 11 import sites**

---

## P2 — Technical Debt, Currently Harmless

### P2-01: FeedbackRepository in phase2.py

The legacy `FeedbackRepository` in `backend/database/repositories/phase2.py` is dead code.

**Recommendation:** Archive entire `phase2.py` to `archive/legacy_repositories/phase2.py` after E6.  
**SAFE_TO_REMOVE: YES — not imported by any active code**

### P2-02: VoiceAudioDecodeError — Identical Exception

Identical in `public_voice_runtime.py` and `mini_brain_voice_runtime.py`.

**Recommendation:** Consolidate to a shared exceptions module after E6.  
**SAFE_TO_REMOVE: YES — after updating import sites**

### P2-03: FakeUploadFile × 15 test files

All 15 test files define identical `FakeUploadFile`. Could be extracted to `tests/conftest.py`.

**Recommendation:** Add to `conftest.py` and remove from individual test files.  
**SAFE_TO_REMOVE: YES — after conftest.py update**

### P2-04: core_model/inference/ stub

The Phase 1 `InferenceEngine` stub in `core_model/inference/__init__.py` serves no production purpose.

**Recommendation:** Remove the import from `core_model/__init__.py` and archive `core_model/inference/` to `archive/` after E6.  
**SAFE_TO_REMOVE: YES — after removing the import from core_model/__init__.py**

---

## P3 — Historical / Audit-Only, Leave Untouched Until After E6

### P3-01: adapter-it-at-* (6,017 directories, 3.8GB)

Historical Phase 1-2 checkpoints. No production code loads them.

**Recommendation:** Archive to cold storage (zip) after E6.  
**SAFE_TO_REMOVE_NOW: NO — preserved for historical auditing**

### P3-02: phase59_ws*.md root-level reports (~40 files)

Engineering decision trail for Phase 59.

**Recommendation:** Move to `docs/historical/phase59/` after E6.  
**SAFE_TO_REMOVE_NOW: NO**

### P3-03: Phase-versioned class duplicates (GuardAction, GovernedRecord, OpenDomainStatus, etc.)

These represent the evolution of the codebase through phases. Each file is a snapshot of a phase.

**Recommendation:** Keep all. Archive after E6 when superseded phases are fully closed.  
**SAFE_TO_REMOVE_NOW: NO**

### P3-04: CreateSessionRequest × 12

Intentional specialization — keep all. Optional P3 cosmetic: rename to `ResearchCenterCreateSessionRequest` etc. to improve readability.

**Recommendation:** KEEP + DOCUMENT. No consolidation needed.

---

## Master Cleanup Decision Table

| ID | Class/File | Occurrences | True Dup? | Active? | Used By | Required? | Risk | Recommendation |
|---|---|---|---|---|---|---|---|---|
| P0-01 | `BrudSmallV2Model` | 4 prod + 5 test | Partial | ✅ | Runners + Tests | ✅ | PE checkpoint mismatch | Create shared module before E4/E5 |
| P0-02 | Training engine (no module) | 4 runners | N/A | ✅ | Phase runners | ✅ | Drift risk | Create shared training engine |
| P1-01 | `HardwareProbeResponse` | 2 | ✅ | ✅ | local_setup + runtime_mgr | ✅ | None | CONSOLIDATE LATER |
| P1-02 | `IngestProviderResultsRequest` + `ProviderOutput` | 2 each | ✅ | ✅ | CLC + research center | ✅ | None | CONSOLIDATE LATER |
| P1-03 | `RagAdminReviewRequest` | 2 | ✅ | ✅ | dataset_evolution + research | ✅ | None | CONSOLIDATE LATER |
| P1-04 | `AdminReviewRequest` (11-copy group) | 11 | ✅ | ✅ | All Mini Brain modules | ✅ | None | CONSOLIDATE LATER |
| P2-01 | `FeedbackRepository` (phase2.py) | 1 dead | ❌ | ❌ | Nothing | ❌ | Low | ARCHIVE AFTER VERIFICATION |
| P2-02 | `VoiceAudioDecodeError` | 2 | ✅ | ✅ | Voice runtimes | ✅ | None | CONSOLIDATE LATER |
| P2-03 | `FakeUploadFile` | 15 | ✅ | ✅ | Tests | ✅ (tests) | None | CONSOLIDATE LATER |
| P2-04 | `InferenceEngine` stub | 1 | ❌ | ❌ | Symbol only | ❌ | None | ARCHIVE AFTER E6 |
| P3-01 | adapter-it-at checkpoints | 6017 dirs | N/A | ❌ | Nothing | Historical | None | ARCHIVE AFTER E6 |
| P3-02 | phase59_ws*.md | ~40 | N/A | ❌ | Nothing | Historical | None | ARCHIVE AFTER E6 |
| P3-03 | GuardAction/GovernedRecord/OpenDomain (phase-versioned) | 2-3 each | Partial | ❌ | Historical | Audit | None | KEEP + DOCUMENT |
| P3-04 | `CreateSessionRequest` × 12 | 12 | ❌ | ✅ | Each own route | ✅ | None | KEEP (Intentional B) |
