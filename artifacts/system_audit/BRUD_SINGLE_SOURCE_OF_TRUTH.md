# BRUD AI — SINGLE SOURCE OF TRUTH ANALYSIS (WS15)
**Audit Date:** 2026-09-07

---

## RESPONSIBILITY → OWNER MAP

| Responsibility | Authoritative Module | Other Implementations | Conflict? |
|----------------|---------------------|----------------------|-----------|
| **Memory Storage** | ConversationMemoryRepository | None | NO |
| **Memory Retrieval** | MemoryService.retrieve() | None | NO |
| **Memory Reasoning** | MemoryReasoningEngine (memory_reasoner.py) | None | NO |
| **Memory Lifecycle** | MemoryLifecycleEngine (memory_lifecycle.py) | None | NO |
| **Memory Deduplication** | DuplicateKnowledgeEngine (duplicate_detector.py) | None | NO |
| **Memory Conflict** | ConflictKnowledgeEngine (conflict_detector.py) | None | NO |
| **Memory Consolidation** | MemoryConsolidatorEngine (memory_consolidator.py) | None | NO |
| **Memory Recall** | MemoryRecallEngine (memory_recall.py) | None | NO |
| **Public Chat Routing** | PublicChatRoutingService | MiniBrainPublicChatRuntimeService | PARTIAL CONFLICT |
| **Admin Chat AI** | AdminAssistantChatService (Phase 8) | MiniBrainLlmRuntimeService (MB-28) | ARCHITECTURAL CONFLICT |
| **Model Inference (Brud)** | InferenceRuntimeService | None | NO |
| **Model Inference (External)** | MiniBrainLlmAdapterProtocol | ExternalProviderMiniBrainAdapter | PARTIAL OVERLAP |
| **RAG Retrieval** | RagRetrievalService | None | NO |
| **RAG Ingestion** | RagIngestionService | controlled_rag_ingestion_service | Scoped (not duplicate) |
| **RAG Generation** | RagGenerationService | None | NO |
| **Provider Registry** | mini_brain_provider_settings_service | provider_settings_connection_adapters | Different scopes |
| **Authentication** | AdminRepository (admin.py) | None | NO |
| **Authorization (Admin)** | require_admin + AdminRepository | None | NO |
| **CSRF Protection** | require_csrf dependency | None | NO |
| **Audit Logging** | AuditLogRepository (phase2.py) | None | NO |
| **Tool Execution (Public)** | DeterministicToolExecutionService | None | NO |
| **Tool Execution (Admin)** | admin_assistant_tools.py | MiniBrainPluginRuntimeService | DIFFERENT SCOPES |
| **Prompt Construction** | core_model/mini_brain/llm_runtime/prompt_builder.py | Multiple inline | PARTIAL OVERLAP |
| **Context Construction** | ChatOrchestrationService | Multiple chat services | COMPLEX |
| **Language Classification** | core_model/rag/language_routing.classify_language() | None | NO |
| **Intent Classification (Admin)** | core_model/admin_assistant/intent.py | MB-28 intent | OVERLAP |
| **Knowledge Gap Capture** | KnowledgeGapCaptureService | None | NO |
| **Knowledge Gap Observation** | clarification_intelligence.classify_knowledge_gap() | None | NO |
| **Data Source Registry** | SourceRegistryService (data_source_service.py) | None | NO |
| **Corpus Pipeline** | Multiple corpus services | — | Scoped (not duplicate) |
| **Training Runtime** | pretraining_service + base_training_service | training_runtime_adapter | Layered (not duplicate) |
| **Tokenizer** | TokenizerService (tokenizer_registry.py) | None | NO |
| **Model Assignment** | ModelAssignmentService | None | NO |
| **Schema** | backend/database/schema.py | None | NO |
| **Config** | backend/core/config.py | None | NO |

---

## ARCHITECTURAL CONFLICTS

### CONFLICT 001 — Admin AI Dual System
**Responsibility:** Admin LLM intelligence
**Owner A:** AdminAssistantChatService (Phase 8)
**Owner B:** MiniBrainLlmRuntimeService (MB-28)
**Bridge:** `chat_action_bridge.propose_chat_action()`
**Risk:** MEDIUM — both active, bridge is narrow but present

### CONFLICT 002 — Public Chat Dual Entry
**Responsibility:** Public user chat
**Owner A:** PublicChatRoutingService via `/chat`
**Owner B:** MiniBrainPublicChatRuntimeService via `/public/chat-runtime/*`
**Risk:** LOW — different deployment scenarios intended

### CONFLICT 003 — Prompt Construction Multiple Locations
**Responsibility:** Building prompts for LLM
**Owner A:** `core_model/mini_brain/llm_runtime/prompt_builder.py`
**Owner B:** Inline construction in `AdminAssistantChatService`
**Owner C:** Inline construction in `PublicChatRoutingService`
**Risk:** LOW — different contexts, not truly conflicting

---

## CLEAR SINGLE OWNERS (NO CONFLICT)

1. Memory System — MemoryService is sole writer/reader
2. RAG Retrieval — RagRetrievalService is authoritative
3. Authentication — AdminRepository is sole auth authority
4. Audit Logging — AuditLogRepository is sole audit writer
5. Schema — schema.py is single source of truth
6. Language Classification — single function in core_model/rag
7. Knowledge Gap — single capture service
8. Model Assignment — single ModelAssignmentService

---
*WS15 Complete*
