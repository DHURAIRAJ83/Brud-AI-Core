# 06 RAG INTEGRATION AUDIT

- Pipeline Trace: Document Upload -> `DocumentService` -> Extraction/Chunking -> `RagRepository` -> SQLite Vector / Qdrant Store -> Retrieval.
- Dashboard Pages: `RagPage.jsx`, `RagSandboxPage.jsx` (`END_TO_END_CONNECTED`).
- Chat Assistant Access:
  - When "Use Knowledge Base" toggle in `ChatPanel.jsx` is checked: calls `POST /api/admin/mini-brain/llm-runtime/grounded-chat` -> retrieves top chunks -> injects into prompt context (`END_TO_END_CONNECTED`).
  - Chat tools to inspect vector index stats or collection size: `NOT_CONNECTED`.
