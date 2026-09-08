# 13 AUDIT CHAIN INTEGRITY AUDIT

- Event Chaining: SHA-256 sequential event chaining (`event_n.previous_hash = event_(n-1).hash`). Tamper detection fails closed on modified or reordered events.
