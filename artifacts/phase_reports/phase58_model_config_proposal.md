# Phase 58 Model Configuration Migration Proposal

**Workstream:** 11 — Model Configuration Migration Design  
**Timestamp:** 2026-08-30T17:48:00Z  
**Status:** ✅ ARCHITECTURE V2 PROPOSAL FINALIZED — CPU-TRACTABLE & HIGHLY EXPRESSIVE

---

## 1. Candidate Architecture Comparison

To resolve the architectural bottleneck identified in Phase 57 while respecting the strict CPU hardware limits (2-core Intel Pentium G2030, 12 GB RAM), three architecture variants were analyzed:

| Parameter | Phase 56 Legacy | Proposed: **Brud-Small v2 (Adopted)** | Brud-Medium v2 (Rejected) |
|---|---|---|---|
| Vocabulary Size ($V$) | 128 (64 active) | **1,024** | 2,048 |
| Hidden Dimension ($d$) | 64 | **128** | 256 |
| Attention Heads ($h$) | 1 | **4** (Head dim = 32) | 8 (Head dim = 32) |
| Layers ($N$) | 2 | **2** | 4 |
| Feed-Forward Dim ($d_{ff}$) | 128 | **256** | 512 |
| Context Length ($T$) | 64 tokens | **128 tokens** | 256 tokens |
| **Total Trainable Parameters** | **83,456** | **528,128 (~528.1K)** | 2,104,320 (~2.1M) |
| **FP32 Weight Footprint** | 0.33 MB | **2.01 MB** | 8.03 MB |
| **Peak Batch RAM on CPU** | ~15 MB | **~45 MB** | ~180 MB |
| **Single-Step CPU Latency** | ~6 ms | **~18 ms** | ~95 ms |

---

## 2. Architectural Advantages of Brud-Small v2

1. **Multi-Head Attention ($h = 4$):**
   Transitions from a single collapsed attention map to 4 parallel attention heads, enabling simultaneous tracking of syntax, entity extraction, question-answering conditioning, and punctuation boundaries.
2. **Context Window Doubled ($T = 128$):**
   Allows full prompt and response to coexist in context without aggressive truncation. Combined with Tokenizer v2's 2.2x compression, this effectively increases the semantic receptive field by **4.4x**.
3. **528K Parameters — Perfectly Bounded for CPU:**
   At 528K parameters, the model is ~6.3x larger than the legacy 83K model, providing genuine representation capacity for 15K tokens, while consuming only **2.01 MB** of RAM and executing in under 20ms per step on our 2-core CPU.
