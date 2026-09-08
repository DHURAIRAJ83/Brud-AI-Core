# 06 RECOVERY AUTHORIZATION AUDIT

- Token Class: `SignedRecoveryAuthorizationToken`.
- Validation: Missing token / expired token / hash mismatch fails closed with `RecoveryAuthorizationError`.
- Production Status: `RECOVERY_UNEXECUTED`.
