# Phase 51 Controlled A/B/C/D Experiment & Causal Attribution Report

**Audit Date**: 2026-08-29T19:48:00+05:30  
**Objective**: Empirically determine if expanding unique corpus scale causes generalizable capability improvements  
**Methodology**: 4-Arm Controlled Frozen Evaluation Battery

---

## 1. Experimental Arms

* **Arm A (Phase 50 Baseline Candidate)**: Checkpoint step 3060, 100,000 exposure tokens on 524 unique tokens (~190.8 passes).
* **Arm B (Phase 51 Trained Candidate)**: Checkpoint step 3106, 135,040 exposure tokens on 1,775 unique tokens (~76.1 passes).
* **Arm C (Frozen Control)**: Unmodified baseline weights evaluated identically.
* **Arm D (Independent Control)**: Independent parameter state evaluated on identical probes.

---

## 2. Comparative Matrix

| Evaluation Dimension | Arm A (Baseline) | Arm B (Phase 51) | Arm C (Frozen) | Arm D (Independent) | Delta (B - A) | Delta (B - C) |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Composite Score** | 1.0000 | 1.0000 | 1.0000 | 1.0000 | **+0.0000** | **+0.0000** |
| **Tamil Language** | 1.0000 | 1.0000 | 1.0000 | 1.0000 | **+0.0000** | **+0.0000** |
| **English Language** | 1.0000 | 1.0000 | 1.0000 | 1.0000 | **+0.0000** | **+0.0000** |
| **Tanglish Policy** | 1.0000 | 1.0000 | 1.0000 | 1.0000 | **+0.0000** | **+0.0000** |
| **Reasoning Score** | 1.0000 | 1.0000 | 1.0000 | 1.0000 | **+0.0000** | **+0.0000** |
| **Grounding Score** | 1.0000 | 1.0000 | 1.0000 | 1.0000 | **+0.0000** | **+0.0000** |
| **OOD Score** | 1.0000 | 1.0000 | 1.0000 | 1.0000 | **+0.0000** | **+0.0000** |
| **Open Generative** | 1.0000 | 1.0000 | 1.0000 | 1.0000 | **+0.0000** | **+0.0000** |

---

## 3. Scientific Causal Attribution Verdict

* **Verdict**: **`INCONCLUSIVE`**
* **Rationale**:
  The candidate capability change across all 4 experimental arms is exactly 0.0000, which is within evaluation noise thresholds. Training on 35,040 new exposure tokens across the expanded 1,775-token corpus preserved full competency and stability without regression, but did not produce an empirical breakthrough on the frozen held-out evaluation battery.
* **Gain / 1,000 Tokens**:
  Gain / 1,000 Tokens = 0.0000 (statistically_meaningful = False).
