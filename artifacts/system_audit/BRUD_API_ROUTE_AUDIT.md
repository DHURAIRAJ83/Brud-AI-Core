# BRUD AI — API ROUTE AUDIT (WS11)
**Audit Date:** 2026-09-07

---

## ROUTE REGISTRY OVERVIEW

`backend/api/route_registry.py` contains 156 registered route plugins.

### Loading Modes
- **Eager (enabled_by_default=True):** Always loaded — public APIs + core admin routes
- **Deferred (enabled_by_default=False):** Loaded unless BRUD_DEFER_ADMIN_TOOL_ROUTES is set

---

## PUBLIC ROUTES (public=True, always active)

| Plugin | Path Prefix | Status |
|--------|------------|--------|
| health | /health | ACTIVE |
| chat | /chat | ACTIVE |
| public_chat_runtime | /public/chat-runtime/* | ACTIVE |
| public_plugin_policy | /public/plugin-policy/* | ACTIVE |
| public_plugin_runtime | /public/plugin-runtime/* | ACTIVE |
| public_voice_runtime | /public/voice/* | ACTIVE |
| auth | /admin/login, /admin/logout, /admin/me | ACTIVE |
| rag | /rag/* | ACTIVE |

---

## ADMIN ROUTES — EAGER (enabled_by_default=True)

| Plugin | Notes |
|--------|-------|
| admin | Admin CRUD |
| admin_assistant | Proposals, chat, reviews |
| system | System status |
| imports | Data imports |
| tokenizers | Tokenizer management |
| core_models | Model registry |
| pretraining | Pre-training control |
| training_reliability | Training reliability |
| base_training | Base training |
| instruction_tuning | Fine-tuning |
| model_evaluation | Evaluation |
| model_release | Release management |
| inference_runtime | Runtime control |
| conversation_memory | Memory management |
| feedback | Feedback |
| corpus | Corpus management |
| pretraining_readiness | Readiness checks |
| data_sources | Data source management |
| manual_data | Manual data entry |
| semantic_chunks | Chunk studio |
| structured_records | Structured records |
| governance | Governance |
| governed_builds | Build pipelines |
| data_lineage | Data lineage |
| external_data_providers | External providers |
| incremental_training | Incremental training |
| knowledge_routing | Knowledge routing |
| knowledge_gap_admin | Knowledge gaps |
| candidate_admin | Candidate curation |
| controlled_ingestion_admin | Controlled ingestion |
| evaluation_admin | Evaluation admin |
| release_admin | Release admin |
| deployment_admin | Deployment admin |
| public_chat_admin | Public chat config |
| trusted_web_admin | Trusted web config |
| deterministic_tools_admin | Tools config |
| external_gateway_dataset_bridge | Gateway bridge |

---

## ADMIN ROUTES — DEFERRED (enabled_by_default=False)

These load unless BRUD_DEFER_ADMIN_TOOL_ROUTES env var is set:

### Document/Dataset Admin (6 routes)
- documents, documents_tamil_correction_rules, datasets, dataset_discovery, dataset_verification, dataset_sample_import

### Mini Brain Admin (34 routes)
- mini_brain, mini_brain_knowledge, mini_brain_intelligence, mini_brain_runtime, mini_brain_prompt_optimization, mini_brain_quality, mini_brain_capability, mini_brain_dataset_intelligence, mini_brain_advanced_dataset, mini_brain_learning_supervisor, mini_brain_release_pipeline, mini_brain_continuous_learning, mini_brain_continuous_learning_center, mini_brain_research_center, mini_brain_dataset_evolution, mini_brain_pipeline_coordinator, mini_brain_language_intelligence, mini_brain_vision_intelligence, mini_brain_vision_model, mini_brain_multimodal_dataset_generator, mini_brain_vision_rag, mini_brain_training_pipeline, mini_brain_evaluation_center, mini_brain_release_governance, mini_brain_external_ai_gateway, mini_brain_training_engine, mini_brain_pretraining_handoff, mini_brain_dataset_pipeline, mini_brain_public_chat_runtime, mini_brain_plugin_governance, mini_brain_plugin_runtime, mini_brain_voice_runtime, mini_brain_provider_settings, mini_brain_llm_runtime, mini_brain_local_setup, mini_brain_runtime_manager, mini_brain_health

### Other Deferred
- production_readiness, rag_sandbox, observability_admin, lock_maintenance_admin, disaster_recovery_admin, recovery_validation_admin

---

## KEY API ENDPOINTS

### Public Chat
| Method | Path | Service | Status |
|--------|------|---------|--------|
| POST | /chat | PublicChatRoutingService | ACTIVE |
| GET | /chat/capabilities | Resolvers | ACTIVE |
| POST | /chat/feedback | PublicChatRoutingRepository | ACTIVE |
| GET | /chat/help | Static | ACTIVE |

### Admin Assistant
| Method | Path | Service | Status |
|--------|------|---------|--------|
| POST | /admin/assistant/proposals | AdminAssistantService | ACTIVE |
| POST | /admin/assistant/proposals/{id}/review | AdminAssistantService | ACTIVE |
| POST | /admin/assistant/proposals/{id}/execute | AdminAssistantService | ACTIVE |
| POST | /admin/assistant/chat | AdminAssistantChatService | ACTIVE |

### Authentication
| Method | Path | Status |
|--------|------|--------|
| POST | /admin/login | ACTIVE |
| POST | /admin/logout | ACTIVE |
| GET | /admin/me | ACTIVE |

---

## DUPLICATE ROUTE ANALYSIS

| Finding | Severity |
|---------|----------|
| No duplicate public chat endpoints | CLEAN |
| No duplicate auth endpoints | CLEAN |
| Both `/chat` and `/public/chat-runtime/*` exist | POSSIBLE OVERLAP — different purposes |
| `rag` is public but also has admin RAG routes | EXPECTED — different operations |

### Finding: `/chat` vs `/public/chat-runtime/*`
- `/chat` → `routes/chat.py` → `PublicChatRoutingService` (Phase 18 orchestrator)
- `/public/chat-runtime/*` → `routes/public_chat_runtime.py` → mini_brain_public_chat_runtime_service
- **These are DIFFERENT systems** — separate entry points to different runtime paths
- **VERDICT:** D3 Partial Duplicate — architectural overlap but different implementations

---

## FINDINGS

1. **COMPLETE:** 156 routes registered and discoverable
2. **ACTIVE:** All eager routes load at startup
3. **PARTIAL:** Deferred routes load conditionally
4. **CONFLICT:** `/chat` and `/public/chat-runtime/*` represent two parallel public chat entry points
5. **NO ORPHAN ROUTES** detected — all have corresponding services
6. **CSRF:** Applied on all admin mutating routes

---
*WS11 Complete*
