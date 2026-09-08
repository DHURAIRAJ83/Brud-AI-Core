# Phase 38 — Benchmark Dataset Report

## 1. Evaluation Benchmark Datasets
- **Fixture Version**: `phase11-fixed-eval-v1`
- **Benchmark Corpus**: Hardcoded literal evaluation fixtures in [`core_model/training/fixed_eval_fixtures.py`](file:///home/dhurai/Projects/brud-ai/core_model/training/fixed_eval_fixtures.py).
  - `TAMIL_SENTENCES`: 12 Tamil human-written benchmark sentences.
  - `ENGLISH_SENTENCES`: 12 English benchmark sentences.
  - `TANGLISH_SENTENCES`: 10 Tanglish sentences for normalization tests.
  - `MIXED_SENTENCES`: 6 Code-switched sentences.
- **Provenance**: Fixed internal held-out test fixtures; zero leakage with pretraining corpora.
- **Manifest Integrity**: SHA-256 manifest computed and validated across all fixture sets.
