# 02 DATASET LIFECYCLE FORENSIC TRACE

- **Source Registration & Upload**: Handled via `DatasetAdminRepository` & `DocumentService` (`POST /api/admin/assistant/upload`, `POST /api/admin/documents`).
- **Text Normalization & Deduplication**: Managed by `DatasetService` and `data_cleaner.py` / `normalization.py`.
- **Rights & Provenance Approval**: Governed by `RightsGovernanceEngine` and `DatasetAdminRepository` (`dataset_record_review` proposals require Admin Review).
- **Dataset Versioning**: `DatasetAdminRepository` produces training split manifests and exports (`LEVEL 5 - VERIFIED`).
