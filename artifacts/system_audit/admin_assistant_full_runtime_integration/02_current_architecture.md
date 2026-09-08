# 02 CURRENT ARCHITECTURE

- Backend Application: FastAPI app in `backend/main.py` with 94 route modules in `backend/api/routes/`.
- Core Engines: 48 canonical components in `core_model/ops/`, `core_model/eval/`, `core_model/training/`.
- Database Persistence: SQLite database version `78` locked in `backend/database/schema.py` (`backend/database/brud_ai.db`).
- Admin Assistant Chat Service: `AdminAssistantChatService` in `backend/services/admin_assistant_chat_service.py` controlling intent classification, tool invocation (`run_tool`), proposal creation (`propose_chat_action`), and deterministic guidance.
- Frontend App: React + Vite application in `apps/admin-dashboard`.
