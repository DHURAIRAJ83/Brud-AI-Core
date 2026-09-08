# 02 PATH A: ADMIN DATA UPLOAD FORENSIC TRACE

- Upload Path: `ChatPanel.jsx` / `DocumentsPage.jsx` -> `assistantUpload()` / `POST /api/admin/assistant/upload` -> `DocumentService` -> `ImportService`.
- Normalization & Cleaning: Text extracted, normalized via `data_cleaner.py`, deduplicated, and staged into `documents` and `dataset_records` tables.
- Rights & Provenance: Review proposals created via `AdminApprovalRepository`.
- Downstream RAG & Training: Approved document chunks indexed in `RagRepository`; dataset split manifests exported by `DatasetAdminRepository` (`LEVEL 5 - PROVEN`).
