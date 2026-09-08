# Phase 52 Generalization & Transfer Report

**Audit Date**: 2026-08-29T20:15:00+05:30  
**Objective**: Measure knowledge transfer across Seen, Held-out, and OOD distributions

---

## 1. Distribution Split Results

* **Seen Data Score**: **0.9556** (Probes sharing vocabulary with pre-training corpus)
* **Held-out Data Score**: **0.8875** (Probes with unseen phrasing/syntax)
* **Out-of-Distribution (OOD) Score**: **0.8271** (Adversarial, counterfactual, and novel analogies)

---

## 2. Generalization Gaps

* **Seen-to-Held-out Gap**: $0.9556 - 0.8875 = 0.0681$ (6.8% gap, indicating mild memorization bias)
* **Held-out-to-OOD Gap**: $0.8875 - 0.8271 = 0.0604$ (6.0% gap, demonstrating resilient transfer)
