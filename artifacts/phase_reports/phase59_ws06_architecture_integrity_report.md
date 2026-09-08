# Phase 59 WS06 — Architecture Integrity & Parameter Report

**Workstream:** 06 — Model Initialization, Checkpoint Lineage & Weight-Integrity Audit  
**Phase:** 59 — Controlled Capability & Instruction Learning Validation  
**Date:** 2026-08-31  
**Status:** ✅ **ARCHITECTURE INTEGRITY & PARAMETER COUNT FULLY QUALIFIED**

---

## 1. Executive Summary

This report establishes the architectural integrity verification, tensor dimensionality analysis, parameter counting, and weight untying audit for the **Brud-Small v2** model specification.

Brud-Small v2 represents the first model iteration built specifically to interface with Tokenizer v2 (1,024 vocabulary) under the unified sovereign token contract.

---

## 2. Model Structural Specification

| Hyperparameter | Specification | Verification Result | Status |
|---|---|---|---|
| **Model Name** | **Brud-Small v2** | Confirmed | ✅ PASS |
| **Total Parameters** | **528,128** | Exactly 528,128 parameters | ✅ PASS |
| **Trainable Parameters** | **528,128** | 100.0% trainable (`requires_grad=True`) | ✅ PASS |
| **Vocabulary Size ($V$)** | **1,024** | Exactly 1,024 tokens | ✅ PASS |
| **Context Length ($T$)** | **128** | Exactly 128 tokens | ✅ PASS |
| **Model Dimension ($d_{\text{model}}$)** | **128** | Exactly 128 channels | ✅ PASS |
| **Attention Heads ($h$)** | **4** | Exactly 4 heads ($d_{\text{head}} = 32$) | ✅ PASS |
| **Transformer Layers ($L$)** | **2** | Exactly 2 layers | ✅ PASS |
| **Feed-Forward Dimension ($d_{\text{ff}}$)** | **256** | Exactly 256 hidden channels | ✅ PASS |
| **Parameter Tying** | **False (Independent)** | Untied embedding & LM head | ✅ PASS |

---

## 3. Comprehensive Tensor Dimensionality Table

Every individual tensor in the model state dict was audited:

| Submodule / Tensor Name | Tensor Shape | Parameter Count | Parameter Role |
|---|---|---|---|
| `embedding.weight` | `[1024, 128]` | 131,072 | Token embedding matrix |
| `encoder.layers.0.self_attn.in_proj_weight` | `[384, 128]` | 49,152 | Q, K, V combined input projection |
| `encoder.layers.0.self_attn.in_proj_bias` | `[384]` | 384 | Q, K, V bias vector |
| `encoder.layers.0.self_attn.out_proj.weight`| `[128, 128]` | 16,384 | Attention output projection |
| `encoder.layers.0.self_attn.out_proj.bias` | `[128]` | 128 | Attention output bias |
| `encoder.layers.0.linear1.weight` | `[256, 128]` | 32,768 | FFN intermediate expansion |
| `encoder.layers.0.linear1.bias` | `[256]` | 256 | FFN intermediate bias |
| `encoder.layers.0.linear2.weight` | `[128, 256]` | 32,768 | FFN contraction projection |
| `encoder.layers.0.linear2.bias` | `[128]` | 128 | FFN contraction bias |
| `encoder.layers.0.norm1.weight` | `[128]` | 128 | Self-attention LayerNorm scale |
| `encoder.layers.0.norm1.bias` | `[128]` | 128 | Self-attention LayerNorm bias |
| `encoder.layers.0.norm2.weight` | `[128]` | 128 | FFN LayerNorm scale |
| `encoder.layers.0.norm2.bias` | `[128]` | 128 | FFN LayerNorm bias |
| *(Layer 0 Subtotal)* | — | *132,224* | *Layer 0 Transformer Block* |
| `encoder.layers.1.*` (Identical structure) | — | 132,224 | Layer 1 Transformer Block |
| `lm_head.weight` | `[1024, 128]` | 131,072 | Un-tied LM head projection |
| `lm_head.bias` | `[1024]` | 1,024 | Vocabulary prior bias vector |
| **Total Model Parameters** | — | **528,128** | **Bit-exact match with specification** |

---

## 4. Parameter Tying & Independence Verification

- **Storage Independence:** `id(m.embedding.weight) != id(m.lm_head.weight)`.
- **Untied LM Head Rationale:** In low-parameter multilingual models, untied embeddings allow the input representation to focus on semantic token clustering, while the LM head projection specializes in output vocabulary selection.
- **Verification:** Both matrices exist as separate, independently updated parameter buffers in `model.parameters()`.

---

## 5. Architecture Verdict

**STATUS: PASS.** All layer dimensions, tensor shapes, parameter counts (528,128), and memory layouts match the Phase 59 specification bit-exact without discrepancy.
