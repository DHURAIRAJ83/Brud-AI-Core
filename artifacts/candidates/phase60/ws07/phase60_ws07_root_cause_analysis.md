# Phase 60 WS07 — Multi-Factor Root-Cause Analysis

**Execution Phase:** Phase 60 — Capability Expansion & Generalization Improvement  
**Workstream:** WS07 — Capability Remediation & Architecture/Inference Scaling  
**Stage:** Stage A — Remediation Design, Baseline Diagnosis & Experiment Formulation  
**Date:** 2026-08-31  
**Status:** ✅ **STAGE A QUALIFIED — READY FOR HUMAN AUTHORIZATION CHECKPOINT**  
**Stage B Training Authorization:** 🔒 **STRICTLY BLOCKED (PENDING HUMAN APPROVAL)**  

---

## 1. Empirical Decoding Ablation Findings
A controlled ablation was performed on the frozen WS05 checkpoint across diagnostic probes:
- **Greedy Argmax Baseline:** Mean Repetition = **0.7500**
- **Controlled Sampling (E0: Rep Penalty = 1.25, Top-k = 20, Temp = 0.7):** Mean Repetition = **0.0067**
- **N-gram Blocking (E1: + No-repeat 3-gram):** Mean Repetition = **0.0000**

## 2. Factor Disentanglement:
- **FM-01 Repetition:** Primarily driven by unpenalized greedy decoding. Introducing repetition penalty virtually eliminates cyclic looping without retraining.
- **FM-02 Context:** Driven by context horizon ($T=128$) saturation and dataset multi-turn sparsity.
- **FM-03 Arithmetic:** Strict parameter boundary: 528K parameters cannot learn multi-digit multiplication/addition. Must be resolved via tool-dispatch formatting.
- **FM-04 EOS Termination:** Caused by under-weighted EOS token loss supervision ($\sim 2.5\%$ of sequence loss).
