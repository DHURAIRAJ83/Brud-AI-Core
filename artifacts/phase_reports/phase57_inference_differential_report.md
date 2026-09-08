# Phase 57 Baseline/Candidate Differential Inference Report

**Workstream:** 8 — Baseline/Candidate Differential Inference  
**Timestamp:** 2026-08-30T16:53:00Z  
**Status:** ✅ DIFFERENTIAL INFERENCE CONFIRMED — GENERATIVE BEHAVIOR SHIFTED FROM EOS TO UNK-REPETITION

---

## 1. Generation Comparison Across Milestones

Inference was captured on identical evaluation prompts across Arm A (M0 Baseline) and Arm B (M3 Candidate) using greedy argmax decoding capped at 25 tokens.

| Probe ID | M0 Baseline Token IDs | M0 Decoded Text | M3 Candidate Token IDs | M3 Decoded Text | Behavioral Difference |
|---|---|---|---|---|---|
| `ta_vocab_01` | `[3]` | `""` (Empty) | `[37, 1, 37, 1, 37, 1, ...]` | `" ⁇   ⁇   ⁇   ⁇   ⁇ "` | Immediate EOS → Repetitive UNK |
| `ta_grammar_02` | `[3]` | `""` (Empty) | `[37, 1, 37, 1, 37, 1, ...]` | `" ⁇   ⁇   ⁇   ⁇   ⁇ "` | Immediate EOS → Repetitive UNK |
| `ta_literature_03` | `[3]` | `""` (Empty) | `[37, 1, 37, 1, 37, 1, ...]` | `" ⁇   ⁇   ⁇   ⁇   ⁇ "` | Immediate EOS → Repetitive UNK |
| `ta_syntax_05` | `[52, 3]` | `"ண"` | `[1, 37, 1, 37, 1, ...]` | `" ⁇   ⁇   ⁇   ⁇   ⁇ "` | Random token → Repetitive UNK |
| `en_synonym_01` | `[3]` | `""` (Empty) | `[37, 1, 37, 1, 37, 1, ...]` | `" ⁇   ⁇   ⁇   ⁇   ⁇ "` | Immediate EOS → Repetitive UNK |
| `reasoning_01` | `[3]` | `""` (Empty) | `[37, 1, 37, 1, 37, 1, ...]` | `" ⁇   ⁇   ⁇   ⁇   ⁇ "` | Immediate EOS → Repetitive UNK |

---

## 2. Quantitative Shift in Inference Profiles

| Metric | M0 Baseline | M3 Candidate | Shift |
|---|---|---|---|
| Average Response Length (tokens) | 1.1 tokens | 25.0 tokens (capped) | +23.9 tokens |
| EOS Emission on First Step | 93.8% (30/32 probes) | 0.0% (0/32 probes) | −93.8% |
| Most Frequent Generated Token | Token 3 (`<eos>`) | Token 1 (`<unk>`) & Token 37 (`▁`) | Shift to distribution prior |
| N-gram Repetition Ratio | 0.00 | 0.95 | +0.95 |
| Keyword Hits | 0 / 32 | 0 / 32 | 0.0% (Unchanged) |

---

## 3. Analysis of the Shift

1. **Why M0 emitted EOS:** In the Phase 53 checkpoint (step 3154 on older tiny sequences), the model's highest probability at step 1 was token 3 (`<eos>`), terminating generation immediately.
2. **Why M3 emits UNK repetition:** In Phase 56, training on 120 steps with 29.17% `<unk>` tokens in the training corpus increased the logit weights for token 1 (`<unk>`) and token 37 (space prefix `▁`). The model learned that alternating space and `<unk>` is the highest likelihood sequence in its training corpus.
3. **Conclusion:** While the evaluation score remained 0/32 for both models, **the model weights and generative output changed substantially**. The change was an adaptation to corpus token statistics rather than semantic comprehension.
