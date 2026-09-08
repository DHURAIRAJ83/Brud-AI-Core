# Phase 57 Architecture Capability Report

**Workstream:** 13 — Architecture Capability Audit  
**Timestamp:** 2026-08-30T17:08:00Z  
**Status:** ⚠️ SEVERE CAPACITY BOTTLENECK IDENTIFIED

---

## 1. Architectural Specifications of Brud Tiny Model

| Parameter | Current Value | Functional Impact on Capabilities |
|---|---|---|
| Layers ($N$) | 2 | Only 2 levels of transformer abstraction; limited compositional depth |
| Hidden Dimension ($d$) | 64 | Narrow representation space; vectors cannot separate many concepts |
| Attention Heads ($h$) | 1 | Single attention head; cannot attend to multiple syntactic/semantic relations in parallel |
| Head Dimension | 64 | Bounded capacity per token interaction |
| Feed-Forward Dim ($d_{ff}$) | 128 | $2 \times d$ (modern LLMs use $4 \times d$ or $8/3 \times d$ SwiGLU) |
| Context Length ($T$) | 64 tokens | Prompt of 40 tokens leaves only 24 tokens for response generation |
| Model Vocabulary ($V_{model}$) | 128 | Fixed embedding projection |
| Tokenizer Vocabulary ($V_{tok}$) | 64 | Upper 64 slots in model are unused; lower 64 has 29% UNK |
| Total Trainable Parameters | 83,456 | ~0.08M parameters (modern SLMs are 100M – 1,500M params) |

---

## 2. Theoretical Expressiveness Analysis

1. **Single Attention Head ($h = 1$):**
   In multi-head attention, different heads attend to different dependencies (e.g., Head 1 tracks grammar agreement, Head 2 tracks question intent, Head 3 extracts factual keywords). With $h = 1$, the attention mechanism must collapse all attention signals into a single scalar attention weight matrix, forcing trade-offs between syntax and semantics.
2. **Context Length Ceiling ($T = 64$):**
   Because Tamil characters require multiple tokens under the 64-token tokenizer, a prompt like `"தமிழில் 'அகராதி' என்பதன் பொருள் என்ன?"` consumes 38 tokens. When context is capped at 64, the model runs out of receptive field before completing a coherent multi-token sentence.
3. **Hidden Dimension ($d = 64$):**
   A 64-dimensional embedding vector cannot linearly separate hundreds of distinct entity relationships, logic rules, and multilingual vocabularies.

---

## 3. Architecture Verdict

While the architecture is computationally trivial and runs fast on low-end CPUs (10ms latency per probe), its **representational capacity is fundamentally too small for complex zero-shot reasoning or general language comprehension**. It can function as an n-gram character predictor, but cannot sustain the multi-task capabilities tested in the frozen 32-probe manifest.
