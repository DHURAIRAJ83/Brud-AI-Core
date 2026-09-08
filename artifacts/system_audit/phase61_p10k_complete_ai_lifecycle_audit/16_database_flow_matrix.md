# 16 DATABASE FLOW MATRIX

- DB File: `backend/database/brud_ai.db` (Schema Version `78`).
- Key Tables: `dataset_sources`, `dataset_records`, `documents`, `semantic_chunks`, `rag_collections`, `model_versions`, `training_jobs`, `admin_approvals`, `audit_events`, `admin_assistant_feedback`, `conversation_turns`.
- Database Connection: Pooled SQLite connections with WAL mode and foreign key enforcement.
