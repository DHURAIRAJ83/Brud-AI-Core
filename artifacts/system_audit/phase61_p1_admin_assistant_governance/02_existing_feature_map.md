# 02 EXISTING FEATURE MAP (REUSED COMPONENTS)

- **Corpus Ingestion**: Reused `core_model/corpus/production_ingestion_pipeline.py`.
- **Exact Deduplication**: Reused `core_model/corpus/exact_deduplication.py`.
- **Near Deduplication**: Reused `core_model/corpus/near_deduplication.py`.
- **Rights Policy**: Reused `core_model/corpus/licence_policy.py` & `source_policy.py`.
- **Sovereign Pretrainer**: Extended `core_model/training/sovereign_pretrainer.py` with signed authorization gate.
