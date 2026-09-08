# 03 DATASET INGESTION & QUALITY TRACE

- Document Ingestion: Uploading PDF/dataset files via chat or dashboard invokes `DocumentService` / `ImportService` (`POST /api/admin/assistant/upload`).
- Text Extraction & Normalization: Text is extracted, normalized (Tamil/English/Tanglish), and deduplicated via `data_cleaner.py`.
- Quality & Rights Validation: Evaluated by `DatasetAdminRepository` and `RightsGovernanceEngine`. Review proposals require explicit Admin approval (`CONNECTED`).
