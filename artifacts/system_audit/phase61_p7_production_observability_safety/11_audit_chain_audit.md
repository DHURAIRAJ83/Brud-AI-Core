# 11 CRYPTOGRAPHIC AUDIT CHAIN AUDIT

- Class: `ProductionAuditChain` in `core_model/ops/production_audit_chain.py`.
- Chaining: `event_n.previous_hash = event_(n-1).hash`. Tamper detection fails closed on modified or reordered events.
