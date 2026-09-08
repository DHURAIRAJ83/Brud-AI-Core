# 09 CANARY GOVERNANCE AUDIT

- Class: `CanaryDeploymentEngine` in `core_model/eval/canary_deployment_governance.py`.
- Staged Traffic Progression: `0% -> 1% -> 5% -> 10% -> 25% -> 50% -> 100%`. Starts strictly at 0%.
- Anomaly Protection: Error rate spikes or safety violations trigger immediate rollback and reset traffic share to 0.0.
