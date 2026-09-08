# 13 DATABASE & DATAFLOW TRACE

- Schema Version: `SCHEMA_VERSION = 78` in `backend/database/schema.py`.
- Persistence Tables: `dataset_sources`, `dataset_records`, `documents`, `semantic_chunks`, `rag_collections`, `model_versions`, `training_jobs`, `admin_approvals`, `audit_events`, `user_feedback`, `conversation_memory`.
- Integrity: All data writes flow through SQLite transactions with audit hashing. Zero orphan database connections.
