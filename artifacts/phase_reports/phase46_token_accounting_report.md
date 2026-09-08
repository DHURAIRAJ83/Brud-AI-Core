# PHASE 46 TOKEN-LEVEL ACCOUNTING REPORT

**Date:** 2026-08-29  
**Status:** VERIFIED  
**Workstream:** Workstream 3 — Token-Level vs. File-Level Accounting  
**Tracker:** `TokenAccountingRecord`  

---

## 1. Corpus vs. Training Token Accounting

| Accounting Dimension | Unit | Measured Value | Tracking Methodology |
| :--- | :--- | :--- | :--- |
| **Raw Documents Processed** | Documents | 4 corpus files | File system scanning |
| **Corpus Records Ingested** | Records | 18 records | Line-by-line JSONL streaming |
| **Accepted Corpus Records** | Records | 11 records | Passed all quality & security filters |
| **Estimated Corpus Tokens** | Tokens | 281 tokens | Character heuristic (~4 chars/token) |
| **Actual Training Tokens Consumed** | Tokens | **4,160 tokens** | Exact PyTorch tensor token sum |
| **Actual Validation Tokens Consumed**| Tokens | **320 tokens** | Held-out validation tensor token sum |
| **Discarded Tokens (Padded/Filtered)**| Tokens | 0 tokens | Zero wasted padding tokens |
| **Actual Completed Optimizer Steps** | Steps | **130 steps** | AdamW parameter update count |

---

## 2. Metric Integrity: Estimated vs. Actually Consumed

- **Estimated Corpus Tokens:** Represents static text volume (281 tokens).
- **Actually Consumed Tokens:** Represents total token volume processed during iterative optimization (4,160 tokens across multi-epoch batch passes).
