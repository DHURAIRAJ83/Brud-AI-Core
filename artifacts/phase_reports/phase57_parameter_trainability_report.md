# Phase 57 Parameter Trainability Report

**Workstream:** 6 — Trainable Parameter Audit  
**Timestamp:** 2026-08-30T16:48:00Z  
**Status:** ✅ ALL MODEL PARAMETERS VERIFIED TRAINABLE

---

## 1. Trainability Census

Every parameter in the model was inspected for gradient requirements and parameter registration:

| Parameter Tensor | Shape | Elements | Requires Grad | Trainable Status |
|---|---|---|---|---|
| `embedding.weight` | [128, 64] | 8,192 | True | ✅ Trainable |
| `transformer.layers.0.self_attn.in_proj_weight` | [192, 64] | 12,288 | True | ✅ Trainable |
| `transformer.layers.0.self_attn.in_proj_bias` | [192] | 192 | True | ✅ Trainable |
| `transformer.layers.0.self_attn.out_proj.weight` | [64, 64] | 4,096 | True | ✅ Trainable |
| `transformer.layers.0.self_attn.out_proj.bias` | [64] | 64 | True | ✅ Trainable |
| `transformer.layers.0.linear1.weight` | [128, 64] | 8,192 | True | ✅ Trainable |
| `transformer.layers.0.linear1.bias` | [128] | 128 | True | ✅ Trainable |
| `transformer.layers.0.linear2.weight` | [64, 128] | 8,192 | True | ✅ Trainable |
| `transformer.layers.0.linear2.bias` | [64] | 64 | True | ✅ Trainable |
| `transformer.layers.0.norm1.weight` | [64] | 64 | True | ✅ Trainable |
| `transformer.layers.0.norm1.bias` | [64] | 64 | True | ✅ Trainable |
| `transformer.layers.0.norm2.weight` | [64] | 64 | True | ✅ Trainable |
| `transformer.layers.0.norm2.bias` | [64] | 64 | True | ✅ Trainable |
| `transformer.layers.1.self_attn.in_proj_weight` | [192, 64] | 12,288 | True | ✅ Trainable |
| `transformer.layers.1.self_attn.in_proj_bias` | [192] | 192 | True | ✅ Trainable |
| `transformer.layers.1.self_attn.out_proj.weight` | [64, 64] | 4,096 | True | ✅ Trainable |
| `transformer.layers.1.self_attn.out_proj.bias` | [64] | 64 | True | ✅ Trainable |
| `transformer.layers.1.linear1.weight` | [128, 64] | 8,192 | True | ✅ Trainable |
| `transformer.layers.1.linear1.bias` | [128] | 128 | True | ✅ Trainable |
| `transformer.layers.1.linear2.weight` | [64, 128] | 8,192 | True | ✅ Trainable |
| `transformer.layers.1.linear2.bias` | [64] | 64 | True | ✅ Trainable |
| `transformer.layers.1.norm1.weight` | [64] | 64 | True | ✅ Trainable |
| `transformer.layers.1.norm1.bias` | [64] | 64 | True | ✅ Trainable |
| `transformer.layers.1.norm2.weight` | [64] | 64 | True | ✅ Trainable |
| `transformer.layers.1.norm2.bias` | [64] | 64 | True | ✅ Trainable |
| `fc_out.weight` | [128, 64] | 8,192 | True | ✅ Trainable |
| `fc_out.bias` | [128] | 128 | True | ✅ Trainable |

---

## 2. Summary Statistics

- Total Parameters: **83,456**
- Trainable Parameters: **83,456 (100.0%)**
- Frozen Parameters: **0 (0.0%)**
- Trainability Ratio: **1.0**

**Conclusion:** Zero capability gain cannot be attributed to unintentional parameter freezing. All weights participated in learning.
