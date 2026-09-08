# Phase 60 WS06 — Operational Failure & Fallback Matrix

**Execution Phase:** Phase 60 — Capability Expansion & Generalization Improvement  
**Workstream:** WS06 — Independent Capability Evaluation & Candidate Qualification  
**Date:** 2026-08-31  
**Status:** ✅ **INDEPENDENT EVALUATION COMPLETED (VERDICT B — REMEDIATION REQUIRED)**  
**Production State:** ❌ **PRODUCTION PROMOTION REJECTED (PATH B)**  

---

## 1. Operational Failure & Fallback Matrix

| Failure Mode | Detection Protocol | Automatic Action | Fallback Strategy |
|---|---|---|---|
| Checkpoint Hash Mismatch | Pre-eval SHA assertion | Abort evaluation | Re-verify WS05 checkpoint |
| Generation Crash | Exception handler | Record empty output | Check tensor shapes & mask |
| Non-deterministic Sampling | Seed verification | Abort process | Re-seed PyTorch RNG |
| Memory Ceiling Exceeded | RSS monitoring | Abort inference | Reduce batch size to 1 |
