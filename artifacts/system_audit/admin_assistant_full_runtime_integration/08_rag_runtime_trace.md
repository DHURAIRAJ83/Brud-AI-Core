# 08 RAG RUNTIME TRACE

- Chunking & Embedding: Extracted document chunks stored in `RagRepository` SQLite/Vector store (`LEVEL 5 - E2E VERIFIED`).
- RAG Workspace Pages: `RagPage.jsx`, `RagSandboxPage.jsx` (`LEVEL 5 - E2E VERIFIED`).
- RAG Grounded Chat: Executed via `POST /api/admin/mini-brain/llm-runtime/grounded-chat` when KB toggle is ON (`LEVEL 5 - E2E VERIFIED`).
