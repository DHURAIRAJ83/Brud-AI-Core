# 08 RIGHTS GATE

- Module: `core_model/corpus/licence_policy.py`.
- Verification Rule: Mandatory `RIGHTS_VERIFIED == TRUE` gate before training eligibility.
- Ineligible Categories: `COPYRIGHT_RESTRICTED`, `LICENSE_UNKNOWN` -> `TRAINING_INELIGIBLE`.
