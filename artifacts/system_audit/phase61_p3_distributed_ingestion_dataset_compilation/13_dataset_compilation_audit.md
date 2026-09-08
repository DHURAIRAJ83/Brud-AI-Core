# 13 DATASET COMPILATION AUDIT

- Compiler Class: `HighThroughputDatasetCompiler` in `core_model/corpus/dataset_compiler.py`.
- State Machine: `BUILDING -> VALIDATING -> FROZEN -> PENDING_ADMIN_REVIEW -> APPROVED_CANDIDATE`.
- Immutability: FROZEN manifests are immutable. Any content change forces a new dataset version ID.
