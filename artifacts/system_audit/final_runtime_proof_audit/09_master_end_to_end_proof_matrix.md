# 09 MASTER END-TO-END PROOF MATRIX

| Lifecycle Transition | Calling Path / Component | Runtime Result | Connection Status |
|---|---|---|---|
| **DATASET → DOCUMENT INGESTION** | `ChatPanel` Upload / `DocumentsPage` -> `DocumentService` | Document staged with SHA-256 checksum | 🟢 CONNECTED |
| **DOCUMENT → NORMALIZATION** | `ImportService` -> `data_cleaner.py` | Text cleaned & normalized | 🟢 CONNECTED |
| **NORMALIZATION → QUALITY / VALIDATION** | `DatasetAdminRepository` | Quality score & rights check | 🟢 CONNECTED |
| **QUALITY → DATASET VERSION** | `DatasetAdminRepository` | Version manifest created | 🟢 CONNECTED |
| **DATASET VERSION → RAG INDEXING** | `RagRepository` | Semantic chunks created | 🟢 CONNECTED |
| **RAG INDEXING → VECTOR STORAGE** | SQLite Vector / Qdrant Adapter | Chunks indexed in collection | 🟢 CONNECTED |
| **VECTOR STORAGE → RAG RETRIEVAL** | `POST /mini-brain/llm-runtime/grounded-chat` | Top-k chunks retrieved | 🟢 CONNECTED |
| **RAG RETRIEVAL → CHAT CITATIONS** | `ChatPanel.jsx` grounded mode | Source citations appended | 🟢 CONNECTED |
| **CHAT → 48-TOOL ROUTER** | `POST /api/admin/assistant/chat` | `run_tool` deterministic query | 🟢 CONNECTED |
| **48-TOOL ROUTER → GOVERNANCE STATUS** | `EnterpriseGovernanceDashboardContract` | Live status & 4 blockers returned | 🟢 CONNECTED |
| **CHAT → USER FEEDBACK** | `POST /api/admin/assistant/feedback` | Feedback stored in DB | 🟢 CONNECTED |
| **FEEDBACK → LEARNING QUEUE** | `AdminAssistantContextRepository` | Candidate in review queue | 🟢 CONNECTED |
| **LEARNING QUEUE → CURATED DATA** | `DatasetAdminRepository` | Curated dataset export | 🟢 CONNECTED |
| **CURATED DATA → TRAINING GATE** | `SignedTrainingGateEngine` | Token check (`ABSENT`) | 🔒 GOVERNANCE_BLOCKED |
| **TRAINING GATE → TRAINING PIPELINE** | Pretraining CLI / Entry Point | Fail-closed execution block | 🔒 GOVERNANCE_BLOCKED |
| **TRAINING PIPELINE → CANDIDATE MODEL** | `CandidateModelRegistry` | Candidate stored (no mutation) | 🔒 GOVERNANCE_BLOCKED |
| **CANDIDATE MODEL → EVALUATION** | `RedTeamEvaluator` | Red-team score stored | 🟢 CONNECTED |
| **EVALUATION → PROMOTION GATE** | `ProductionPromotionGate` | Token check (`ABSENT`) | 🔒 GOVERNANCE_BLOCKED |
| **PROMOTION GATE → CANARY** | `CanaryDeploymentController` | Traffic share locked at `0.0` | 🔒 GOVERNANCE_BLOCKED |
| **CANARY → PUBLIC CHAT GATE** | `PublicChatAdmissionGate` | Public chat locked (`FALSE`) | 🔒 GOVERNANCE_BLOCKED |
| **PUBLIC CHAT GATE → PUBLIC MODEL** | Production Runtime | Production state locked (`LOCKED`) | 🔒 GOVERNANCE_BLOCKED |
