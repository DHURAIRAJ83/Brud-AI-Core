# 03 TRAINING AUTHORIZATION PREFLIGHT AUDIT

- Training Authorization Mechanism: `SignedTrainingGateEngine`.
- Verification: `SignedTrainingGateEngine.verify_authorization(None)` raises `TrainingAuthorizationError`.
- State: `UNAUTHORIZED & LOCKED`.
