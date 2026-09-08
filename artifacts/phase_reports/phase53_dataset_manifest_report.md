# Phase 53 Sovereign Dataset Manifest & Partitioning Report

**Audit Date**: 2026-08-29T22:10:00+05:30  
**Manifest Path**: `artifacts/phase53_dataset_manifest_v001.json`  
**Records File**: `artifacts/phase53_dataset_records_v001.jsonl`  
**Merkle Root Hash**: `b2ddea9a770a1428900968ec0af0fbeecf57c97175a3f15559f505a58f20cc12`

---

## 1. Authoritative Token & Partition Summary

| Partition Split | Record Count | Character Count | Authoritative Tokens | Percentage Share |
|:---|:---:|:---:|:---:|:---:|
| **Training Split (`train`)** | **143** | 9,484 | **2,325** | **80.00%** |
| **Validation Split (`val`)** | **16** | 1,189 | **290** | **9.98%** |
| **Held-Out Test Split (`test`)**| **18** | 1,192 | **291** | **10.02%** |
| **TOTAL APPROVED SOVEREIGN** | **177** | **11,865** | **2,906** | **100.00%** |

* Note: The partition split achieves the exact user target: $\text{Train}=2,325$, $\text{Val}=290$, $\text{Test}=291$, with $\sum = 2,906$ tokens.

---

## 2. Governance & Provenance Gating

* **Rights Status**: `100%_verified` (Project-authored, curated educational public domain, internal permissive).
* **Licence Family**: `permissive_and_sovereign`.
* **Approval Status**: `approved`.
* **Benchmark Contamination Status**: `SCREENED_CLEAN` against all evaluation manifests.
* **PII & Secret Scan**: 0 phone numbers, 0 emails, 0 credentials, 0 prompt injection signatures.
* **Normalization**: Unicode NFC safe with Tamil combining virama preserved.
