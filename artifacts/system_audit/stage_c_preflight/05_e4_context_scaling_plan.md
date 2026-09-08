# Stage C Pre-Flight Audit — 05: E4 Context Scaling Plan

**Audit Date:** 2026-09-01  
**Audit Context:** Phase 60 WS07 Stage C Pre-Flight  
**Governance Mode:** STRICT READ-ONLY, ZERO MUTATION (`training_execution_authorized = FALSE`)

---

## 1. Executive Summary & Objective

Phase 60 WS07 Stage C E4 is designed to expand the context window of Brud-Small v2:
$$\text{Context Length } T: 128 \longrightarrow 512 \text{ tokens}$$

This 4x context expansion solves the critical **Attention Saturation** bottleneck (FM-02 / RSK-E2E-02) where multi-turn dialogues and document RAG chunks were forcibly truncated at 128 tokens.

---

## 2. Technical Architecture & Positional Encoding Strategy

### Positional Encoding (Sinusoidal PE Buffer Expansion)
The sinusoidal positional encoding buffer is expanded from `max_len=128` to `max_len=512`:

$$\text{PE}_{(pos, 2i)} = \sin\left(\frac{pos}{10000^{2i/d_{model}}}\right), \quad \text{PE}_{(pos, 2i+1)} = \cos\left(\frac{pos}{10000^{2i/d_{model}}}\right)$$

- `pe` buffer shape: `[1, 512, 128]`
- `persistent=False` registered buffer (dynamically constructed at model initialization).
- Zero trainable positional parameters added.

### Attention Masking & Sequence Management
- Dynamic Causal Mask: `nn.Transformer.generate_square_subsequent_mask(seq_len)` for lengths up to 512.
- Data Collator Max Sequence: `max_seq=512`.

---

## 3. Comparative Architectural Specifications

| Property | Current Baseline (WS05 / E3) | E4 Scaled Candidate |
|---|---|---|
| **Max Sequence Length ($T$)** | **128 tokens** | **512 tokens** |
| **Model Parameters** | 528,128 | 528,128 (Zero parameter increase) |
| **Layers ($L$)** | 2 | 2 |
| **Hidden Dim ($d_{model}$)** | 128 | 128 |
| **Heads ($h$)** | 4 | 4 |
| **FFN Dim ($d_{ff}$)** | 256 | 256 |
| **PE Buffer Shape** | `[1, 128, 128]` | `[1, 512, 128]` |
| **Tokenizer** | Tokenizer v2 (1024 BPE) | Tokenizer v2 (1024 BPE) |
| **Base Checkpoint Source** | WS05 Checkpoint (`30dbb8927c0c...`) | Re-initialized PE buffer + WS05 weights |

---

## 4. Hardware & Resource Estimates for E4 Training

Under strict host system resource constraints (2 CPU threads, 2.0 GB RAM ceiling, 0 MB swap):

- **Model Weights (fp32):** 2.11 MB
- **AdamW Optimizer States:** 4.22 MB
- **Gradients:** 2.11 MB
- **Peak Activation Memory (Batch Size B=8, T=512):** ~160 MB
- **Estimated Peak RSS:** **~380 MB** (Well below 2,048 MB RAM ceiling)
- **Estimated Epoch Runtime (2 CPU threads):** ~28 - 35 seconds per epoch (1,885 samples).

---

## 5. Expected Technical Capabilities Post-E4

1. **Multi-Turn Dialogue Context Retention:** Retains up to 6 complete conversational turns without context loss.
2. **RAG Context Embedding:** Accommodates up to 350-word retrieved Tamil/English documentation chunks alongside user queries and system prompts.
3. **Loss Masking Accuracy:** Long instructions will no longer trigger forced EOS truncation at token 128.
