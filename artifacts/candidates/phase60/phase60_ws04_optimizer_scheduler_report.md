# Phase 60 WS04 — Optimizer & Learning-Rate Scheduler Report

**Execution Phase:** Phase 60 — Capability Expansion & Generalization Improvement  
**Workstream:** WS04 — Model Architecture, Hyperparameter Design & Training Preparation  
**Date:** 2026-08-31  
**Status:** ✅ **DESIGN & PREPARATION QUALIFIED — VERDICT A**  
**Training Authorization:** 🔒 **STRICTLY BLOCKED**  

---

## 1. AdamW Parameter Group Separation
To maintain numerical stability, weight decay is applied only to 2D transformation matrices:
- **Decay Group (`weight_decay=0.01`):** `embedding.weight`, attention `in_proj_weight`, attention `out_proj.weight`, FFN `linear1.weight`, FFN `linear2.weight`, `lm_head.weight`.
- **No-Decay Group (`weight_decay=0.0`):** All bias vectors and LayerNorm scale/shift parameters.

## 2. Cosine Decay Trajectory
Following 50 warmup steps, learning rate decays according to standard half-cycle cosine trajectory down to zero.
