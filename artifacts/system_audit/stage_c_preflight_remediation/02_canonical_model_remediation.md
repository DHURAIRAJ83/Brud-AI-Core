# Stage C Remediation Report — 02: P0-01 Canonical Model Consolidation

**Audit Date:** 2026-09-01  
**Audit Context:** Phase 60 WS07 Stage C Pre-Flight Remediation  
**Governance Mode:** STRICT READ-ONLY, ZERO MUTATION (`training_execution_authorized = FALSE`)

---

## 1. Executive Summary & Module Creation

To resolve the copy-paste architectural drift across individual phase runner scripts, we created the canonical shared architecture module:
```text
CANONICAL_MODULE_PATH = core_model/architecture/brud_small_v2.py
```

This module exports:
1. `BrudSmallV2Model` (528,128 parameters; $T=128$ or $T=512$)
2. `BrudSmallScaledModel` (3,159,040 parameters; $L=4, d_{model}=256, h=8, d_{ff}=768, T=512$)

---

## 2. Architectural Verification & Invariants

| Attribute | `BrudSmallV2Model` | `BrudSmallScaledModel` (E5 Target) | Status |
|---|---|---|---|
| **Max Sequence Length ($T$)** | 128 or 512 | 512 | ✅ Programmatically configurable |
| **Layer Count ($L$)** | 2 | 4 | ✅ Verified |
| **Hidden Dimension ($d_{model}$)** | 128 | 256 | ✅ Verified |
| **Attention Heads ($h$)** | 4 | 8 | ✅ Verified |
| **FFN Dimension ($d_{ff}$)** | 256 | 768 | ✅ Verified |
| **Vocab Size ($V$)** | 1024 | 1024 | ✅ Tokenizer v2 aligned |
| **Trainable Parameters** | **528,128** | **3,159,040** | ✅ Programmatically verified |
| **Static PE Persistence** | `persistent=False` | `persistent=False` | ✅ Prevents unexpected state_dict keys |
| **Controlled Generation** | Repetition penalty $\theta=1.25$, 3-gram filter | Repetition penalty $\theta=1.25$, 3-gram filter | ✅ Integrated |

---

## 3. Historical Runner Isolation

Historical experiment runners (`run_controlled_training_ws05.py`, `run_capability_evaluation_ws06.py`, `run_ws07_stage_a_diagnostics.py`, `run_e3_experiments.py`) have **NOT been deleted or modified**. They remain intact to preserve cryptographic baseline reproducibility.
