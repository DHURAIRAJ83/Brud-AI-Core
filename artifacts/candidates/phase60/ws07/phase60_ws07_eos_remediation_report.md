# Phase 60 WS07 — EOS Token Loss Supervision Remediation

**Execution Phase:** Phase 60 — Capability Expansion & Generalization Improvement  
**Workstream:** WS07 — Capability Remediation & Architecture/Inference Scaling  
**Stage:** Stage A — Remediation Design, Baseline Diagnosis & Experiment Formulation  
**Date:** 2026-08-31  
**Status:** ✅ **STAGE A QUALIFIED — READY FOR HUMAN AUTHORIZATION CHECKPOINT**  
**Stage B Training Authorization:** 🔒 **STRICTLY BLOCKED (PENDING HUMAN APPROVAL)**  

---

## 1. EOS Loss Formulation
To remediate the 25% EOS emission rate, Experiment E2 implements an auxiliary weighted loss on token ID 3:
$$\mathcal{L} = \mathcal{L}_{\text{CE}} + 1.5 \cdot \mathbb{I}(y_i = 3) \cdot \mathcal{L}_{\text{CE}}(y_i)$$
This elevates the supervisory gradient signal on the terminal token by $2.5\times$, directly training the model to terminate cleanly.
