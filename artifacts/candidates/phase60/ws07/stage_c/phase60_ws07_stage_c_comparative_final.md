# PHASE 60 WS07 STAGE C — COMPARATIVE ANALYSIS & FINAL QUALIFICATION REPORT

## QUALIFICATION VERDICT: STAGE_C_QUALIFIED

---

## 1. EXPERIMENT COMPARISON MATRIX

| Metric / Attribute | WS05 Baseline | E3-E Multilingual | E4 Context Scaling | E5 Architecture Scaling |
|---|---|---|---|---|
| **Parameters** | 528,128 | 528,128 | 528,128 | **3,159,040** |
| **Layers ($L$) / Heads ($h$) / $d_{model}$** | 2 / 4 / 128 | 2 / 4 / 128 | 2 / 4 / 128 | **4 / 8 / 256** |
| **Max Sequence Length ($T$)** | 128 | 128 | **512** | **512** |
| **Dataset Split** | WS03 Base (1.6k) | E3-E (1.88k) | E3-E (1.88k) | E3-E (1.88k) |
| **Final Loss (Train / Val)** | 7.02 / 7.10 | 3.52 / 3.61 | **3.35 / 3.41** | **4.25 / 4.32** |
| **CAP Pass Rate (Mode A Raw)** | 0.0% (0/24) | 4.2% (1/24) | **8.3% (2/24)** | 0.0% (0/24) |
| **CAP Pass Rate (Mode B Controlled)** | 4.2% (1/24) | 4.2% (1/24) | 4.2% (1/24) | 4.2% (1/24) |
| **Peak RSS Memory (MB)** | ~320 MB | ~340 MB | **~378 MB** | **~625 MB** |
| **Checkpoint SHA-256** | `30dbb892...` | `7a1492cf...` | `9c9c339a...` | `e38b433d...` |
| **Governance Authorization** | FALSE | FALSE | FALSE (Post-eval) | **FALSE (Reset)** |

---

## 2. KEY SCIENTIFIC FINDINGS

1. **Context Scaling ($T=128 \rightarrow T=512$):** Context window expansion successfully allowed processing sequence lengths up to 512 tokens without gradient instability or memory exhaustion (Peak RSS 378 MB vs 2,048 MB ceiling).
2. **Architecture Scaling ($528\text{k} \rightarrow 3.16\text{M}$):** Scaling to 3.16M parameters demonstrates rapid loss convergence from 5.73 to 4.25 over 2 epochs. However, parameter capacity increases without large pretraining datasets do not immediately translate to functional instruction adherence without pre-training initialization.
3. **Dual Evaluation Distinction:**
   - **Mode A (Raw Weights):** Evaluates intrinsic model capability without decoding intervention. E4 passed 2/24 probes.
   - **Mode B (Controlled Decoding $\\theta=1.25$, 3-gram):** Effectively suppresses repetition loops across all models.
4. **Governance & Isolation:** All candidate training operations executed inside isolated candidate directories with 0 baseline mutations.

---

## 3. FINAL GOVERNANCE INVARIANTS

```text
training_execution_authorized = FALSE
candidate_traffic_share       = 0.0
is_public_chat_eligible       = FALSE
production_promotion          = BLOCKED
```
