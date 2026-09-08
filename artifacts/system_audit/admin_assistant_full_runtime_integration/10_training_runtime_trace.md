# 10 TRAINING RUNTIME TRACE

- Training Pages: `BaseTrainingPage.jsx`, `IncrementalTrainingPage.jsx`, `TrainingPage.jsx` (`LEVEL 5 - E2E VERIFIED`).
- Pretraining Readiness & Invariants: Evaluated by `SignedTrainingGateEngine`. Currently `SignedTrainingAuthorizationToken = ABSENT`. Pretraining execution, optimizer stepping, and weight mutation are **100% FAIL-CLOSED BLOCKED**.
- Proposal Creation: Attempting to create a model training proposal returns unsupported action error (`LEVEL 5 - E2E FAIL-CLOSED`).
