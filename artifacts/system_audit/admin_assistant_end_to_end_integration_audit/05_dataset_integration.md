# 05 DATASET INTEGRATION AUDIT

- Backend Engine: `DatasetAdminRepository`, `DocumentService`, `ImportService`, `DataStudioService`.
- API Routes: `/api/admin/datasets`, `/api/admin/data-sources`, `/api/admin/documents`, `/api/admin/sample-import`.
- Dashboard Pages: `DatasetsPage.jsx`, `SourcesRightsPage.jsx`, `DocumentWizardPage.jsx`, `DatasetSampleImportPage.jsx` (`END_TO_END_CONNECTED`).
- Admin Assistant Access: `assistantUpload` (`/api/admin/assistant/upload`) processes uploads (`END_TO_END_CONNECTED`).
- Chat Tool Query: `list_dataset_versions` and `get_dataset_version` tools exist in `admin_assistant_tools.py` but are not invoked by widget chat (`UI_NOT_INVOKING`).
