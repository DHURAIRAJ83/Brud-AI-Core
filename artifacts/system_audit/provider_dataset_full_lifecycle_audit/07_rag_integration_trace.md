# 07 RAG INTEGRATION TRACE

- Ingestion Pipeline: Approved documents and certified datasets chunked into `semantic_chunks` and indexed in `RagRepository` vector store collections.
- Chat Retrieval: `sendMiniBrainGroundedMessage` (`POST /api/admin/mini-brain/llm-runtime/grounded-chat`) retrieves vector chunks and injects them into prompt context with citations (`LEVEL 5 - PROVEN`).
