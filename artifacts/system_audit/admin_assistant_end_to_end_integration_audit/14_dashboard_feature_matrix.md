# 14 DASHBOARD FEATURE MATRIX

| Dashboard Feature | Frontend Component | API Route | Core Backend Engine | Status |
|---|---|---|---|---|
| Overview | `OverviewPage.jsx` | `/api/admin/assistant/overview` | `AdminAssistantService` | END_TO_END_CONNECTED |
| Governance Status | `AdminAssistantPage.jsx` | `/api/admin/assistant/governance-status` | `EnterpriseGovernanceDashboardContract` | END_TO_END_CONNECTED |
| Datasets | `DatasetsPage.jsx` | `/api/admin/datasets` | `DatasetAdminRepository` | END_TO_END_CONNECTED |
| Documents | `DocumentsPage.jsx` | `/api/admin/documents` | `DocumentService` | END_TO_END_CONNECTED |
| RAG Workspace | `RagPage.jsx` | `/api/admin/rag` | `RagRepository` | END_TO_END_CONNECTED |
| RAG Sandbox | `RagSandboxPage.jsx` | `/api/admin/rag-sandbox` | `RagRepository` | END_TO_END_CONNECTED |
| Model Registry | `ModelRegistryPage.jsx` | `/api/admin/candidates` | `CandidateModelRegistry` | END_TO_END_CONNECTED |
| Base Training | `BaseTrainingPage.jsx` | `/api/admin/base-training` | `SignedTrainingGateEngine` | END_TO_END_CONNECTED |
| Provider Settings | `ProviderSettingsTab.jsx` | `/api/admin/mini-brain/provider-settings` | `ProviderSettingsService` | END_TO_END_CONNECTED |
| Feedback | `FeedbackPage.jsx` | `/api/admin/assistant/feedback` | `AdminAssistantContextRepository` | END_TO_END_CONNECTED |
