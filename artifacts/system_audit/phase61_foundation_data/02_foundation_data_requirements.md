# Phase 61 Report — 02: Foundation Data Requirement Audit

## Pretraining Scale Scenarios for 3.16M Parameter Architecture ($L=4, d=256, h=8$)

| Scenario | Token Volume | Tokens / Parameter | Est. Steps ($B=4, T=512$) | Storage (JSONL) | CPU Training Duration (Est.) | Feasibility | Expected Capability |
|---|---|---|---|---|---|---|---|
| **Scenario A** | 10M Tokens | 3.16 tokens/param | 4,882 steps | ~38 MB | ~3.2 Hours | Feasible | Basic Grammar & Vocabulary |
| **Scenario B** | 25M Tokens | 7.91 tokens/param | 12,207 steps | ~95 MB | ~8.0 Hours | Highly Feasible | Syntactic Fluency & Basic QA |
| **Scenario C (Recommended)** | **50M Tokens** | **15.82 tokens/param** | **24,414 steps** | **~190 MB** | **~16.0 Hours** | **Optimal** | **Strong General Language Reasoning** |
| **Scenario D** | 100M Tokens | 31.64 tokens/param | 48,828 steps | ~380 MB | ~32.0 Hours | Heavy CPU Load | Saturated Micro-Model Reasoning |

### Theoretical Heuristics vs Brud-Specific Requirements
- **Chinchilla Optimal Scaling Heuristic:** $\\approx 20$ tokens per parameter ($63.2\\text{M}$ tokens for 3.16M model).
- **Brud Empirical Baseline (Scenario C):** **50M Tokens** provides $15.82$ tokens/param, balancing CPU execution limits with representation learning.
