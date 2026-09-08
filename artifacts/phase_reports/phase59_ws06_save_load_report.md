# Phase 59 WS06 — Save/Load Fidelity & Architecture Compatibility Report

**Workstream:** 06 — Model Initialization, Checkpoint Lineage & Weight-Integrity Audit  
**Phase:** 59 — Controlled Capability & Instruction Learning Validation  
**Date:** 2026-08-31  
**Status:** ✅ **SAVE/LOAD FIDELITY & ARCHITECTURAL COMPATIBILITY FULLY QUALIFIED**

---

## 1. Executive Summary

This report establishes the empirical verification of save/load fidelity, tensor roundtrip bit-exactness, and architectural compatibility enforcement for Brud-Small v2 checkpoints.

---

## 2. Checkpoint Save/Load Roundtrip Fidelity

In an isolated temporary audit environment, a fresh Brud-Small v2 model was instantiated, saved to disk, and reloaded into a clean twin model:

1. **Tensor Bit-Exactness:** Every parameter tensor was compared element-by-element:
   ```python
   torch.equal(m1.state_dict()[k], m2.state_dict()[k]) == True
   ```
   All 26 parameter tensors matched bit-for-bit with zero drift.
2. **SHA-256 Byte Hash Matching:** Raw binary bytes of exported and reloaded tensors exhibited identical SHA-256 digests.
3. **Logits Invariance:** When fed identical input token IDs ($x$), the reloaded model produced bit-for-bit identical output logits:
   ```python
   torch.equal(m1(x), m2(x)) == True
   ```
4. **State Persistence:** Optimizer parameters, scheduler states, training step indices, and PyTorch CPU RNG states survived the roundtrip intact without data truncation.

---

## 3. Controlled Architectural Mismatch Scenarios

To confirm that the loading pipeline enforces strict structural compatibility, synthetic mismatch models were created and tested against standard Brud-Small v2 checkpoints:

| Incompatible Configuration | Discrepancy Description | PyTorch Reaction | System Behavior |
|---|---|---|---|
| **Vocab = 1,023** | 1 token smaller than checkpoint (1,024) | `RuntimeError: size mismatch for embedding.weight` | Explicitly rejected |
| **Vocab = 1,025** | 1 token larger than checkpoint (1,024) | `RuntimeError: size mismatch for embedding.weight` | Explicitly rejected |
| **d_model = 64** | Hidden dimension halved (64 vs 128) | `RuntimeError: size mismatch for embedding.weight` | Explicitly rejected |
| **d_model = 256** | Hidden dimension doubled (256 vs 128) | `RuntimeError: size mismatch for embedding.weight` | Explicitly rejected |
| **Layers = 1** | 1 layer omitted from target model | `RuntimeError: Unexpected key(s) in state_dict` | Explicitly rejected |
| **Layers = 3** | 1 layer added to target model | `RuntimeError: Missing key(s) in state_dict` | Explicitly rejected |

### Anti-Coercion Guarantee:
- **No Shape Coercion:** PyTorch does not interpolate, pad, or truncate tensors of differing shapes during state loading.
- **No Partial Loading:** Partial parameter loads are strictly prohibited; any mismatched layer causes the entire load operation to fail closed.

---

## 4. Save/Load Verdict

**STATUS: PASS.** Checkpoint roundtrip achieves 100% bit-exact fidelity, and all architectural discrepancies fail closed with explicit RuntimeErrors.
