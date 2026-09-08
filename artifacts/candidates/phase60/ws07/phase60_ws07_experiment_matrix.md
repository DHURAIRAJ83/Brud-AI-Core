# Phase 60 WS07 — Controlled Remediation Experiment Matrix (E0 to E6)

**Execution Phase:** Phase 60 — Capability Expansion & Generalization Improvement  
**Workstream:** WS07 — Capability Remediation & Architecture/Inference Scaling  
**Stage:** Stage A — Remediation Design, Baseline Diagnosis & Experiment Formulation  
**Date:** 2026-08-31  
**Status:** ✅ **STAGE A QUALIFIED — READY FOR HUMAN AUTHORIZATION CHECKPOINT**  
**Stage B Training Authorization:** 🔒 **STRICTLY BLOCKED (PENDING HUMAN APPROVAL)**  

---

## 1. Controlled Experiment Specifications

| Exp ID | Experiment Name | Model Architecture | Context | Training Required? | Target Objective |
|---|---|---|---|---|---|
| `E0` | Inference Repetition Penalty Baseline | Brud-Small v2 (528,128 params) | 128 | No | Reduce repetition ratio < 0.40 on frozen candidate checkpoint |
| `E1` | Inference N-gram Blocking & Contrastive Decoding | Brud-Small v2 (528,128 params) | 128 | No | Eliminate cyclical attractor loops (rep ratio < 0.25) |
| `E2` | EOS-Weighted Auxiliary Loss Supervision | Brud-Small v2 (528,128 params) | 128 | Yes | Increase EOS emission rate from 25.0% to >= 90.0% |
| `E3` | Data Remediation & Multi-Turn Expansion | Brud-Small v2 (528,128 params) | 128 | Yes | Improve functional pass rate > 25% on defined probes |
| `E4` | Context Horizon Expansion to T=256 | Brud-Small v2 (528,128 params, T=256) | 256 | Yes | Successful turn-2 entity binding in 3-turn dialogues |
| `E5` | Moderate Architectural Capacity Scaling | Brud-Medium v1 (~1.23M params) | 128 | Yes | Evaluate expressivity boundary on dual-core CPU (< 1 GB RSS) |
| `E6` | Optimal Combined Remediation Candidate | Determined by Stage B findings | 256 | Yes | Pass minimum functional qualification gates for WS08 candidate audit |


## 2. Governance Protocol
Experiments E0 and E1 are inference-only decoding remediations executing against the frozen WS05 checkpoint. Experiments E2 through E6 require training and will strictly remain **BLOCKED** until explicit Stage B human authorization is granted.
