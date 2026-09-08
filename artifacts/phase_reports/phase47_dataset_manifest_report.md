# PHASE 47 DATASET MANIFEST REPORT

**Date:** 2026-08-29  
**Status:** VERIFIED  
**Workstream:** Workstream 3 — Immutable Dataset Manifest  
**Manifest Path:** `phase47_dataset_manifest.json`  

---

## 1. Immutable Manifest Content

```json
{
  "dataset_id": "phase47_sovereign_expanded_v1",
  "source_id": "sovereign_multi_source_v1",
  "source_path": "data/corpus_exports;data/document_sft_exports",
  "source_hash": "208d0e515d9cf281fe9ea8d867c46f1e6b36cb7bf0076fe9eb949b29cb25cb97",
  "record_count": 13,
  "total_input_records": 43,
  "rejected_unapproved": 0,
  "estimated_token_count": 334,
  "language_distribution": {
    "ta": 10,
    "en": 3,
    "tgl": 0,
    "mixed": 0
  },
  "train_count": 12,
  "validation_count": 1,
  "test_count": 0,
  "contamination_checks": {
    "benchmark_prompts_screened": 16,
    "excluded_count": 0,
    "quarantined_injections": 0,
    "secrets_detected": 0,
    "pii_redacted_count": 0
  },
  "normalization_policy": "NFKC_TAMIL_SAFE_COMBINING_MARKS_PRESERVED",
  "tokenizer_hash": "sovereign_sp_32k",
  "manifest_hash": "c8b4480e9fb5e521db5f403f70231bfb673aa09d4d18b7b14fe78afe33454b2a"
}
```

---

## 2. Integrity & Cryptographic Binding

- **Deterministic Root Hash:** Computed across `dataset_id`, `record_count`, `estimated_token_count`, and `tokenizer_hash`.
- **Reproducibility:** Binds the pretraining runs directly to the expanded multi-source dataset lineage.
