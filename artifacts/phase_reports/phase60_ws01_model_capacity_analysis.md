# Phase 60 WS01 — Model Capacity & Architecture Analysis

**Execution Phase:** Phase 60 — Capability Expansion & Generalization Improvement  
**Workstream:** WS01 — Post-Training Diagnostic & Capability Gap Baseline  
**Date:** 2026-08-31  
**Status:** ✅ **BRUD-SMALL V2 ARCHITECTURE CAPACITY ASSESSED**

---

## 1. Architectural Dimensions
- **Parameters:** Exactly 528,128 parameters ($0.53$ M).
- **Hidden Dimension ($d$):** 128 channels.
- **Attention Heads ($h$):** 4 heads (head dimension 32).
- **Layers ($L$):** 2 Transformer layers.
- **Intermediate Feedforward ($d_{\text{ff}}$):** 256 channels.
- **Context Length ($T$):** 128 tokens.
- **Vocabulary Size ($V$):** 1,024 pieces.

---

## 2. Capacity Categorization

| Capability Tier | Plausibility with Brud-Small v2 | Technical Assessment |
|---|---|---|
| **Tier A: Realistically Learnable** | Short QA, definitions, language classification, tone, basic dialogue, refusal templates | $0.53$M parameters has ample capacity for a few thousand specialized patterns |
| **Tier B: Capacity-Constrained** | Encyclopedic open-domain trivia, deep multi-paragraph reasoning | Memory capacity limits memorization of millions of independent facts |
| **Tier C: Tool-Assisted Boundary** | Multi-digit arithmetic, real-time factual data | Should emit structured tool queries rather than attempting internal computation |
| **Tier D: Future Architecture Target** | Multi-turn threads ($> 128$ tokens), code generation | Requires expanding context to 256/512 tokens and scaling to 3M–10M parameters in future phases |
