# Phase 39 — Dataset Governance Report

## 1. Production Dataset Registry Specification
Every production pretraining dataset must be registered with immutable metadata:
- **`dataset_id`**: Globally unique canonical identifier (e.g. `brud-sovereign-ta-en-v1`).
- **`name`**: Descriptive corpus designation.
- **`version`**: Semantic version string (`1.0.0`).
- **`language`**: Target language code (`ta`, `en`, `mixed`).
- **`source`**: Originating collection source / archive.
- **`provenance`**: Lineage traceability graph identifier.
- **`license / rights`**: Explicit legal attribution and usage license.
- **`record_count`**: Total validated text records.
- **`train_count` / `val_count` / `test_count`**: Strict split boundaries.
- **`sha256`**: Deterministic content hash of canonical JSONL file.
- **`quality_status`**: Review verdict (`approved`, `rejected`, `quarantined`).
- **`approval_status`**: Multi-signature admin governance flag.

---

## 2. Ingestion Boundary & Formats
- Supported formats: UTF-8 JSONL, plain text (`.txt`), structured documents.
- PDFs: Text extraction requires OCR/extraction validation, layout verification, and rejection of non-text or corrupted pages.
- Auditing: Unapproved external scraped files are quarantined automatically.
