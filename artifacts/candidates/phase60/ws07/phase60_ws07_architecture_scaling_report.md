# Phase 60 WS07 — Architectural Capacity & Dimension Scaling Analysis

**Execution Phase:** Phase 60 — Capability Expansion & Generalization Improvement  
**Workstream:** WS07 — Capability Remediation & Architecture/Inference Scaling  
**Stage:** Stage A — Remediation Design, Baseline Diagnosis & Experiment Formulation  
**Date:** 2026-08-31  
**Status:** ✅ **STAGE A QUALIFIED — READY FOR HUMAN AUTHORIZATION CHECKPOINT**  
**Stage B Training Authorization:** 🔒 **STRICTLY BLOCKED (PENDING HUMAN APPROVAL)**  

---

## 1. Capacity Scaling Comparison

| Dimension | Baseline Brud-Small v2 | Candidate Brud-Medium v1 (E5) | Delta |
|---|---|---|---|
| **Vocabulary ($V$)** | 1,024 | 1,024 | Constant |
| **Model Dimension ($d_{\text{model}}$)** | 128 | 192 | +50% width |
| **Attention Heads ($h$)** | 4 ($d_{\text{head}}=32$) | 6 ($d_{\text{head}}=32$) | +50% heads |
| **Transformer Layers ($L$)** | 2 | 4 | +100% depth |
| **Feedforward ($d_{\text{ff}}$)** | 256 | 384 | +50% MLP width |
| **Total Parameters** | **528,128** | **~1,230,000 (~1.23M)** | **2.33x capacity** |
| **Predicted Peak RSS** | 479 MB | ~680 MB | Safe (< 2,048 MB) |

## 2. Resource Feasibility
Brud-Medium v1 remains 100% runnable on the dual-core Intel Pentium G2030 host with peak RSS well under the 2,048 MB hard ceiling.
