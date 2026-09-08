# 04 RAG RETRIEVAL & VECTOR SEARCH TRACE

- Vector Indexing: Extracted chunks are stored in `RagRepository` SQLite/Vector store collections (`CONNECTED`).
- Grounded Chat Search: Checking "Use Knowledge Base" in `ChatPanel.jsx` calls `POST /api/admin/mini-brain/llm-runtime/grounded-chat` -> retrieves top-k vector chunks -> appends source citations to LLM prompt context (`CONNECTED`).
