# 06 RAG END-TO-END TRACE

- Retrieval Flow: Document Upload -> Extraction -> Chunking -> `RagRepository` -> SQLite Vector / Qdrant Store -> Grounded Search -> Citation Generation.
- Grounded Chat: Executed via `POST /api/admin/mini-brain/llm-runtime/grounded-chat` when KB toggle is ON (`LEVEL 5 - E2E VERIFIED`).
