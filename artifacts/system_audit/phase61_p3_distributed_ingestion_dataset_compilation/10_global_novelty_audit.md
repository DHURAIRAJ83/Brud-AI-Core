# 10 GLOBAL NOVELTY AUDIT

- Novelty Atomicity: Atomic mutex lock over `GlobalCanonicalNoveltyLedgerEngine`.
- Concurrent Ingestion: Submitting duplicate content across two workers grants `TRUE_GLOBAL_NEW` to the first worker and `HISTORICAL_DUPLICATE` (`TRUE_NEW_TOKENS = 0`) to the second.
