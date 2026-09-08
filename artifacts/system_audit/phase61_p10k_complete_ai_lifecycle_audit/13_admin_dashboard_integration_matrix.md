# 13 ADMIN DASHBOARD INTEGRATION MATRIX

| Subsystem Page | FastAPI Route | Service | Database Table | Status |
|---|---|---|---|---|
| Datasets | `/api/admin/datasets` | `DatasetService` | `dataset_sources`, `dataset_records` | LEVEL 5 - VERIFIED |
| Documents | `/api/admin/documents` | `DocumentService` | `documents` | LEVEL 5 - VERIFIED |
| RAG | `/api/admin/rag` | `RagService` | `rag_collections`, `semantic_chunks` | LEVEL 5 - VERIFIED |
| RAG Sandbox | `/api/admin/rag-sandbox` | `RagService` | Sandbox Index | LEVEL 5 - VERIFIED |
| Model Registry | `/api/admin/candidates` | `ModelReleaseService` | `model_registry` | LEVEL 5 - VERIFIED |
| Base Training | `/api/admin/base-training` | `BaseTrainingService` | `training_jobs` | LEVEL 5 - VERIFIED |
| Governance | `/api/admin/governance` | `GovernanceApprovalService` | `admin_approvals` | LEVEL 5 - VERIFIED |
| Feedback | `/api/admin/assistant/feedback` | `ContextRepository` | `admin_assistant_feedback` | LEVEL 5 - VERIFIED |
| Memory | `/api/admin/conversation-memory` | `MemoryService` | `conversation_turns` | LEVEL 5 - VERIFIED |
