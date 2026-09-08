# PHASE 45 ARTIFACT INTEGRITY REPORT

**Date:** 2026-08-29  
**Status:** VERIFIED  
**Workstream:** Workstream 16 — Artifact Hash Binding & Invalidation Rules  

---

## 1. Candidate Checkpoint Cryptographic Manifest

| Artifact Component | File Path | Verification Method | Status |
| :--- | :--- | :--- | :--- |
| **Model Weights** | `model_state.pt` | SHA-256 vs `manifest.json` | **MATCH** |
| **Optimizer Moments** | `optimizer_state.pt` | SHA-256 vs `manifest.json` | **MATCH** |
| **Scheduler State** | `scheduler_state.pt` | SHA-256 vs `manifest.json` | **MATCH** |
| **RNG Tensors** | `rng_state.pt` | SHA-256 vs `manifest.json` | **MATCH** |
| **Trainer Metadata** | `trainer_state.json` | SHA-256 vs `manifest.json` | **MATCH** |
| **Configuration** | `config.json` | SHA-256 vs `manifest.json` | **MATCH** |
| **Lineage References** | `references.json` | SHA-256 vs `manifest.json` | **MATCH** |

---

## 2. Invalidation Policy Enforcement

- If any `.pt` or `.json` file within the checkpoint is modified after governance approval:
  - Checkpoint integrity check immediately fails.
  - All existing administrative approvals are invalidated.
  - Governance state resets to `REVIEW_REQUIRED`.
