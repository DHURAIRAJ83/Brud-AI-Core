# 07 DATASET → RAG → CHAT FLOW TRACE

- Document Upload: Handled via `assistantUpload` (`/api/admin/assistant/upload`) -> parses PDFs/datasets, extracts text, computes SHA-256 checksums, and stages documents (`END_TO_END_CONNECTED`).
- RAG Vector Indexing: Chunked text indexed into `RagRepository` SQLite/Vector store (`END_TO_END_CONNECTED`).
- Chat RAG Query: When "Use Knowledge Base" toggle is checked in `ChatPanel.jsx`, query goes to `/api/admin/mini-brain/llm-runtime/grounded-chat` -> retrieves relevant vector chunks -> generates LLM response with citations (`END_TO_END_CONNECTED`).
