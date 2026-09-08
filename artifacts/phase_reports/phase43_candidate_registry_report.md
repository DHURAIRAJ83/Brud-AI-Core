# PHASE 43 CANDIDATE REGISTRY REPORT

**Date:** 2026-08-29  
**Status:** VERIFIED  
**Workstream:** Workstream 2 — Candidate Discovery & Checkpoint Inventory  
**Engine:** `CandidateRegistry` (`core_model/release/phase43_candidate_registry.py`)  

---

## 1. Candidate Checkpoint Inventory

| Checkpoint ID | Model Version | Step | Train Loss | Val Loss | Artifact Size | Classification | Integrity Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `checkpoint_step_0` | `0.3.0-candidate` | 0 | 4.500 | 4.600 | ~1.2 MB | **BASELINE** | `INTEGRITY_VERIFIED` |
| `checkpoint_step_2` | `0.3.0-candidate` | 2 | 3.842 | 3.910 | ~1.2 MB | **INTERMEDIATE** | `INTEGRITY_VERIFIED` |
| `checkpoint_step_4` | `0.3.0-candidate` | 4 | 3.215 | 3.320 | ~1.2 MB | **LATEST** | `INTEGRITY_VERIFIED` |
| `checkpoint_best` | `0.3.0-candidate` | 4 | 3.215 | 3.320 | ~1.2 MB | **PROMOTION_CANDIDATE**| `INTEGRITY_VERIFIED` |

---

## 2. Classification Logic

- **Classification Invariant:** Candidate classification is derived strictly from **verified validation telemetry**, not file or folder names.
- **BASELINE:** Lowest step count in candidate series.
- **LATEST:** Highest step count in candidate series.
- **BEST_VALIDATION / PROMOTION_CANDIDATE:** Checkpoint attaining the lowest held-out validation loss while satisfying all cryptographic manifest checks.
- **REJECTED:** Any checkpoint failing SHA-256 verification or exhibiting configuration corruption.
