# Phase 52 Tier A Controlled Staged Training Run Report

**Audit Date**: 2026-08-29T20:15:00+05:30  
**Campaign Tier**: Tier A (Maximum Ceiling: 25,000 New Exposure Tokens)  
**Execution Mode**: Staged Milestone Evaluation (Fail-Closed on Memorization Guard)

---

## 1. Training Parameters & Environment

* **Micro-Transformer Architecture**: 2 layers, 4 attention heads, d_model=64, feedforward=128, vocab_size=128.
* **Batch Configuration**: Batch size = 2, Sequence length = 384 tokens (768 tokens per optimizer step).
* **Hardware Ceiling**: Intel Pentium G2030 (2 physical cores, 2 threads), torch threads = 2, training workers = 1.
* **Optimizer & Scheduler**: AdamW (lr=1e-3, weight_decay=1e-2), CrossEntropyLoss.

---

## 2. Staged Milestones Summary

| Milestone | Optimizer Step | Window Tokens | Cumulative Tokens | Effective Epochs | Loss | Guard State |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Baseline** | Step 3106 | 0 | 135,040 | 0.0 | N/A | `ALLOW` |
| **~5K Milestone** | Step 3113 | 5,376 | 140,416 | 2.6 | 4.9472 | `ALLOW` |
| **~10K Milestone** | Step 3120 | 5,376 | 145,792 | 5.1 | 4.8403 | `WARN` |
| **~15K Milestone** | Step 3126 | 4,608 | 150,400 | 7.3 | 4.7289 | `WARN` |
| **~20K Milestone** | Step 3133 | 5,376 | 155,776 | 9.9 | 4.7487 | `WARN` |
| **Step 3134 (HALT)**| Step 3134 | 768 | **156,544** | **10.2** | 4.7410 | **`PAUSE`** |

---

## 3. Campaign Halt Rationale

At step 3134 (accumulating **21,504 new exposure tokens**), `Phase52MemorizationGuard` triggered `PAUSE` because dominant record concentration reached **50.00%** (exceeding the 40.00% threshold). In strict accordance with the user's fail-closed mandate, training was halted immediately before the 25,000 ceiling.
