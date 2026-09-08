# 02 BACKEND SUBSYSTEM INVENTORY

- Core Backend Engine: 48 canonical components in `core_model/ops/`, `core_model/eval/`, `core_model/training/`.
- Repository Layer: 35 repository classes in `backend/database/repositories/` (`DatasetAdminRepository`, `DocumentRepository`, `RagRepository`, `AuditLogRepository`, `AdminApprovalRepository`, `PretrainingRepository`, etc.).
- Service Layer: 42 service classes in `backend/services/` (`AdminAssistantService`, `DocumentService`, `ImportService`, `DatasetService`, `RagService`, `GovernanceApprovalService`, `ProviderSettingsService`).
- Database Schema: Version `78` locked in `backend/database/schema.py` (Migrations 001–078 intact).
