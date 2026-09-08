# PHASE 46 CORPUS INVENTORY REPORT

**Date:** 2026-08-29  
**Status:** VERIFIED  
**Workstream:** Workstream 1 — Sovereign Corpus Inventory & Provenance  
**Pipeline:** `Phase46CorpusScaler` (`core_model/corpus/phase46_corpus_scaler.py`)  

---

## 1. Available Sovereign Corpus Inventory

| Source Identifier | Path | Format | Record Count | Estimated Tokens | Language | Provenance / Rights | Training Eligibility |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`e8f5d7bc`** | `data/corpus_exports/e8f5d7bc.../shard-00000.jsonl` | JSONL | 4 records | ~120 tokens | ta, en, tgl | `user_owned_with_permission` | **ELIGIBLE** |
| **`ab474f97`** | `data/corpus_exports/ab474f97.../shard-00000.jsonl` | JSONL | 4 records | ~95 tokens | ta, en, mixed | `user_owned_with_permission` | **ELIGIBLE** |
| **`13318bdd`** | `data/corpus_exports/13318bdd.../shard-00000.jsonl` | JSONL | 5 records | ~110 tokens | ta, en | `user_owned_with_permission` | **ELIGIBLE** |
| **`c7d1889a`** | `data/corpus_exports/c7d1889a.../shard-00000.jsonl` | JSONL | 5 records | ~105 tokens | ta, en, tgl | `user_owned_with_permission` | **ELIGIBLE** |
| **`document_sft`**| `data/document_sft_exports/*.jsonl` | JSONL | 100+ files | ~25,000 tokens | en, ta | `verified` rights status | **ELIGIBLE (SFT Pool)** |

---

## 2. Ingestion & Quality Filtering Results

- **Total Shards Scanned:** 4 primary training shards
- **Total Records Ingested:** 18 raw records
- **Accepted High-Quality Records:** 11 records
- **Rejected Records:** 7 records (too short, exact duplicates, near duplicates)
- **PII Findings Redacted:** 1 record (phone/email redacted cleanly)
- **Secrets Detected:** 0
- **Quarantined Prompt Injections:** 0
- **Benchmark Contamination Excluded:** 100% excluded via 5-way screening
