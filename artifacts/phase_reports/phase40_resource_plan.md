# PHASE 40 RESOURCE FEASIBILITY & EXECUTION PLAN

**Date:** 2026-08-29  
**Status:** VERIFIED  
**Workstream:** Workstream 6 — CPU Resource-Aware Training  
**Component:** `SovereignPretrainer` & `assess_resource_guard`  

---

## 1. Hardware Baseline Reality Check

| Hardware Dimension | Measured Capacity | Operating Limit for Training |
| :--- | :--- | :--- |
| **Physical CPU** | Intel(R) Pentium(R) CPU G2030 @ 3.00GHz (2 Cores) | Single-process / 2 dataloader threads |
| **Instruction Sets** | SSE4.1, SSE4.2, Popcnt (No AVX/AVX2) | Plain FP32 fallback enforced |
| **Total System RAM** | 12 GB | Max 4.5 GB allocatable to pretraining |
| **Available RAM** | ~5.6 GB | Bounded micro-batches & streaming |
| **Available Disk** | ~107 GB | >50 GB checkpoint & artifact headroom |
| **Swap Space** | ~6.0 GB | Emergency overflow buffer |

---

## 2. Resource Feasibility Calculation

For a model with $N$ parameters in FP32 precision:
- Static model parameters: $N \times 4\text{ bytes}$
- Gradients: $N \times 4\text{ bytes}$
- AdamW Optimizer states (first and second moments): $N \times 8\text{ bytes}$
- Total parameter + optimizer footprint: $N \times 16\text{ bytes}$

### Safety Thresholds Enforced by `verify_resource_feasibility()`:
1. `minimum_available_memory_bytes = 100 MB`
2. `minimum_available_disk_bytes = 500 MB`
3. If host RAM drops below safety margin, Resource Guard triggers PAUSE/STOP rather than allowing an Out-Of-Memory (OOM) crash.
4. Bounded micro-batching (`batch_size = 1` or `2`) combined with gradient accumulation (`gradient_accumulation_steps = 2` to `4`) ensures execution stays well within the 5.6 GB RAM boundary.
