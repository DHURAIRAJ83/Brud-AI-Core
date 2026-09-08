# 08 AUDIT CHAIN INTEGRITY AUDIT

- Verification: SHA-256 event chaining (`event_n.previous_hash = event_(n-1).hash`). Tamper detection fails closed on modified or reordered events.
