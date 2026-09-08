# 07 RAG INTEGRATION REPORT

- Knowledge Base Retrieval: Checking "Use Knowledge Base" in `ChatPanel.jsx` calls `sendMiniBrainGroundedMessage` -> `POST /api/admin/mini-brain/llm-runtime/grounded-chat` -> queries `RagRepository` vector chunks and appends citations (`END_TO_END_WORKING`).
- RAG Workspace Pages: `RagPage.jsx` and `RagSandboxPage.jsx` connect to `GET /api/admin/rag` and `POST /api/admin/rag-sandbox` (`END_TO_END_WORKING`).
