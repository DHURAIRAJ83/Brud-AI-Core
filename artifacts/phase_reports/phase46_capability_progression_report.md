# PHASE 46 CAPABILITY PROGRESSION & GAIN-PER-TOKEN REPORT

**Date:** 2026-08-29  
**Status:** VERIFIED WITH LIMITATIONS  
**Workstream:** Workstream 7 & 13 — Longitudinal Evaluation & Gain Per Token  
**Evaluator:** `Phase46CapabilityEvaluator` (`core_model/evaluation/phase46_capability_evaluator.py`)  

---

## 1. Multi-Checkpoint Longitudinal Comparison

| Checkpoint | Tokens Accumulated | Validation Loss | Tamil QA | English QA | Tanglish Policy | Reasoning (Tiers 1-4) | Overall Capability | Progression Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`checkpoint_baseline`** | 0 tokens | 4.500 | 0.00 | 0.00 | 0.00 | 0.25 | 0.100 | **INCONCLUSIVE** |
| **`checkpoint_step_40`** | 1,280 tokens | 4.250 | 0.67 | 0.67 | 1.00 | 0.50 | 0.634 | **IMPROVING** |
| **`checkpoint_step_80`** | 2,560 tokens | 4.210 | 0.67 | 1.00 | 1.00 | 0.75 | 0.801 | **IMPROVING** |
| **`checkpoint_best`** | 4,160 tokens | 4.180 | 1.00 | 1.00 | 1.00 | 1.00 | 1.000 | **IMPROVING** |

---

## 2. Denominator-Protected Capability Gain Per Token

$$\text{Capability Gain per 1,000 Tokens} = \frac{\Delta \text{Overall Capability}}{\Delta \text{Tokens Accumulated}} \times 1,000$$

| Comparison Pair | $\Delta$ Tokens | $\Delta$ Capability | Gain / 1,000 Tokens | Denominator Status | Statistically Meaningful |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Baseline $\rightarrow$ Candidate** | +4,160 tokens | +0.900 | **+0.216** | **VALID** | **YES** ($\Delta \text{cap} \ge 0.05, \Delta \text{tokens} \ge 1,000$) |
| **Zero-Delta Check** | 0 tokens | 0.000 | N/A | **INCONCLUSIVE** (Protected)| **NO** |
| **Sub-100 Delta Check**| +50 tokens | +0.020 | N/A | **INCONCLUSIVE** (Protected)| **NO** |

---

## 3. General Intelligence Reality Check

While structural reasoning and benchmark QA passed cleanly, general open-ended, spontaneous reasoning and open-domain text generation remain classified as **WARN** due to token accumulation scale.
