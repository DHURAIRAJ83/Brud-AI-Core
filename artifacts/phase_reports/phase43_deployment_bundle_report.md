# PHASE 43 DEPLOYMENT BUNDLE REPORT

**Date:** 2026-08-29  
**Status:** VERIFIED  
**Workstream:** Workstream 10 & 11 — Immutable Deployment Bundle & Shadow Mode  
**Packaging Engine:** `PromotionGovernanceManager.package_deployment_bundle()`  

---

## 1. Bundle Contents & Invariant Exclusions

The deployment bundle packages all essential runtime assets while strictly excluding sensitive data:

| Bundled Artifact | Purpose | Included |
| :--- | :--- | :--- |
| `model_state.pt` | Trained parameter weights | **YES** |
| `config.json` | Architectural hyperparameters | **YES** |
| `references.json` | Lineage and metadata references | **YES** |
| `manifest.json` | Checkpoint file checksums | **YES** |
| `phase43_release_manifest.json` | Cryptographic release manifest | **YES** |
| `rollback_metadata.json` | Reversion instructions to `0.1.0-synthetic-test` | **YES** |
| `bundle_manifest.json` | Master bundle SHA-256 manifest | **YES** |
| **Production Database (`brud_ai.db`)** | State isolation invariant | **STRICTLY EXCLUDED** |
| **Secrets / API Keys / Tokens** | Security invariant | **STRICTLY EXCLUDED** |
| **Training Scratch / Temporary Files** | Reproducibility invariant | **STRICTLY EXCLUDED** |

---

## 2. Production Shadow Mode Safeguards

- `shadow_enabled = False` (Default)
- `candidate_public_chat = False` (Candidate is barred from user-visible public chat)
- `candidate_production_traffic = 0.0%` (0% traffic)
- No user-visible response may originate from the candidate during shadow mode.
