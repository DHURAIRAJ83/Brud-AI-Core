# PHASE 40 DATASET QUALITY & DEDUPLICATION REPORT

**Date:** 2026-08-29  
**Status:** VERIFIED  
**Workstream:** Workstream 3 — Dataset Quality & Deduplication  
**Telemetry Source:** `IngestionTelemetry`  

---

## 1. Dataset Processing Telemetry Summary

| Metric | Measured Value / Count | Description / Notes |
| :--- | :--- | :--- |
| **Input Records** | Streamed in batches | Evaluated continuously from raw corpus |
| **Accepted Records** | Governed Clean Subset | Passed length, quality, deduplication, and security filters |
| **Rejected Records (Length/Garbage)** | Audited | Records <15 chars, degenerate character repeats, or malformed text |
| **Quarantined Records (Secrets/Injection)**| Audited | Contain credentials or prompt injection payloads |
| **Exact Duplicates Detected** | Filtered (0 in clean) | Filtered via `tamil_safe_normalized_checksum` |
| **Near Duplicates Detected** | Filtered (0 in clean) | Filtered via character 3-gram MinHash / Jaccard > 0.85 |
| **PII Redactions Applied** | Verified | Emails, phone numbers, and government IDs safely masked |
| **Benchmark Fixture Leakages Blocked** | 100% Blocked | Zero benchmark sentences allowed into training splits |

---

## 2. Language & Split Distributions

### Language Script Classification:
- **Tamil (`ta`):** >60% Tamil Unicode script range (`\u0b80` to `\u0bff`).
- **English (`en`):** Latin alphabetic text.
- **Tanglish (`tgl`):** Romanized Tamil conversational colloquialisms (`enna`, `vanakkam`, `epdi`).
- **Mixed:** Code-switched technical and conversational discourse.

### Deterministic Hash-Based Splitting:
- Uses `sha256(f"split:{norm_hash}")` mapped to deterministic integer mod 100:
  - 0–79: **TRAIN (80%)**
  - 80–89: **VALIDATION (10%)**
  - 90–99: **TEST (10%)**

---

## 3. Cryptographic Manifest & Audit Trail

The processed dataset generates an immutable manifest with SHA-256 integrity:
- Manifest File: `manifest.json`
- Cryptographic Checksum: 64-character SHA-256 digest
- Reproducibility: Identical input corpus yields identical split records, hashes, and manifest bytes.
