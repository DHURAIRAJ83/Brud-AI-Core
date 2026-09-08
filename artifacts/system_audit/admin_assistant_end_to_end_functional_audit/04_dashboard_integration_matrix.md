# 04 ADMIN DASHBOARD INTEGRATION MATRIX

| Page / Component | Route Called | Backend Service | Data Engine | Status |
|---|---|---|---|---|
| AdminAssistantPage | `/api/admin/assistant/governance-status` | `AdminAssistantService` | `EnterpriseGovernanceDashboardContract` | 🟢 END_TO_END_WORKING |
| OverviewPage | `/api/admin/assistant/overview` | `AdminAssistantService` | SQLite Counts | 🟢 END_TO_END_WORKING |
| DatasetsPage | `/api/admin/datasets` | `DatasetService` | `DatasetAdminRepository` | 🟢 END_TO_END_WORKING |
| DocumentsPage | `/api/admin/documents` | `DocumentService` | `DocumentRepository` | 🟢 END_TO_END_WORKING |
| RagPage | `/api/admin/rag` | `RagService` | `RagRepository` | 🟢 END_TO_END_WORKING |
| RagSandboxPage | `/api/admin/rag-sandbox` | `RagService` | Vector Engine | 🟢 END_TO_END_WORKING |
| ModelRegistryPage | `/api/admin/candidates` | `ModelReleaseService` | `CandidateModelRegistry` | 🟢 END_TO_END_WORKING |
| BaseTrainingPage | `/api/admin/base-training` | `BaseTrainingService` | `SignedTrainingGateEngine` | 🟢 END_TO_END_WORKING |
| GovernancePage | `/api/admin/governance` | `GovernanceApprovalService` | `RBACGovernanceEngine` | 🟢 END_TO_END_WORKING |
| FeedbackPage | `/api/admin/assistant/feedback` | `ContextRepository` | SQLite Feedback Table | 🟢 END_TO_END_WORKING |
| ConversationMemoryPage | `/api/admin/conversation-memory` | `MemoryService` | `ConversationMemoryRepository` | 🟢 END_TO_END_WORKING |
