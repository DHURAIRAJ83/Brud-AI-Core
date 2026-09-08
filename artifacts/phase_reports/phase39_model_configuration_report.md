# Phase 39 — Production Model Configuration Report

## 1. Architecture Specifications (`BrudForCausalLM`)
- **Norm**: RMSNorm (epsilon 1e-5).
- **Position Embeddings**: Rotary Positional Embeddings (RoPE).
- **Activation**: SwiGLU gated activation.
- **Attention**: Multi-Head Attention (MHA) with matching query/key/value head dimensions (`num_key_value_heads == num_attention_heads`).

---

## 2. Model Profiles & Configuration Targets
| Parameter | `tiny_preset` (Verification) | Production Scale Target |
|---|---|---|
| **Vocabulary Size** | 2,000 | 32,000 |
| **Context Length** | 512 | 1,024 |
| **Hidden Size** | 256 | 512 |
| **Intermediate Size** | 768 | 1,536 |
| **Layers** | 6 | 8 |
| **Attention Heads** | 8 | 8 |
| **KV Heads** | 8 | 8 |
| **Precision** | float32 (CPU) | bfloat16 / float32 (CPU) |
| **Optimizer** | AdamW | AdamW (weight decay 0.01) |
| **LR Scheduler** | Cosine Annealing | Cosine Annealing with Warmup |
