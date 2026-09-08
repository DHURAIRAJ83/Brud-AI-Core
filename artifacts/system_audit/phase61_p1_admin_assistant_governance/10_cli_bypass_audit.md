# 10 CLI BYPASS AUDIT

- Target Entry Points Audited & Hardened:
  - `core_model/training/sovereign_pretrainer.py`
  - `core_model/training/smoke_train.py`
  - `core_model/training/continuous_pretrainer.py`
- Audit Result: `CLOSED`. Direct CLI execution without signed token aborts immediately with `TrainingAuthorizationError`. 0 optimizer steps executed, 0 weight mutations.
