# Stage C Pre-Flight Audit — 13: Duplicate Code Cleanup Plan

**Audit Date:** 2026-09-01  
**Audit Context:** Phase 60 WS07 Stage C Pre-Flight  
**Governance Mode:** STRICT READ-ONLY, ZERO MUTATION (`training_execution_authorized = FALSE`)

---

## 1. Executive Summary & Policy

Following the WS08 Forensic Audit, we establish the explicit timeline for consolidating technical debt duplicate code.

```text
STRICT MANDATE: NO CODE DELETIONS, RENAMES, OR MOVES DURING PRE-FLIGHT OR STAGE C TRAINING.
REASON         : All existing files must remain bit-for-bit intact to preserve baseline SHA hashes.
```

---

## 2. Phased Consolidation Roadmap

### Phase 1: BEFORE E4 CONTEXT SCALING (Pre-Flight Verification Only)
- **Action:** Verify checkpoint loading routine explicitly filters non-persistent buffers (`pe` key) rather than relying on uninspected `strict=False`.
- **Action:** Create `core_model/architecture/brud_small_v2.py` as shared architecture module.
- **Action:** Create `core_model/training/brud_training_engine.py` as shared training loop.
- **Deletions:** **0 files deleted.**

### Phase 2: BEFORE E5 ARCHITECTURE SCALING (Canonical Module Adoption)
- **Action:** Standardize E5 runner scripts to import model architecture from `core_model/architecture/brud_small_v2.py`.
- **Action:** Consolidate P1 true duplicate schema classes (`HardwareProbeResponse`, `IngestProviderResultsRequest`, `ProviderOutput`, `RagAdminReviewRequest`) into `backend/models/shared.py`.
- **Deletions:** **0 files deleted.**

### Phase 3: AFTER E6 COMPLETION (Historical Archiving & Debt Removal)
- **Action:** Compress 6,017 `adapter-it-at-*` Phase 1–2 initialization checkpoint directories (3.8 GB) into cold storage zip archives.
- **Action:** Archive Phase 1 `core_model/inference/__init__.py` stub to `archive/legacy_inference/`.
- **Action:** Archive `backend/database/repositories/phase2.py` legacy repository snapshot.
- **Action:** Consolidate test helper `FakeUploadFile` across 15 test files into `tests/conftest.py`.
- **Deletions:** **Zero production code files deleted (archived only).**
