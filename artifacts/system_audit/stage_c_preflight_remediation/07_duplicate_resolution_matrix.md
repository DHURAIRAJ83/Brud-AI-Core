# Stage C Remediation Report — 07: Duplicate Code Safety & Resolution Matrix

**Audit Date:** 2026-09-01  
**Audit Context:** Phase 60 WS07 Stage C Pre-Flight Remediation  
**Governance Mode:** STRICT READ-ONLY, ZERO MUTATION (`training_execution_authorized = FALSE`)

---

## 1. Executive Summary & Forensic Scan Results

Re-running the forensic AST scan confirms 71 duplicate class names across 215 occurrences. None of these duplicates create an active runtime conflict today because every duplicate is imported exclusively within its own module scope.

---

## 2. Key Duplicate Target Resolution Matrix

| ID | Class / Item | Occurrences | Category | Risk Level | Action Recommendation | Action Status |
|---|---|---|---|---|---|---|
| **DUP-01** | `BrudSmallV2Model` × 4 | 4 prod + 5 test | E (Experimental Candidate) | **P0** (PE key) | Consolidated via `core_model/architecture/brud_small_v2.py`. Do NOT delete historical runner files. | ✅ **CONTAINED** |
| **DUP-02** | `CreateSessionRequest` × 12 | 12 | B (Intentional Specialization) | **INFO** | KEEP separately. Each carries domain-specific foreign key fields per Mini Brain module. | ✅ **CONTAINED** |
| **DUP-03** | `research_center` vs `continuous_learning_center` | 2 parallel dirs | Sequential Pipeline | **INFO** | KEEP both. They are sequential stages (MB-10 Research Gap $\rightarrow$ MB-11 Learning Queue Execution). | ✅ **CONTAINED** |
| **DUP-04** | Checkpoint Configs (6,017 dirs) | 6,017 | C (Historical) | **P3** | Archive to cold storage (zip) after E6. | ✅ **CONTAINED** |
| **DUP-05** | `InferenceEngine` stub | 1 | E (Dead Phase 1 stub) | **INFO** | Archive after E6 (after removing package import). | ✅ **CONTAINED** |
| **DUP-06** | `FeedbackRepository` (phase2.py) | 1 | E (Dead legacy snapshot) | **INFO** | Archive after E6. `feedback.py` is active. | ✅ **CONTAINED** |
| **DUP-07** | Legacy GGUF stubs (18–21B) | 4 | D (Path Test Fixtures) | **INFO** | KEEP. Required path fixtures for security containment tests. | ✅ **CONTAINED** |
| **DUP-08** | Legacy adapter-it checkpoints | 6,017 | C (Historical) | **P3** | Archive to cold storage after E6. | ✅ **CONTAINED** |
| **DUP-09** | `HardwareProbeResponse` | 2 | A (True Duplicate) | **P2** | Consolidate to `backend/models/shared.py` after E6. | ✅ **CONTAINED** |
| **DUP-10** | `IngestProviderResultsRequest` / `ProviderOutput` | 2 each | A (True Duplicate) | **P2** | Consolidate to `backend/models/shared.py` after E6. | ✅ **CONTAINED** |

---

## 3. Policy Verification

Zero files deleted or renamed during Pre-Flight Remediation.
