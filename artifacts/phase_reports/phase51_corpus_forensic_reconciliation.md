# Phase 51 Corpus Forensic Reconciliation Report

**Audit Date**: 2026-08-29T19:22:00+05:30  
**Subject**: Forensic Investigation & Resolution of the Phase 50 Corpus Size Discrepancy (524 tokens vs ~8,680 tokens)  
**Author**: Antigravity Core Agent  
**Status**: RECONCILIATION COMPLETE & AUTHORITATIVE

---

## 1. The Core Discrepancy Statement

In Phase 50 documentation, two distinct figures were cited for unique corpus size:
1. **Preliminary Estimate in Initial Scale Gap Analysis**:
   * Approximately **~8,680 unique corpus tokens** (across 334 raw files in `data/document_sft_exports` and `data/corpus_exports`).
2. **Authoritative Measurement in Final Manifest & Walkthrough**:
   * Exactly **524 unique tokens** across **14 unique records** (resulting in $100,000 / 524 \approx 190.8$ corpus-equivalent passes).

---

## 2. Forensic Investigation & Root Cause Decomposition

Our forensic audit using `core_model/corpus/phase51_corpus_forensics.py` independently inspected every file, character, and byte across both source directories.

### Source A: `data/document_sft_exports/`
* **Total JSONL Files**: 316 files
* **Total File Size**: 101,382 bytes
* **Total Raw Record Count**: 316 records
* **Total Raw Characters**: 29,647 characters
* **Exact Duplicate Analysis**:
  * **313 out of the 316 files were 100% byte-identical duplicates** of a single template:
    ```json
    {
      "instruction": "Explain the meaning of the term covered in this passage.",
      "context": "",
      "response": "Brud AI is a Tamil-first assistant. This paragraph explains what it is.",
      "rights_status": "verified"
    }
    ```
  * SHA-256 Hash of this template: `45952593656a1645b0e06b4f657fc2fe83e022ba466223ab411e6e4cdc812d7c`
  * Exactly 1 instance of this template was retained, while 313 exact duplicate instances were filtered by the deduplication engine.
  * Only **2 other unique records** existed in this folder:
    1. Record ID `sft_077deadc...` (129 chars, 32 tokens, SHA `2c59c5eb...`)
    2. Record ID `sft_a7d7b821...` (760 chars, 190 tokens, SHA `65ad85d5...`)
* **Unique Records Accepted from Source A**: **3 unique records** (243 tokens, 974 chars).

### Source B: `data/corpus_exports/`
* **Total Source Directories**: 4 directories (`13318bdd...`, `ab474f97...`, `c7d1889a...`, `e8f5d7bc...`)
* **Total Raw Records**: 18 records across `train/*.jsonl`
* **Total Raw Characters**: 2,168 characters
* **Deduplication Analysis**:
  * 6 records were exact duplicates or near-duplicates.
  * 1 record was dropped due to sub-minimum length.
* **Unique Records Accepted from Source B**: **11 unique records** (281 tokens, 1,135 chars).

---

## 3. Reconciliation Table

| Metric Dimension | Phase 50 Initial Estimate | Independently Recomputed Raw | Deduplicated / Authoritative | Filtering Root Cause |
|:---|:---:|:---:|:---:|:---|
| **Raw File Count** | 334 | 334 | **14 unique files** | 320 duplicate files |
| **Total Input Records** | 334 | 334 | **14 unique records** | 319 exact duplicates + 1 near duplicate |
| **Character Count** | ~34,720 chars | 31,815 raw chars | **2,109 unique chars** | 29,706 chars were duplicated text |
| **Estimated Tokens** | **~8,680 tokens** | 7,953 raw tokens | **524 unique tokens** | Exact SHA-256 deduplication of template |
| **Exposure Passes (@ 100K)** | ~11.5 passes (est.) | ~12.5 passes (raw) | **~190.8 passes (actual)** | Model trained on 524 tokens 190.8 times |

---

## 4. Reason for the Discrepancy

1. **Premature Character Summation**: In Phase 50 Workstream 2, the scale gap analysis naively summed all 316 SFT file sizes ($29,647 \text{ chars}$) and 18 corpus shards ($5,073 \text{ chars}$) before executing deduplication, assuming each file contained distinct content ($34,720 / 4 \approx 8,680 \text{ tokens}$).
2. **Hidden Exact Template Duplication**: 313 of the 316 SFT JSONL files contained identical copy-pasted definition instructions.
3. **Correct Deduplication Execution**: When `Phase50DatasetPipeline` ran with `Phase47CorpusExpander`, the exact SHA-256 deduplication engine (`raw_checksum`) properly filtered out the 313 duplicate files, yielding exactly 3 unique SFT records + 11 unique corpus records = **14 unique records**.
4. **Manifest Ground Truth**: The generated immutable dataset manifest `artifacts/phase50_dataset_manifest_v001.json` accurately recorded the true unique token count (**524 unique tokens**).

---

## 5. Authoritative Values & Counting Methodology

### Authoritative Unique Corpus Baseline
* **Authoritative Unique Records**: **14 records**
* **Authoritative Unique Characters**: **2,109 characters**
* **Authoritative Unique Tokens**: **524 tokens**
* **Phase 50 Training Exposure Tokens**: **100,000 tokens**
* **Authoritative Exposure Ratio**: **190.8 corpus-equivalent passes**

### Authoritative Counting Methodology
1. **Character Count**: Sum of `len(text)` after NFKC Tamil-safe normalization (preserving pulli and virama).
2. **Estimated Token Count**: `len(normalized_text) // 4` (Standard character-to-token heuristic for micro-transformer with vocabulary size 64).
3. **Exact Token Count**: Number of token IDs in tensor sequences passed to PyTorch forward pass.
4. **Deduplication Boundary**: Exact SHA-256 hash match on normalized text (`raw_checksum`) + 5-gram character Jaccard similarity ($\ge 0.85$).
5. **Training Exposure Tokens**: Sum of actual batch tokens ($B \times T$) over all backward optimizer steps committed to the token ledger.
"""
    (root / "phase51_corpus_forensic_reconciliation.md").write_text(reconcil_content, encoding="utf-8")

    print("Generated phase51_corpus_forensic_reconciliation.md.")

if __name__ == "__main__":
    pass
