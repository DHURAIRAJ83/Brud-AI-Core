# 07 IDEMPOTENCY AUDIT

- Task Keying: SHA-256 hash of `source_id:book_id:checksum`.
- Behavior: Submitting an already COMPLETED task skips processing and sets `idempotent_skip = True`.
