# PHASE 40 MODEL CONFIGURATION REPORT

**Date:** 2026-08-29  
**Status:** VERIFIED  
**Workstream:** Workstream 5 — Production Model Configuration  
**Component:** `BrudModelConfig` (`core_model/architecture/config.py`)  

---

## 1. Target Production Profile (`production_preset`)

```python
def production_preset(vocabulary_size: int, **overrides: object) -> BrudModelConfig:
    data = {
        "vocabulary_size": vocabulary_size,
        "context_length": 1024,
        "hidden_size": 512,
        "intermediate_size": 1536,
        "num_hidden_layers": 8,
        "num_attention_heads": 8,
        "num_key_value_heads": 8,
    }
```

| Hyperparameter | Value | Architectural Justification |
| :--- | :--- | :--- |
| **Model Architecture** | `BrudForCausalLM` | Llama-style decoder-only causal Transformer |
| **Vocabulary Size** | ~32,000 | Native support for bilingual Tamil/English subwords |
| **Context Length** | 1,024 Tokens | Balances attention context with CPU memory bounds |
| **Hidden Dimension ($d_{model}$)** | 512 | Provides balanced capacity for bilingual representation |
| **Intermediate Dimension ($d_{ff}$)** | 1,536 ($3 \times d_{model}$) | SwiGLU MLP projection dimension |
| **Number of Layers** | 8 Layers | Sufficient depth for causal representation on CPU |
| **Attention Heads** | 8 Heads | Multi-Head Attention (Head dimension = 64) |
| **KV Heads** | 8 Heads | Standard MHA layout |
| **Positional Embeddings** | RoPE ($\theta = 10,000$) | Rotary Positional Embedding (even head dimension) |
| **Normalization** | RMSNorm ($\epsilon = 10^{-6}$)| Root Mean Square Normalization |
| **Activations** | SwiGLU | Swish-Gated Linear Unit activations |
| **Precision Mode** | FP32 Fallback | Safe FP32 execution on CPU host |

---

## 2. Configuration Validation Gates

Every `BrudModelConfig` instance is validated at initialization:
1. `vocabulary_size > 0`
2. `context_length > 1`
3. `hidden_size % num_attention_heads == 0`
4. `head_dimension % 2 == 0` (Mandatory for RoPE)
5. `num_key_value_heads == num_attention_heads`
6. Special token IDs (`pad_token_id`, `bos_token_id`, `eos_token_id`, `unk_token_id`) must reside strictly within `[0, vocabulary_size - 1]`.
