# 12 DATASET OVERLAP TESTS

- Test Case: Re-ingest dataset containing 50% historical content + 50% new content.
- Execution Verdict: Global Novelty Ledger correctly detects historical overlap, flags 50% as `HISTORICAL_DUPLICATE`, excludes duplicate tokens (`TRUE_NEW_TOKENS = 0` for duplicates), and accepts only the 50% novel records.
