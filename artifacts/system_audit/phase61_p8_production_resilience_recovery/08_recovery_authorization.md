# 08 CRYPTOGRAPHIC RECOVERY AUTHORIZATION GATE AUDIT

- Class: `RecoveryAuthorizationGate` in `core_model/ops/recovery_authorization_gate.py`.
- HMAC-SHA256 Token: Requires signed `SignedRecoveryAuthorizationToken` bound to request ID, release ID, snapshot hash, and admin ID.
