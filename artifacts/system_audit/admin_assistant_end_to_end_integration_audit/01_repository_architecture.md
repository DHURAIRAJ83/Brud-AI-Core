# 01 REPOSITORY ARCHITECTURE MAP

- Baseline Commit: `df054cb100b58d99acf42a72d18dcbcb7dcbd5f8`
- Core Architecture Layout:
  - `backend/`: FastAPI application, routers (`backend/api/routes/`), database repositories (`backend/database/repositories/`), services (`backend/services/`), models (`backend/models/`).
  - `core_model/`: 48 canonical components covering ops, training, evaluation, governance, RAG, providers, localization, admin assistant registries.
  - `apps/admin-dashboard/`: React + Vite admin frontend, pages (`apps/admin-dashboard/src/pages/`), components (`apps/admin-dashboard/src/components/`), API service (`apps/admin-dashboard/src/services/api.js`).
  - `apps/chatbot/`: End-user React chatbot UI.
  - `scripts/`: Production & utility scripts (`01_prepare_data.py`, `02_train_tokenizer.py`, `03_pretrain.py`, `04_finetune.py`, `05_quantize.py`, `06_test_inference.py`).
  - `tests/`: 312 unit & integration test files (`tests/core_model/`, `tests/backend/`, `tests/database/`).

DATABASE SCHEMA:
- Version: `SCHEMA_VERSION = 78` in `backend/database/schema.py`.
- Persistence: SQLite database at `backend/database/brud_ai.db`.
