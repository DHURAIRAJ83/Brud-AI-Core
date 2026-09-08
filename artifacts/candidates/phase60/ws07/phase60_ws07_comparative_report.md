# Phase 60 WS07 — Comparative Benchmark: Baseline vs Remediation Targets

**Execution Phase:** Phase 60 — Capability Expansion & Generalization Improvement  
**Workstream:** WS07 — Capability Remediation & Architecture/Inference Scaling  
**Stage:** Stage A — Remediation Design, Baseline Diagnosis & Experiment Formulation  
**Date:** 2026-08-31  
**Status:** ✅ **STAGE A QUALIFIED — READY FOR HUMAN AUTHORIZATION CHECKPOINT**  
**Stage B Training Authorization:** 🔒 **STRICTLY BLOCKED (PENDING HUMAN APPROVAL)**  

---

## 1. Quantitative Benchmark Targets

| Metric | WS06 Baseline | Remediation Target | Remediation Mechanism |
|---|---|---|---|
| **Repetition Ratio** | 0.75 | **< 0.30** | Decoding controls (E0/E1) & Data deduplication (E3) |
| **EOS Emission Rate** | 25.0% | **>= 90.0%** | EOS-weighted loss (E2) |
| **Functional Hit Rate** | 4.17% | **> 25.0%** | Tool-dispatch & structured tuning (E3/E6) |
| **Multi-Turn Context** | Failed | **Pass on 2-turn** | Context expansion T=256 (E4) |
| **Peak RSS** | 479 MB | **< 1,000 MB** | Controlled batch & architecture bounds |
