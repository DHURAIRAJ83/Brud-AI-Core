# Phase 59 WS09 — Pre-Training Baseline Model Report

**Workstream:** 09 — Final Training Authorization & Controlled Execution  
**Phase:** 59 — Controlled Capability & Instruction Learning Validation  
**Date:** 2026-08-31  
**Status:** ✅ **PRE-TRAINING BASELINE CHARACTERIZED & FINGERPRINTED**

---

## 1. Model Initialization Profile

- **Model Class:** `BrudSmallV2StandardModel` (Decoder-Only Causal Transformer)
- **Total Parameters:** Exactly 528,128 parameters (100.0% trainable)
- **Vocabulary Size ($V$):** 1,024 pieces (SentencePiece BPE Tokenizer v2)
- **Model Dimension ($d$):** 128 channels
- **Attention Heads ($h$):** 4 heads
- **Hidden Layers ($L$):** 2 layers
- **Intermediate Feedforward ($d_{\text{ff}}$):** 256 channels
- **Context Length ($T$):** 128 tokens
- **Initialization Seed:** 42
- **Pre-Training Model Fingerprint:** `513b8070ad7abd1cb4364a339d55893f33661e38066107e5bed1d7571c3845fa`

---

## 2. Pre-Training Evaluation Metrics (Step 0)

| Partition / Benchmark | Evaluated Loss / Metric | Theoretical Random Bound | Assessment |
|---|---|---|---|
| **Validation Split (40 seqs)** | **7.0738** | $\ln(1024) \approx 6.9315$ | Near-uniform entropy baseline |
| **Test Split (40 seqs)** | **7.0943** | $\ln(1024) \approx 6.9315$ | Near-uniform entropy baseline |
| **Phase 53 Benchmark (32 probes)** | **0.0000** | 0.0000 | Zero knowledge at init |
