# Phase 52 Corpus Forensic Scale Report

**Audit Date**: 2026-08-29T19:59:00+05:30  
**Phase**: Phase 52 Workstream 2 — Sovereign Corpus Forensic Scale Analysis  
**Auditor**: Antigravity Core Agent  
**Status**: READ-ONLY FORENSIC AUDIT COMPLETE

---

## 1. Executive Summary & Objective

In accordance with Phase 52 Non-Negotiable Directives (Zero Fabrication & Unique Corpus != Training Exposure), this forensic investigation conducted an exhaustive, deterministic inventory of all raw and processed text across the repository to determine the true, authoritative boundary of approved unique sovereign data.

---

## 2. Complete Multi-Source Forensic Breakdown

| Candidate Repository Source | Raw Files Found | Raw Records | Raw Characters | Raw Tokens | Filtered Duplicates | Filtered Rejections | Approved Unique Records | Unique Characters | Unique Tokens | Provenance & Rights Status |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| **`data/document_sft_exports/`** | 316 | 316 | 29,647 | 7,411 | 313 (exact copies) | 0 | **3** | 974 | **243** | Verified (User-owned) |
| **`data/corpus_exports/`** | 4 dirs | 18 | 2,168 | 542 | 6 (exact dups) | 1 (sub-min length) | **11** | 1,135 | **281** | Verified (Public Domain) |
| **`data/imports/processed/`** | 2 | 29 | 5,810 | 1,452 | 2 (exact dups) | 1 (malformed JSON) | **26** | 4,967 | **1,229** | Verified (User-owned) |
| **`data/dataset_exports/`** | 142 dirs | 142 | 34,080 | 8,520 | 139 (test fixtures)| 0 | **3** | 89 | **22** | Verified (Synthetic Test) |
| **`data/tokenizers/corpora/`** | 3 | 91 | 4,057 | 1,014 | 42 (exact dups) | 0 | **49** | 1,236 | **292** | Verified (Core Corpora) |
| **`data/documents/pending/`** | 8,115 | N/A | N/A | N/A | N/A | 8,115 (Unapproved/Draft)| **0** | 0 | **0** | **REJECTED (Unapproved)** |
| **`data/imports/pending/`** | 17 | 97 | 25,600 | 6,400 | 72 (exact dups) | 25 (Duplicate of 1a8c)| **0** | 0 | **0** | **REJECTED (Unreviewed)** |
| **Total Repository Scope** | **8,599** | **693+** | **95,762+** | **23,939+** | **572+** | **8,142+** | **92** | **8,401** | **2,067** | **100% GOVERNED** |

---

## 3. Key Forensic Discoveries

1. **Template Duplication Remains Pervasive in Raw Directories**:
   - In `data/document_sft_exports/`: 313 of 316 files are byte-identical copies of a single definition instruction.
   - In `data/dataset_exports/`: 139 of 142 `train.jsonl` files are identical copies of 3 short greeting test fixtures.
   - In `data/imports/pending/`: 16 files contain identical copy-pasted slices of `data/imports/processed/1a8c33171970478ea59dfe160475509d.jsonl`.
2. **Strict Exclusion of Unapproved Data**:
   - All 8,115 PDF files in `data/documents/pending/` lack rights/licensing metadata and contain synthetic test drafts, confidential markers, or placeholders. Under Rule 4 ("Unknown rights status: REJECT; Unknown provenance: REJECT"), 100% are excluded from pre-training.
3. **Authoritative Sovereign Unique Corpus**:
   - The total approved, deduplicated, rights-verified sovereign corpus in the repository is strictly **92 unique records**, totaling **8,401 characters** and **2,067 estimated tokens**.
   - This represents a **3.94x expansion** over the Phase 50 baseline (524 tokens), and a **1.16x expansion** over Phase 51 (1,775 tokens).
   - **Target Comparison**: The recommended target of $\ge 10,000$ tokens is **NOT MET** ($2,067 < 10,000$). In strict compliance with Non-Negotiable Directive 1 (Zero Fabrication), this shortfall is reported truthfully.

---

## 4. Deduplication & Accounting Reconciliation

* `raw_tokens`: **23,939+ tokens** (naive raw token sum across un-deduplicated candidate files).
* `deduplicated_tokens`: **2,067 tokens** (after exact SHA-256 and 5-gram Jaccard deduplication).
* `approved_tokens`: **2,067 tokens** (100% pass 10-step rights and licensing screening).
* `rejected_records`: **8,142+ records/files** (unapproved pending PDFs, duplicate templates, malformed lines).
* `duplicate_ratio`: **91.4%** across scanned text sources.
