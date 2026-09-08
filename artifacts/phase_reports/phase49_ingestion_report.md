# Phase 49 Corpus Ingestion and Dataset Manifest Report

## 1. Ingestion Architecture
* **Class**: `core_model.corpus.phase49_ingestion_scheduler.Phase49IngestionScheduler`
* **7-Stage Pipeline**:
  `DISCOVERED` -> `VALIDATING` -> `APPROVAL_CHECK` -> `SANITIZING` -> `DEDUPLICATING` -> `MANIFESTING` -> `READY_FOR_TRAINING`.

## 2. Ingestion Governance Controls
* **Sovereign Rights Verification**: Fail-closed check requiring explicitly granted approval and distribution rights.
* **PII Redaction**: Regex-based redaction of emails (`[REDACTED_EMAIL]`) and phone numbers (`[REDACTED_PHONE]`).
* **Secret Scanning**: Scans for API keys, AWS tokens, private keys, and passwords, failing closed if detected.
* **Prompt Injection Quarantine**: Detects adversarial injection triggers (`ignore previous instructions`, `bypass safety rules`) and diverts records to quarantine.
* **Tamil-Safe Unicode Normalization**: Applies NFKC normalization while strictly preserving Tamil virama (pulli) and compound glyph structures. Detects orphan combining marks.
* **Exact SHA-256 Deduplication**: Generates deterministic SHA-256 hashes per document, pruning duplicates across ingestion windows.

## 3. Dataset Manifest Binding
* Output: `artifacts/phase49_dataset_manifest_<version>.json`
* Manifest Hash: SHA-256 digest of concatenated record hashes, tokenizer hash, and preprocessing version.
* Enforcement: Checkpoints record the active `dataset_manifest_hash`. Resuming training with a different manifest hash raises `DatasetManifestMismatchError`.
