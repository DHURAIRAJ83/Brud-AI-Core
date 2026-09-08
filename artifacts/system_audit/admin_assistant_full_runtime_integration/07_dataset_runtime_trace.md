# 07 DATASET RUNTIME TRACE

- Document & File Upload: Executed via `POST /api/admin/assistant/upload` -> parses PDF/datasets, extracts text, computes SHA-256 checksums, stages documents (`LEVEL 5 - E2E VERIFIED`).
- Dataset Management Pages: `DatasetsPage.jsx`, `SourcesRightsPage.jsx`, `DocumentWizardPage.jsx` (`LEVEL 5 - E2E VERIFIED`).
- Dataset Queries via Chat: `list_dataset_versions` and `get_dataset_version` callable via `AdminAssistantChatService` (`LEVEL 4 - CHAT CONNECTED`).
