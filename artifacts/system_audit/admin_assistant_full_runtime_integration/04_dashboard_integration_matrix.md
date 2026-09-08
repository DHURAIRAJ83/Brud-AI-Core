# 04 DASHBOARD INTEGRATION MATRIX

| Page / Component | Route Called | Backend Service | Data Engine | Status |
|---|---|---|---|---|
| AdminAssistantPage | `/api/admin/assistant/governance-status` | `AdminAssistantService` | `EnterpriseGovernanceDashboardContract` | 🟢 LEVEL 5 - E2E VERIFIED |
| OverviewPage | `/api/admin/assistant/overview` | `AdminAssistantService` | SQLite Counts | 🟢 LEVEL 5 - E2E VERIFIED |
| DatasetsPage | `/api/admin/datasets` | `DatasetService` | `DatasetAdminRepository` | 🟢 LEVEL 5 - E2E VERIFIED |
| DocumentsPage | `/api/admin/documents` | `DocumentService` | `DocumentRepository` | 🟢 LEVEL 5 - E2E VERIFIED |
| RagPage | `/api/admin/rag` | `RagService` | `RagRepository` | 🟢 LEVEL 5 - E2E VERIFIED |
| RagSandboxPage | `/api/admin/rag-sandbox` | `RagService` | Vector Engine | 🟢 LEVEL 5 - E2E VERIFIED |
| ModelRegistryPage | `/api/admin/candidates` | `ModelReleaseService` | `CandidateModelRegistry` | 🟢 LEVEL 5 - E2E VERIFIED |
| BaseTrainingPage | `/api/admin/base-training` | `BaseTrainingService` | `SignedTrainingGateEngine` | 🟢 LEVEL 5 - E2E VERIFIED |
| GovernancePage | `/api/admin/governance` | `GovernanceApprovalService` | `RBACGovernanceEngine` | 🟢 LEVEL 5 - E2E VERIFIED |
| FeedbackPage | `/api/admin/assistant/feedback` | `ContextRepository` | SQLite Feedback Table | 🟢 LEVEL 5 - E2E VERIFIED |
| ConversationMemoryPage | `/api/admin/conversation-memory` | `MemoryService` | `ConversationMemoryRepository` | 🟢 LEVEL 5 - E2E VERIFIED |
