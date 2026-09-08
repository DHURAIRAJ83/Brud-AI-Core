# 08 DATASET → TRAINING FLOW TRACE

- Dataset Versioning & Manifest: `DatasetAdminRepository` builds training split manifests.
- Pretraining Readiness: Evaluated by `PretrainingReadinessRepository`.
- Training Authorization Gate: `SignedTrainingGateEngine` requires cryptographic `SignedTrainingAuthorizationToken`.
- Gate Status: Currently `SignedTrainingAuthorizationToken = ABSENT`. Pretraining execution, optimizer stepping, and weight mutation are **100% FAIL-CLOSED BLOCKED**.
- UI Display: Displayed on `BaseTrainingPage.jsx` and `AdminAssistantPage.jsx` (`END_TO_END_CONNECTED`).
