# Stage C Remediation Report — 03: P0-02 Canonical Training Engine & Authorization Hard-Stop

**Audit Date:** 2026-09-01  
**Audit Context:** Phase 60 WS07 Stage C Pre-Flight Remediation  
**Governance Mode:** STRICT READ-ONLY, ZERO MUTATION (`training_execution_authorized = FALSE`)

---

## 1. Executive Summary & Engine Creation

We extracted and consolidated the verified training behavior from `run_e3_experiments.py` into the canonical shared module:
```text
CANONICAL_ENGINE_PATH = core_model/training/brud_training_engine.py
```

This engine provides:
- Governed training execution (`verify_authorization`)
- AdamW + Cosine learning rate scheduler with warmup
- Response-only loss masking (`-100` for prompt tokens)
- CPU thread limit (`torch.set_num_threads(2)`)
- Hardware RAM / Swap resource guards
- Atomic two-phase checkpoint writing (`.tmp` $\rightarrow$ `.pt`) with SHA-256 state dict manifests
- Non-mutating dry-run execution (`run_dry_run`)

---

## 2. Hard Governance Refusal Path Verification

The training engine enforces an immutable refusal path:
```python
def verify_authorization(self) -> None:
    if not self.training_execution_authorized:
        raise TrainingAuthorizationError(
            "HARD GOVERNANCE STOP: training_execution_authorized is FALSE. "
            "Model training, weight mutation, and optimizer stepping are BLOCKED."
        )
```

### Unit Test Verification Result (`test_training_engine_refusal_when_unauthorized`):
```text
tests/core_model/test_phase60_ws07_stage_c_remediation.py::test_training_engine_refusal_when_unauthorized PASSED
```
The refusal path raises `TrainingAuthorizationError` immediately upon invocation whenever `training_execution_authorized == False`. Default repository state remains **FALSE**.
