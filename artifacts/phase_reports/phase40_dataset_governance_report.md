# PHASE 40 DATASET GOVERNANCE REPORT

**Date:** 2026-08-29  
**Status:** VERIFIED  
**Workstream:** Workstream 2 — Sovereign Dataset Ingestion  
**Engine:** `ProductionIngestionPipeline` (`core_model/corpus/production_ingestion_pipeline.py`)  

---

## 1. Governance Metadata & Provenance Tracking

| Field | Configuration / Value | Verification Status |
| :--- | :--- | :--- |
| **Dataset ID** | `brud-sovereign-production-v1` | Immutable |
| **Dataset Version** | `1.0.0` | Semantic Versioning |
| **Language Scope** | Bilingual: Tamil (ta) & English (en) + Tanglish (tgl) | Verified |
| **Provenance** | Verified sovereign corpus archives & clean public domain literature | Audited |
| **Licensing** | Sovereign Public Bilingual License v1.0 | Compatible |
| **Rights Clearance** | All inputs verified free of proprietary restrictions | Enforced |
| **Manifest Format** | Deterministic JSON with SHA-256 integrity hash | Cryptographically Verified |

---

## 2. Ingestion Pipeline Lifecycle

The ingestion pipeline executes the following deterministic stages:

$$\text{Disk Stream} \longrightarrow \text{NFC Normalization} \longrightarrow \text{Length Filter} \longrightarrow \text{Garbage / Repetition Filter} \longrightarrow \text{Benchmark Isolation} \longrightarrow \text{Security \& PII Screening} \longrightarrow \text{Exact \& Near Deduplication} \longrightarrow \text{Deterministic Split}$$

### Key Security Invariants Enforced:
1. **Streaming Processing:** Multi-gigabyte text archives are read chunk-by-chunk in bounded memory buffers without loading entire archives into host RAM.
2. **Benchmark Fixture Isolation:** Text overlapping with evaluation test suites (`ENGLISH_SENTENCES`, `TAMIL_SENTENCES`, `TANGLISH_SENTENCES`) is matched via n-gram similarity and strictly blocked from pretraining splits.
3. **Secret & Prompt Injection Quarantine:** Texts with passwords, tokens, API keys, or prompt injections are quarantined and logged with audit telemetry.
4. **PII Redaction:** Emails, phone numbers, Aadhaar, PAN, and passport numbers are redacted with typed placeholders (`<EMAIL_REDACTED>`, `<PHONE_REDACTED>`, `<PERSONAL_ID_REDACTED>`) to preserve record integrity safely.

---

## 3. Split Distribution & Zero-Leakage Policy

| Split | Ratio | Purpose | Leakage Check |
| :--- | :--- | :--- | :--- |
| **TRAIN** | 80% | Model parameter pretraining | Verified disjoint from val/test |
| **VALIDATION** | 10% | Held-out validation loss evaluation | Verified disjoint from train/test |
| **TEST** | 10% | Final offline model benchmark evaluation | Verified disjoint from train/val |

**Semantic Zero-Leakage Verification:**  
Semantic leakage is verified across three dimensions:
- Exact string duplicate matching ($Train \cap Val = \emptyset$)
- Normalized text checksum matching
- Near-duplicate character n-gram Jaccard matching (<0.85 threshold)
- Complete exclusion of all Phase 38 / Phase 39 evaluation fixtures
