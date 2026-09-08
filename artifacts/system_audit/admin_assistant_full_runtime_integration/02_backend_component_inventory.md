# 02 BACKEND COMPONENT INVENTORY

- Canonical Subsystems: 48 canonical components verified across `core_model/ops/`, `core_model/eval/`, `core_model/training/`.
- Repositories: 35 repository classes in `backend/database/repositories/` (`DatasetAdminRepository`, `DocumentRepository`, `RagRepository`, `AuditLogRepository`, `AdminApprovalRepository`, `PretrainingRepository`, etc.).
- Services: 42 service classes in `backend/services/` (`AdminAssistantService`, `AdminAssistantChatService`, `DocumentService`, `ImportService`, `DatasetService`, `RagService`, `GovernanceApprovalService`, `ProviderSettingsService`).
- Database Schema: Version `78` locked in `backend/database/schema.py` (Migrations 001–078 intact).
