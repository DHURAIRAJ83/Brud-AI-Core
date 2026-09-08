# Phase 56 Tokenizer & Model Compatibility Report

**Workstream:** 3 — Tokenizer & Model Compatibility Audit  
**Timestamp:** 2026-08-30T15:50:00Z  
**Status:** ✅ COMPATIBLE WITH KNOWN LIMITATIONS DOCUMENTED

---

## 1. Model Architecture

| Property | Value |
|----------|-------|
| Architecture | Legacy TransformerEncoder (2-layer PyTorch nn.TransformerEncoder) |
| Checkpoint | `artifacts/checkpoints/phase53/checkpoint_step_3154.pt` |
| Training Step | 3,154 |
| Effective Epochs (at checkpoint) | 5.2856 |
| Cumulative Tokens (at checkpoint) | 171,904 |
| Total Parameters | **83,456** |
| Embedding Dimension (d_model) | 64 |
| Attention Heads | 1 |
| FFN Dimension | 128 |
| Number of Layers | 2 |
| Context Length (training) | 64 tokens |
| Vocabulary Size (model) | 128 |
| Guard State | ALLOW |

### Architecture Layer Breakdown

| Layer | Shape | Parameters |
|-------|-------|------------|
| embedding.weight | [128, 64] | 8,192 |
| transformer.layers.0.self_attn.in_proj_weight | [192, 64] | 12,288 |
| transformer.layers.0.self_attn.in_proj_bias | [192] | 192 |
| transformer.layers.0.self_attn.out_proj.weight | [64, 64] | 4,096 |
| transformer.layers.0.self_attn.out_proj.bias | [64] | 64 |
| transformer.layers.0.linear1.weight | [128, 64] | 8,192 |
| transformer.layers.0.linear1.bias | [128] | 128 |
| transformer.layers.0.linear2.weight | [64, 128] | 8,192 |
| transformer.layers.0.linear2.bias | [64] | 64 |
| transformer.layers.0.norm1.weight/bias | [64] × 2 | 128 |
| transformer.layers.0.norm2.weight/bias | [64] × 2 | 128 |
| (Layer 1 mirrors Layer 0) | — | ~33,472 |
| fc_out.weight | [128, 64] | 8,192 |
| fc_out.bias | [128] | 128 |
| **Total** | — | **83,456** |

---

## 2. Tokenizer Properties

| Property | Value |
|----------|-------|
| Type | SentencePiece (BPE) |
| Path | `data/tokenizers/versions/tok/v1/tokenizer.model` |
| Vocabulary Size | **64** tokens |
| BOS ID | 2 |
| EOS ID | 3 |
| PAD ID | 0 |
| UNK ID | 1 |
| Model Vocabulary | 128 (model has 64 extra unused slots) |

### Vocabulary Mismatch Note

The SentencePiece tokenizer has a vocabulary of **64** tokens, while the model embedding layer has **128** slots. The upper 64 slots (IDs 64–127) are structurally unused at tokenization time but exist in the model weights. This is a known architectural characteristic of the Brud model. Token IDs must be clamped to `[0, 63]` during evaluation to prevent IndexError.

---

## 3. Tokenizer Diagnostics

### 3.1 Per-Language Tokenization Results

| Language | Sample Text | Tokens | UNK Count | Char/Token Efficiency | UNK Rate |
|----------|-------------|--------|-----------|----------------------|----------|
| Tamil | "தமிழ் மொழி மிகவும் பழமையான மொழி. அது திராவிட மொழிக் குடும்பத்தைச் சேர்ந்தது." | 64 | 0 | 1.19 | 0.0% |
| English | "Machine learning is a subset of artificial intelligence..." | 94 | 0 | 1.04 | 0.0% |
| Tanglish | "naan veetuku poren, eppadi irukeenga romba thanks nanba" | 51 | 0 | 1.08 | 0.0% |
| Bilingual | "Python is a programming language. Python ஒரு நிரலாக்க மொழி." | 51 | 0 | 1.16 | 0.0% |
| Classical Tamil | "அறனெனப் பட்டதே இல்வாழ்க்கை..." | 48 | 0 | 1.31 | 0.0% |
| STEM Bilingual | Mixed English/Tamil STEM text | 105 | 0 | 1.29 | 0.0% |
| Reasoning | "If all birds can fly and penguins are birds, do penguins fly?" | 59 | 0 | 1.03 | 0.0% |
| **Total/Avg** | — | **472** | **0** | **1.16** | **0.0%** |

### 3.2 Tamil Unicode Handling
- Tamil Unicode characters are tokenized correctly at the character and sub-character level
- No unknown tokens produced for standard Tamil Unicode blocks
- Tamil fragmentation rate: high (character-level tokenization at a 64-vocab level is expected)
- 0% UNK rate confirms all Tamil characters are within the vocabulary

### 3.3 English Handling
- English tokenized at character level (1.04 chars/token average)
- Very small vocabulary (64) results in character-level encoding rather than word/subword
- 0% UNK rate for all standard ASCII English

### 3.4 Tanglish Handling
- Romanized Tamil handled as standard ASCII characters
- No UNK tokens
- 0% UNK rate

### 3.5 BOS/EOS/PAD Behavior
- PAD token (ID=0): Functions as mask token
- BOS (ID=2): Available for generation seeding
- EOS (ID=3): Acts as stop token during generation
- Sequences capped at 64 tokens (context length)

### 3.6 Sequence Packing
- Training sequences: 64-token blocks with split-oversized policy
- At 15,162 total training tokens, train split (12,277 tokens) can form ~191 blocks of 64

---

## 4. Tokenizer Diagnostic Summary

| Metric | Value |
|--------|-------|
| Unknown-token ratio | **0.0%** |
| Average tokens per record (corpus) | ~38.3 (15,162 / 396) |
| Maximum sequence length | 64 (context limit) |
| Truncation rate | Estimated low (avg record < 64 tokens) |
| Tamil fragment ratio | High (char-level), but **lossless** |
| Bilingual fragment ratio | High (char-level), but **lossless** |
| Overall UNK count | 0 across all test samples |

---

## 5. Compatibility Assessment

| Dimension | Status | Notes |
|-----------|--------|-------|
| Tamil Unicode | ✅ COMPATIBLE | 0% UNK, full coverage |
| English | ✅ COMPATIBLE | 0% UNK, character-level |
| Tanglish | ✅ COMPATIBLE | 0% UNK |
| Bilingual records | ✅ COMPATIBLE | 0% UNK |
| STEM terminology | ✅ COMPATIBLE | Character-level fallback |
| Classical Tamil | ✅ COMPATIBLE | 0% UNK |
| Reasoning/instruction | ✅ COMPATIBLE | 0% UNK |
| BOS/EOS/PAD | ✅ CORRECT | Standard SPM behavior |
| Sequence packing | ✅ SUPPORTED | split_oversized policy |
| Vocabulary mismatch (64 vs 128) | ⚠️ KNOWN — MITIGATED | Clamp IDs to [0,63] during eval |
| Model architecture loading | ✅ VERIFIED | Checkpoint loads cleanly |

---

## 6. Trainable Parameter Count

| Component | Parameters |
|-----------|------------|
| Embedding | 8,192 |
| Transformer Layer 0 | ~33,344 |
| Transformer Layer 1 | ~33,344 |
| fc_out (LM head) | 8,320 |
| **Total trainable** | **83,456** |

All 83,456 parameters are trainable (no frozen layers).

---

## 7. Compatibility Verdict

> **✅ TOKENIZER AND MODEL ARE COMPATIBLE FOR PHASE 56 TRAINING**
>
> - 0% UNK rate across all language types
> - Model loads from Phase 53 checkpoint cleanly
> - Vocabulary mismatch (64 vs 128) is documented and mitigated
> - Architecture is appropriate for the Phase 55 corpus scale (15,162 tokens)
> - Character-level tokenization is expected behavior at vocab_size=64
>
> Proceed to Workstream 4.

---

## 8. Limitation Acknowledgements

1. **Char-level tokenization:** At vocab_size=64, all encoding is character-level. This means the model cannot learn sub-word or word-level patterns, severely limiting semantic capability. This is a known architectural constraint of the Brud tiny model.

2. **Model size (83K params):** Very small by language model standards. Meaningful semantic capability gain is possible but bounded.

3. **Context length (64 tokens):** Very short. Many evaluation probes exceed this when encoded. Prompt truncation is applied.

4. **Baseline capability = 0/32 probes:** The pre-Phase-56 baseline shows 0% keyword-hit capability on the frozen 32-probe evaluation. This is the documented baseline against which any post-training capability improvement will be measured.
