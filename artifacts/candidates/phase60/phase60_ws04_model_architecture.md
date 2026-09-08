# Phase 60 WS04 — Model Architecture Specification

**Execution Phase:** Phase 60 — Capability Expansion & Generalization Improvement  
**Workstream:** WS04 — Model Architecture, Hyperparameter Design & Training Preparation  
**Date:** 2026-08-31  
**Status:** ✅ **DESIGN & PREPARATION QUALIFIED — VERDICT A**  
**Training Authorization:** 🔒 **STRICTLY BLOCKED**  

---

## 1. Brud-Small v2 Structural Specification

| Hyperparameter | Value | Description |
|---|---|---|
| **Architecture Type** | Decoder-Only Causal Transformer | Standard autoregressive architecture |
| **Total Parameters** | **528,128** | Exactly 528,128 parameters (100% trainable) |
| **Trainable Parameters** | **528,128** | All weights require grad |
| **Vocabulary Size (V)** | **1,024** | Governed by Tokenizer v2 (tokenizer.model) |
| **Context Length (T)** | **128** | Maximum token sequence length |
| **Model Dimension (d_model)** | **128** | Hidden channel width |
| **Attention Heads (h)** | **4** | Multi-head self-attention (head_dim = 32) |
| **Transformer Layers (L)** | **2** | Sequential encoder layers |
| **Feedforward Dimension (d_ff)** | **256** | MLP intermediate dimension (2 * d_model) |
| **Positional Encoding** | **Fixed Sinusoidal** | Sine/Cosine formulation; 0 trainable parameters |
| **Normalization** | **LayerNorm** | Post-LN configuration (norm_first=False, eps=1e-5) |
| **Activation** | **ReLU** | Rectified Linear Unit |
| **Embedding Tying** | **Untied (False)** | Independent embedding.weight and lm_head.weight |

## 2. Complete Parameter Count & Tensor Breakdown

| Tensor Name | Shape | Parameter Count |
|---|---|---|
| `embedding.weight` | `[1024, 128]` | 131,072 |
| `encoder.layers.0.self_attn.in_proj_weight` | `[384, 128]` | 49,152 |
| `encoder.layers.0.self_attn.in_proj_bias` | `[384]` | 384 |
| `encoder.layers.0.self_attn.out_proj.weight` | `[128, 128]` | 16,384 |
| `encoder.layers.0.self_attn.out_proj.bias` | `[128]` | 128 |
| `encoder.layers.0.linear1.weight` | `[256, 128]` | 32,768 |
| `encoder.layers.0.linear1.bias` | `[256]` | 256 |
| `encoder.layers.0.linear2.weight` | `[128, 256]` | 32,768 |
| `encoder.layers.0.linear2.bias` | `[128]` | 128 |
| `encoder.layers.0.norm1.weight` | `[128]` | 128 |
| `encoder.layers.0.norm1.bias` | `[128]` | 128 |
| `encoder.layers.0.norm2.weight` | `[128]` | 128 |
| `encoder.layers.0.norm2.bias` | `[128]` | 128 |
| `encoder.layers.1.self_attn.in_proj_weight` | `[384, 128]` | 49,152 |
| `encoder.layers.1.self_attn.in_proj_bias` | `[384]` | 384 |
| `encoder.layers.1.self_attn.out_proj.weight` | `[128, 128]` | 16,384 |
| `encoder.layers.1.self_attn.out_proj.bias` | `[128]` | 128 |
| `encoder.layers.1.linear1.weight` | `[256, 128]` | 32,768 |
| `encoder.layers.1.linear1.bias` | `[256]` | 256 |
| `encoder.layers.1.linear2.weight` | `[128, 256]` | 32,768 |
| `encoder.layers.1.linear2.bias` | `[128]` | 128 |
| `encoder.layers.1.norm1.weight` | `[128]` | 128 |
| `encoder.layers.1.norm1.bias` | `[128]` | 128 |
| `encoder.layers.1.norm2.weight` | `[128]` | 128 |
| `encoder.layers.1.norm2.bias` | `[128]` | 128 |
| `lm_head.weight` | `[1024, 128]` | 131,072 |
| `lm_head.bias` | `[1024]` | 1,024 |
| **TOTAL** | **All 27 Tensors** | **528,128** |
