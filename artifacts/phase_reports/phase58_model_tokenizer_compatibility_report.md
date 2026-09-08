# Phase 58 Model/Tokenizer Compatibility Report

**Workstream:** 10 — Model/Tokenizer Compatibility Analysis  
**Timestamp:** 2026-08-30T17:45:00Z  
**Status:** ⚠️ DIRECT CHECKPOINT COMPATIBILITY = NO (STRUCTURAL MIGRATION REQUIRED)

---

## 1. Dimensional Comparison: Phase 56 Checkpoint vs Tokenizer v2

The Phase 56 model weights (`artifacts/phase56_checkpoints/ckpt_M3_step0120.pt`) were configured for Tokenizer v1:

| Model Component | Phase 56 Checkpoint Tensor Shape | Tokenizer v2 Expected Tensor Shape | Direct Match Status |
|---|---|---|---|
| Embedding Matrix (`embedding.weight`) | `[128, 64]` | `[1024, 64]` | ❌ Incompatible (Rows: 128 vs 1024) |
| Attention Layers 0 & 1 | `[192, 64]`, `[64, 64]` | Independent of vocab | ✅ Compatible if $d=64$ preserved |
| Feed-Forward Layers 0 & 1 | `[128, 64]`, `[64, 128]` | Independent of vocab | ✅ Compatible if $d=64$ preserved |
| LayerNorms 0 & 1 | `[64]` | Independent of vocab | ✅ Compatible if $d=64$ preserved |
| LM Head Projection (`fc_out.weight`) | `[128, 64]` | `[1024, 64]` | ❌ Incompatible (Rows: 128 vs 1024) |
| LM Head Bias (`fc_out.bias`) | `[128]` | `[1024]` | ❌ Incompatible (Length: 128 vs 1024) |

---

## 2. Can the Existing Checkpoint Be Loaded Directly?

**DIRECT CHECKPOINT COMPATIBILITY = NO.**

Loading `ckpt_M3_step0120.pt` into a model initialized with Tokenizer v2 results in a PyTorch runtime error:
```
RuntimeError: Error(s) in loading state_dict for BrudModel:
  size mismatch for embedding.weight: copying a param with shape torch.Size([128, 64]) from checkpoint, the shape in current model is torch.Size([1024, 64]).
  size mismatch for fc_out.weight: copying a param with shape torch.Size([128, 64]) from checkpoint, the shape in current model is torch.Size([1024, 64]).
  size mismatch for fc_out.bias: copying a param with shape torch.Size([128]) from checkpoint, the shape in current model is torch.Size([1024]).
```

---

## 3. Why Weight Slicing or Padding Is Scientifically Inappropriate

One could theoretically pad the remaining rows with random noise. However:
1. Tokenizer v1 tokens did not share the same ID mappings as Tokenizer v2 (e.g., in v1 token 43 is `க`, in v2 token 43 is a byte piece `<0x20>`).
2. The semantic meanings of token IDs have completely changed. Copying weights across mismatched token semantics would corrupt the model with scrambled embeddings.
3. Therefore, per Rule 1 and Rule 7, **no Frankenstein checkpoint slicing will be performed**.

**Verdict:** Transition to Tokenizer v2 requires initializing a fresh model architecture designed for the 1,024 vocabulary size.
