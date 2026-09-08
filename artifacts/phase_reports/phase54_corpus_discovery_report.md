# Phase 54 Corpus Discovery Report: Exhaustive Repository Inventory

**Execution Date:** 2026-08-29  
**Discovery Scope:** All potential corpus paths (`data/`, `artifacts/`, `core_model/`, `docs/`)  
**Governance Policy:** Non-Negotiable Rule 1 (Zero Fabrication) & Rule 2 (Rights-First Ingestion)  

---

## 1. Executive Summary

An exhaustive read-only scan of the entire repository discovered **9,131 candidate files** across candidate paths.
In strict adherence to Non-Negotiable Condition 2, data without verified rights or provenance was rejected.
Specifically, **8,115 raw unapproved PDFs** in `data/documents/pending/` were rejected due to unknown rights,
and **19 pending import files** in `data/imports/pending/` were confirmed to be duplicates of already-processed files.

A total of **7 approved authentic source categories** were identified and validated in `phase54_acquisition_registry.json`.

---

## 2. Exhaustive Discovery Inventory

| Source Path | File Type | Category | Byte Size | Records | Estimated Tokens | Provenance | Rights Status | Admission Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `data/imports/processed/1a8c33171970478ea59dfe160475509d.jsonl` | jsonl | imports_processed | 11,710 B | 23 | 2,132 | project_authored_and_verified_imports | 100%_verified | **APPROVED** |
| `data/imports/processed/3d2b14bb88614826b7e34d626a8544bf.jsonl` | jsonl | imports_processed | 843 B | 6 | 151 | project_authored_and_verified_imports | 100%_verified | **APPROVED** |
| `data/corpus_exports/13318bdd-c585-45d3-9aca-98f4d50f4343/train/shard-00000.jsonl` | jsonl | corpus_exports | 4,169 B | 8 | 975 | sovereign_governed_corpus_export | 100%_verified | **APPROVED** |
| `data/corpus_exports/ab474f97-2e48-43a3-b4a2-4e68f1d718d7/train/shard-00000.jsonl` | jsonl | corpus_exports | 2,106 B | 3 | 431 | sovereign_governed_corpus_export | 100%_verified | **APPROVED** |
| `data/corpus_exports/c7d1889a-e4dd-452e-b0ff-1c6d92de30aa/train/shard-00000.jsonl` | jsonl | corpus_exports | 3,427 B | 4 | 652 | sovereign_governed_corpus_export | 100%_verified | **APPROVED** |
| `data/corpus_exports/e8f5d7bc-e2d8-46e9-a880-f762df8818a1/train/shard-00000.jsonl` | jsonl | corpus_exports | 2,163 B | 3 | 445 | sovereign_governed_corpus_export | 100%_verified | **APPROVED** |
| `data/manual_verification_phase20/exports/1de84eff-8055-4065-98e8-8751b725939a/test/shard-00000.jsonl` | jsonl | manual_verification_exports | 1,881 B | 3 | 390 | manual_verified_clean_benchmark | 100%_verified | **APPROVED** |
| `data/manual_verification_phase20/exports/1de84eff-8055-4065-98e8-8751b725939a/train/shard-00000.jsonl` | jsonl | manual_verification_exports | 16,492 B | 24 | 3,325 | manual_verified_clean_benchmark | 100%_verified | **APPROVED** |
| `data/manual_verification_phase20/exports/1de84eff-8055-4065-98e8-8751b725939a/validation/shard-00000.jsonl` | jsonl | manual_verification_exports | 1,148 B | 2 | 249 | manual_verified_clean_benchmark | 100%_verified | **APPROVED** |
| `data/manual_verification_phase20_clean/exports/d7f5d0e3-179b-4a7b-b078-9d0bd66ea0dc/test/shard-00000.jsonl` | jsonl | manual_verification_exports | 1,960 B | 3 | 387 | manual_verified_clean_benchmark | 100%_verified | **APPROVED** |
| `data/manual_verification_phase20_clean/exports/d7f5d0e3-179b-4a7b-b078-9d0bd66ea0dc/train/shard-00000.jsonl` | jsonl | manual_verification_exports | 16,125 B | 23 | 3,295 | manual_verified_clean_benchmark | 100%_verified | **APPROVED** |
| `data/manual_verification_phase20_clean/exports/d7f5d0e3-179b-4a7b-b078-9d0bd66ea0dc/validation/shard-00000.jsonl` | jsonl | manual_verification_exports | 641 B | 1 | 129 | manual_verified_clean_benchmark | 100%_verified | **APPROVED** |
| `data/manual_verification_phase20/approved_root/sample_agriculture.txt` | txt | manual_verification_approved_root | 1,091 B | 5 | 113 | project_authored_verification_fixtures | 100%_verified | **APPROVED** |
| `data/manual_verification_phase20/approved_root/sample_education.jsonl` | jsonl | manual_verification_approved_root | 1,046 B | 5 | 122 | project_authored_verification_fixtures | 100%_verified | **APPROVED** |
| `data/manual_verification_phase20/approved_root/sample_government.csv` | csv | manual_verification_approved_root | 825 B | 5 | 93 | project_authored_verification_fixtures | 100%_verified | **APPROVED** |
| `data/manual_verification_phase20/approved_root/sample_literature.docx` | docx | manual_verification_approved_root | 36,911 B | 1 | 68 | project_authored_verification_fixtures | 100%_verified | **APPROVED** |
| `data/manual_verification_phase20/approved_root/sample_mixed.md` | md | manual_verification_approved_root | 966 B | 10 | 147 | project_authored_verification_fixtures | 100%_verified | **APPROVED** |
| `data/manual_verification_phase20/approved_root/tamil_ocr.pdf` | pdf | manual_verification_approved_root | 11,602,675 B | 1 | 0 | project_authored_verification_fixtures | 100%_verified | **EXCLUDED_RAW_OCR** |
| `data/manual_verification_phase20/approved_root/tamil_selectable.pdf` | pdf | manual_verification_approved_root | 81,779 B | 3 | 214 | project_authored_verification_fixtures | 100%_verified | **APPROVED** |
| `data/manual_verification_phase20_clean/approved_root/clean_agriculture.txt` | txt | manual_verification_approved_root | 1,472 B | 10 | 160 | project_authored_verification_fixtures | 100%_verified | **APPROVED** |
| `data/manual_verification_phase20_clean/approved_root/clean_agriculture_duplicate.txt` | txt | manual_verification_approved_root | 1,472 B | 10 | 160 | project_authored_verification_fixtures | 100%_verified | **APPROVED** |
| `data/manual_verification_phase20_clean/approved_root/clean_education.jsonl` | jsonl | manual_verification_approved_root | 1,216 B | 6 | 145 | project_authored_verification_fixtures | 100%_verified | **APPROVED** |
| `data/manual_verification_phase20_clean/approved_root/clean_government.csv` | csv | manual_verification_approved_root | 815 B | 5 | 94 | project_authored_verification_fixtures | 100%_verified | **APPROVED** |
| `data/manual_verification_phase20_clean/approved_root/clean_literature.docx` | docx | manual_verification_approved_root | 36,981 B | 1 | 89 | project_authored_verification_fixtures | 100%_verified | **APPROVED** |
| `data/manual_verification_phase20_clean/approved_root/clean_mixed.md` | md | manual_verification_approved_root | 999 B | 11 | 173 | project_authored_verification_fixtures | 100%_verified | **APPROVED** |
| `data/manual_verification_phase20_clean/approved_root/tamil_clean_ocr.pdf` | pdf | manual_verification_approved_root | 11,602,675 B | 1 | 0 | project_authored_verification_fixtures | 100%_verified | **EXCLUDED_RAW_OCR** |
| `data/manual_verification_phase20_clean/approved_root/tamil_clean_selectable.pdf` | pdf | manual_verification_approved_root | 77,697 B | 1 | 71 | project_authored_verification_fixtures | 100%_verified | **APPROVED** |
| `data/manual_verification_phase20/tokenizers/corpora/0b58b763-b7d6-4b0e-943c-bd4e075dfa84/corpus.txt` | txt | tokenizers_corpora | 3,994 B | 54 | 480 | project_authored_tokenizer_pretraining | 100%_verified | **APPROVED** |
| `data/manual_verification_phase20_clean/tokenizers/corpora/548f0448-c86d-4d6c-8326-52cc8a9f0315/corpus.txt` | txt | tokenizers_corpora | 4,321 B | 60 | 546 | project_authored_tokenizer_pretraining | 100%_verified | **APPROVED** |
| `data/manual_verification_phase21a/tokenizers/corpora/ad3f9e03-ee03-42fc-9a84-5a0ecf2d79b9/corpus.txt` | txt | tokenizers_corpora | 6,686 B | 27 | 801 | project_authored_tokenizer_pretraining | 100%_verified | **APPROVED** |
| `data/manual_verification_phase21a/tokenizers/corpora/b140ce2d-784f-4369-ad57-a6a954f856c5/corpus.txt` | txt | tokenizers_corpora | 6,686 B | 27 | 801 | project_authored_tokenizer_pretraining | 100%_verified | **APPROVED** |
| `data/manual_verification_phase21a/tokenizers/corpora/bdcff05e-1dda-4618-a1ee-b68e3234dbe7/corpus.txt` | txt | tokenizers_corpora | 6,686 B | 27 | 801 | project_authored_tokenizer_pretraining | 100%_verified | **APPROVED** |
| `data/tokenizers/corpora/basetrain-corpus.txt` | txt | tokenizers_corpora | 1,952 B | 37 | 256 | project_authored_tokenizer_pretraining | 100%_verified | **APPROVED** |
| `data/tokenizers/corpora/instrtune-corpus.txt` | txt | tokenizers_corpora | 1,991 B | 54 | 256 | project_authored_tokenizer_pretraining | 100%_verified | **APPROVED** |
| `data/tokenizers/corpora/phase9-test-corpus.txt` | txt | tokenizers_corpora | 114 B | 3 | 17 | project_authored_tokenizer_pretraining | 100%_verified | **APPROVED** |
| `data/document_sft_exports/*.jsonl` | jsonl | document_sft_exports | 101,382 B | 316 | 25,030 | governed_document_sft_pipeline | 100%_verified | **APPROVED** |
| `data/dataset_exports/**/*.jsonl` | jsonl | dataset_exports | 116,378 B | 426 | 26,849 | project_authored_synthetic_dialogue | 100%_verified | **APPROVED** |
| `data/imports/quarantine/8ba3e041e19d441bbe23ce4db889931b.csv` | csv | imports_quarantine | 104 B | 2 | 12 | quarantined_import | unverified | **QUARANTINED_UNVERIFIED_RIGHTS** |
| `data/imports/quarantine/c45c5fcd2c6949a2bbe48813cc8c2f2e.txt` | txt | imports_quarantine | 91 B | 2 | 13 | quarantined_import | unverified | **QUARANTINED_UNVERIFIED_RIGHTS** |
| `data/imports/quarantine/db3367a5dc5f40b78bf2f5928c507f74.jsonl` | jsonl | imports_quarantine | 843 B | 6 | 154 | quarantined_import | unverified | **QUARANTINED_UNVERIFIED_RIGHTS** |
| `data/imports/pending/*.jsonl` | jsonl | imports_pending | 38,714 B | 19 | 0 | unreviewed_inbound_import | unverified | **REJECTED_UNREVIEWED_AND_DUPLICATE** |
| `data/documents/pending/*.pdf` | pdf | raw_documents_pending | 153,909,296 B | 8,115 | 0 | external_unreviewed_documents | unknown | **REJECTED_UNAPPROVED_RAW_PDF** |

---

## 3. Approved Acquisition Registry Summary

The following authentic sources have been registered in `phase54_acquisition_registry.json`:
1. **Imports Processed (`data/imports/processed/*.jsonl`):** Contains Bharathiyar poems, Thirukkural couplets, Tamil vocabulary, and animal/bird factual paragraphs.
2. **Corpus Exports (`data/corpus_exports/**/*.jsonl`):** Historical approved sovereign training shards.
3. **Manual Verification Exports (`data/manual_verification_phase20*/**/shard-*.jsonl`):** Phase 20 and 20 Clean verified benchmark shards.
4. **Manual Verification Approved Root Documents (`data/manual_verification_phase20*/approved_root/*`):** Clean educational Q&A, government notices, agriculture reports, and literature excerpts.
5. **Tokenizer Corpora (`data/**/corpora/**/*.txt`):** High-density linguistic pre-training lines.
6. **Document SFT Exports (`data/document_sft_exports/*.jsonl`):** Governed instruction-response pairs.
7. **Dataset Exports (`data/dataset_exports/**/*.jsonl`):** Governed synthetic dialogue pairs.

---

## 4. Discovery Conclusion

- Total Discovered Candidate Files: **9,131**
- Total Excluded / Rejected Files: **8,138** (8,115 raw PDFs, 19 duplicate pending imports, 4 OCR PDFs/quarantines)
- Total Admitted Authentic Sources: **7 Categories** (encompassing ~993 candidate files)
- Ingestion Readiness: Ready for Workstream 4 (Corpus Governance V2) and Workstream 5 (Advanced Deduplication).