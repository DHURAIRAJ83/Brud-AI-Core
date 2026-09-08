# PHASE 48 CORPUS REPORT

**Date:** 2026-08-29  
**Status:** VERIFIED  
**Workstream:** Workstream 12 — Corpus Ingestion & Provenance  
**Manifest Hash:** `c8b4480e9fb5e521db5f403f70231bfb673aa09d4d18b7b14fe78afe33454b2a`  

---

## 1. Corpus Sources & Approval Status

Every record used in Phase 48 pretraining was verified against the immutable Phase 47 manifest:
- Primary shards: `data/corpus_exports/*/train/*.jsonl`
- Approved SFT records: `data/document_sft_exports/*.jsonl`
- Invariant: `is_approved_for_training(rights_status, licence_family, approval_status) == True`
- Rights family: `user_owned_with_permission` / `verified`

---

## 2. Tamil-Safe Unicode Normalization

All records undergo NFKC Tamil-safe normalization:
- Combining marks and pulli are strictly preserved.
- Orphan combining marks are detected and rejected via `TamilNormalizationError`.
- No unauthorized external unverified scrapes were admitted.
