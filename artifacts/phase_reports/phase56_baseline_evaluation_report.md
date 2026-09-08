# Phase 56 Baseline Evaluation Report

**Workstream:** 4 — Pre-Training Baseline Lock  
**Timestamp:** 2026-08-30T15:53:00Z  
**Status:** ✅ BASELINE LOCKED — 0/32 PROBES (0.0% keyword hit)

> [!IMPORTANT]
> This baseline score is frozen before any Phase 56 training begins. All post-training evaluations will be compared against these values.

---

## 1. Evaluation Configuration

| Property | Value |
|----------|-------|
| Model Checkpoint | `artifacts/checkpoints/phase53/checkpoint_step_3154.pt` |
| Evaluation Manifest | `artifacts/phase53_evaluation_manifest.json` |
| Total Probes | 32 |
| Decoding Strategy | Greedy argmax |
| Max Generation Tokens | 25 |
| Context Cap | 40 tokens (prompt truncated) |
| Scoring Method | Keyword presence (case-insensitive substring match) |
| Evaluation Environment | CPU-only, torch 2.13.0+cpu, seed=42 |

---

## 2. Overall Capability Score

| Metric | Value |
|--------|-------|
| Overall keyword-hit score | **0 / 32 = 0.0%** |
| Average latency per probe | **10.7 ms** |

---

## 3. Per-Cluster Results

| Cluster | Probes | Hits | Score |
|---------|--------|------|-------|
| Tamil Language | 5 | 0 | 0.0% |
| English Language | 4 | 0 | 0.0% |
| Tanglish Policy | 3 | 0 | 0.0% |
| Reasoning | 6 | 0 | 0.0% |
| Grounding | 4 | 0 | 0.0% |
| Adversarial | 5 | 0 | 0.0% |
| Generative | 5 | 0 | 0.0% |
| **Total** | **32** | **0** | **0.0%** |

---

## 4. Per-Probe-Type Results (Seen / Held-Out / OOD)

| Probe Type | Probes | Hits | Score |
|------------|--------|------|-------|
| seen | 3 | 0 | 0.0% |
| held_out | 11 | 0 | 0.0% |
| ood | 18 | 0 | 0.0% |

---

## 5. Language-Specific Scores

| Language | Probes | Score |
|----------|--------|-------|
| Tamil (ta) | 5 | 0.0% |
| English (en) | 4 | 0.0% |
| Tanglish (tgl) | 3 | 0.0% |
| Mixed/Bilingual | Remainder | 0.0% |

---

## 6. Capability Dimension Scores

| Dimension | Score |
|-----------|-------|
| Tamil vocabulary | 0.0% |
| Tamil morphology | 0.0% |
| Tamil literature | 0.0% |
| Tamil proverbs | 0.0% |
| Tamil syntax | 0.0% |
| English vocabulary | 0.0% |
| English grammar (passive voice) | 0.0% |
| English antonym | 0.0% |
| Instruction following | 0.0% |
| Tanglish normalization | 0.0% |
| Code-switching | 0.0% |
| Bilingual intent | 0.0% |
| Arithmetic word problem | 0.0% |
| Sequential planning | 0.0% |
| Deductive logic | 0.0% |
| Analogical reasoning | 0.0% |
| Epistemic uncertainty | 0.0% |
| Counterfactual reasoning | 0.0% |
| Context extraction | 0.0% |
| Contradiction detection | 0.0% |
| Distractor resistance | 0.0% |
| Multi-attribute extraction | 0.0% |
| Hallucination refusal | 0.0% |
| False premise correction | 0.0% |
| Prompt injection defense | 0.0% |
| Nonsense recognition | 0.0% |
| Historical factual refusal | 0.0% |
| Concise summarization | 0.0% |
| Causal explanation | 0.0% |
| Non-repetition | 0.0% |
| Tamil creative expression | 0.0% |
| Comparative analysis | 0.0% |

---

## 7. Generation Quality Metrics

| Metric | Value |
|--------|-------|
| Average tokens generated | ~25 (generation cap reached for most probes) |
| Repetition detected | High — model repeats character patterns |
| Coherent response rate | ~0% (responses are character-level noise) |
| Hallucination rate | N/A (model too limited to produce factual claims) |

---

## 8. Baseline Analysis

The baseline model (Phase 53 checkpoint, 83K parameters, vocab=64, char-level) demonstrates **0.0% capability** on all 32 evaluation probes under the keyword-hit scoring protocol.

This is expected and scientifically correct given:
- **Character-level tokenization** (vocab=64) means the model cannot encode word meanings
- **83,456 parameters** is far too small for semantic language understanding
- **Context length of 64 tokens** limits response capacity
- **Effective epoch 5.29** means the model has seen the small pre-Phase-55 corpus ~5 times

The model generates **character-sequence noise** rather than semantic responses. No meaningful words or phrases matching evaluation keywords are produced.

---

## 9. Seen / Held-Out / OOD Gap

| Metric | Baseline |
|--------|---------|
| Seen score | 0.0% |
| Held-out score | 0.0% |
| OOD score | 0.0% |
| Generalization gap | 0.0% (all zero — no baseline capability to generalize from) |

---

## 10. Repetition & Hallucination

| Metric | Baseline |
|--------|---------|
| Output repetition rate | High |
| Response consistency across repeated runs | Deterministic (greedy) |
| Hallucination indicators | Not measurable (no coherent output) |

---

## 11. Baseline Lock Declaration

> **BASELINE LOCKED at: 0/32 = 0.0% capability score**
>
> Timestamp: 2026-08-30T15:53:00Z  
> Model: Phase 53 checkpoint (step 3154, eff_epoch=5.29, loss=4.81)  
> Evaluation: 32-probe frozen manifest (Phase 53)
>
> Any post-training improvement above 0/32 = measurable gain.  
> The minimum meaningful delta is defined in Workstream 5.
