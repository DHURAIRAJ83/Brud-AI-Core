# PHASE 47 CORPUS EXPANSION AND PROVENANCE REPORT

**Date:** 2026-08-29  
**Status:** VERIFIED  
**Workstream:** Workstream 3 — Sovereign Corpus Expansion & Provenance  
**Engine:** `Phase47CorpusExpander` (`core_model/corpus/phase47_corpus_expander.py`)  

---

## 1. Multi-Source Sovereign Corpus Crawl

In accordance with **Mandatory Correction 2**, discovery does not equal approved training data. Every record undergoes strict verification of provenance, rights status, and approval status before admission.

| Source Pool | Path / Shard Pattern | Scanned Records | Approved & Admitted | Rejected Records | Provenance & Rights Verification | Trainable Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`corpus_exports`** | `data/corpus_exports/*/train/*.jsonl` | 18 | 11 | 7 (duplicates / short) | `user_owned_with_permission` / verified | **APPROVED** |
| **`document_sft`** | `data/document_sft_exports/*.jsonl` | 25 | 2 | 23 (duplicate / short) | `verified` rights status | **APPROVED** |
| **Total Ingested** | **Multi-source unified** | **43** | **13** | **30** | **100% Provenance Bound** | **GATE PASSED** |

---

## 2. Mandatory Approval Gating Verification

- **Policy Rule:** `is_approved_for_training(rights_status, licence_family, approval_status)`
- **Approved Rights Set:** `{"verified", "user_owned_with_permission", "approved", "public_domain"}`
- **Approval Gate Verdict:** Only records with explicit `approval_status == "approved"` and approved rights status were passed to training and validation splits. Zero unauthorized crawls were admitted.
