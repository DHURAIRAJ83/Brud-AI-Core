# 02 REPOSITORY ARCHITECTURE DISCOVERY

- Backend Modules: 94 FastAPI route modules under `backend/api/routes/`, 35 SQLite repository classes in `backend/database/repositories/`, 42 services in `backend/services/`.
- Core Engines: 48 canonical components in `core_model/ops/`, `core_model/eval/`, `core_model/training/`.
- Database Persistence: SQLite database version `78` locked in `backend/database/schema.py` (`backend/database/brud_ai.db` with 518 tables).
- Admin Dashboard Frontend: React + Vite application in `apps/admin-dashboard` (25 pages/components verified).
