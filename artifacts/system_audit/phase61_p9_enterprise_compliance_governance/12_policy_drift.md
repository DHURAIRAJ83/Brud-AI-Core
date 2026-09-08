# 12 POLICY DRIFT EVALUATOR AUDIT

- Class: `PolicyDriftEvaluator` in `core_model/ops/policy_drift_evaluator.py`.
- Evaluation: Evaluates RBAC, tenant isolation, licensing, and secret policy drift. Unknown states fail closed to `CRITICAL_DRIFT`.
