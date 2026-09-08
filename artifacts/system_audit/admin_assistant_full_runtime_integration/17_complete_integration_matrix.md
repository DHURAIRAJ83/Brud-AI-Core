# 17 COMPLETE INTEGRATION MATRIX

| Subsystem | Backend Code | Backend Service | API Route | Frontend Component | Chat Reachable | Dashboard Reachable | Runtime Verified | Read/Write | Governance Gate | RBAC | Tenant Isolation | Test Result | Final Classification |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Governance Status | 🟢 YES | `AdminAssistantService` | `/api/admin/assistant/governance-status` | `AdminAssistantPage.jsx` | 🟢 YES | 🟢 YES | 🟢 YES | READ | ADVISORY | YES | YES | PASSED | 🟢 END_TO_END_WORKING |
| Document Ingestion | 🟢 YES | `DocumentService` | `/api/admin/assistant/upload` | `ChatPanel.jsx` / `DocumentsPage.jsx` | 🟢 YES | 🟢 YES | 🟢 YES | WRITE | ADVISORY | YES | YES | PASSED | 🟢 END_TO_END_WORKING |
| RAG Grounded Chat | 🟢 YES | `RagService` | `/mini-brain/llm-runtime/grounded-chat` | `ChatPanel.jsx` (KB Toggle) | 🟢 YES | 🟢 YES | 🟢 YES | READ | ADVISORY | YES | YES | PASSED | 🟢 END_TO_END_WORKING |
| Assistant Chat Router | 🟢 YES | `AdminAssistantChatService` | `/api/admin/assistant/chat` | `ChatPanel.jsx` | 🟢 YES | 🟢 YES | 🟢 YES | READ | ADVISORY | YES | YES | PASSED | 🟢 END_TO_END_WORKING |
| Datasets Management | 🟢 YES | `DatasetService` | `/api/admin/datasets` | `DatasetsPage.jsx` | 🟢 YES | 🟢 YES | 🟢 YES | READ | ADVISORY | YES | YES | PASSED | 🟢 END_TO_END_WORKING |
| Model Registry | 🟢 YES | `ModelReleaseService` | `/api/admin/candidates` | `ModelRegistryPage.jsx` | 🟢 YES | 🟢 YES | 🟢 YES | READ | ADVISORY | YES | YES | PASSED | 🟢 END_TO_END_WORKING |
| Base Training Gate | 🟢 YES | `SignedTrainingGateEngine` | `/api/admin/base-training` | `BaseTrainingPage.jsx` | 🟢 YES | 🟢 YES | 🟢 YES | READ | FAIL-CLOSED | YES | YES | PASSED | 🟢 END_TO_END_WORKING |
| Provider Settings | 🟢 YES | `ProviderSettingsService` | `/api/admin/mini-brain/provider-settings` | `ProviderSettingsTab.jsx` | 🟢 YES | 🟢 YES | 🟢 YES | READ | ADVISORY | YES | YES | PASSED | 🟢 END_TO_END_WORKING |
| Feedback System | 🟢 YES | `ContextRepository` | `/api/admin/assistant/feedback` | `FeedbackPage.jsx` | 🟢 YES | 🟢 YES | 🟢 YES | WRITE | ADVISORY | YES | YES | PASSED | 🟢 END_TO_END_WORKING |
