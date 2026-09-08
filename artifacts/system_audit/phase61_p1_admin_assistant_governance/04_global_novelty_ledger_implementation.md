# 04 GLOBAL NOVELTY LEDGER IMPLEMENTATION

- **Repository Class**: `backend/database/repositories/global_novelty_ledger_repository.py`.
- **Decision Engine**: `core_model/corpus/global_novelty_ledger.py`.
- **Novelty Statuses**: `TRUE_GLOBAL_NEW`, `HISTORICAL_DUPLICATE`, `NORMALIZED_DUPLICATE`, `NEAR_DUPLICATE`, `SYNTHETIC_DERIVATIVE`, `TRANSLATION_DERIVATIVE`.
- **Historical Duplicate Rule**: Re-ingesting historical content produces `HISTORICAL_DUPLICATE` or `NORMALIZED_DUPLICATE` with `TRUE_NEW_TOKENS = 0`.
