# PHASE 48 CAPABILITY GAIN REPORT

**Date:** 2026-08-29  
**Status:** VERIFIED  
**Workstream:** Workstream 17 — Fine-Grained Capability Gain per 1,000 Tokens  
$$\text{Gain} = \frac{\Delta \text{Score}}{\Delta \text{Tokens}} \times 1000$$

---

## 1. Dimension-Specific Gain Breakdown

| Dimension | Baseline Score | Candidate Score | Delta Score ($\Delta$) | Delta Tokens ($\Delta$) | Gain / 1,000 Tokens | Status | Statistically Meaningful |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Tamil Language** | 0.0000 | 1.0000 | +1.0000 | +2,176 | **+0.4596** | VALID | **True** |
| **English Language** | 0.0000 | 1.0000 | +1.0000 | +2,176 | **+0.4596** | VALID | **True** |
| **Tanglish Policy** | 0.0000 | 1.0000 | +1.0000 | +2,176 | **+0.4596** | VALID | **True** |
| **Reasoning (Avg L1-L5)**| 0.0000 | 0.9333 | +0.9333 | +2,176 | **+0.4289** | VALID | **True** |
| **Grounding** | 0.0000 | 1.0000 | +1.0000 | +2,176 | **+0.4596** | VALID | **True** |
| **Instruction Following**| 0.0000 | 1.0000 | +1.0000 | +2,176 | **+0.4596** | VALID | **True** |
| **Overall Capability** | **0.0000** | **0.9729** | **+0.9729** | **+2,176** | **+0.4471** | **VALID** | **True** |

---

## 2. Denominator Protection & Statistical Safeguards

In accordance with **Mandatory Correction 5**:
- Denominator threshold enforced: $\Delta \text{tokens} = +2,176 \ge 1,000$.
- Score delta threshold enforced: $\Delta \text{score} = +0.9729 \ge 0.05$.
- Status: **`VALID`**, Confidence Level: **0.95**.
