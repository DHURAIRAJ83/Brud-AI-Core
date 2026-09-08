# 09 TRAINING GATE

- Engine: `core_model/training/signed_training_gate.py`.
- Validation Criteria:
  - `training_execution_authorized = TRUE`
  - Valid HMAC-SHA256 Signed Authorization Token
  - Governance Gates PASS (`rights_gate`, `novelty_gate`, `provenance_gate`, `holdout_gate`, `token_accounting_gate`)
  - Signed Human Authorization Signature
- Current Runtime State: `training_execution_authorized = FALSE` (LOCKED).
