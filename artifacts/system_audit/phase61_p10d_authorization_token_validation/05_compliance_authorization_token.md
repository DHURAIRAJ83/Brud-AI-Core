# 05 COMPLIANCE AUTHORIZATION TOKEN AUDIT

- Token Class: `SignedComplianceCertificationToken`.
- Validation: Missing token / expired token / bad signature fails closed with `ComplianceCertificationError`.
- Production Status: `BLOCKED_PENDING_HUMAN_SIGNATURE`.
