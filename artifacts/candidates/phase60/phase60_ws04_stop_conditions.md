# Phase 60 WS04 — 12 Formal Stop Conditions Report

**Execution Phase:** Phase 60 — Capability Expansion & Generalization Improvement  
**Workstream:** WS04 — Model Architecture, Hyperparameter Design & Training Preparation  
**Date:** 2026-08-31  
**Status:** ✅ **DESIGN & PREPARATION QUALIFIED — VERDICT A**  
**Training Authorization:** 🔒 **STRICTLY BLOCKED**  

---

## 1. Formal Stop Conditions Matrix

| ID | Trigger Condition | Severity | Immediate Action |
|---|---|---|---|
| **SC-01** | NaN loss detected | Critical | Immediate process abort |
| **SC-02** | +/- Inf loss detected | Critical | Immediate process abort |
| **SC-03** | NaN gradients in any tensor | Critical | Immediate process abort |
| **SC-04** | Inf gradients in any tensor | Critical | Immediate process abort |
| **SC-05** | Unclipped gradient norm > 100.0 | Critical | Immediate process abort |
| **SC-06** | Validation loss > 3.0x initial loss | High | Early stop with divergence flag |
| **SC-07** | Checkpoint serialization/load failure | Critical | Immediate process abort |
| **SC-08** | Dataset or tokenizer SHA-256 mutation | Critical | Immediate process abort |
| **SC-09** | Mutation of production `brud_ai.db` | Fatal | Emergency halt & rollback |
| **SC-10** | Process RSS memory > 2,048 MB | High | Process abort (OOM prevention) |
| **SC-11** | File write outside `artifacts/candidates/phase60/` | Fatal | Emergency halt |
| **SC-12** | External network socket open | Fatal | Emergency halt |
