# BRUD AI — MASTER ARCHITECTURE AUDIT (WS21)
**Audit Date:** 2026-09-07

---

## SYSTEM ARCHITECTURE DIAGRAM

```
┌─────────────────────────────────────────────────────────────────────┐
│                        BRUD AI SYSTEM                               │
├─────────────────┬─────────────────┬────────────────────────────────┤
│  Admin Dashboard │  Public Chatbot  │         Backend API            │
│  (React/Vite)    │  (React/Vite)   │         (FastAPI)              │
│  77 pages        │  Public chat UI │         156 route plugins       │
│  Hash routing    │                 │         Cookie + CSRF auth      │
└────────┬─────────┴────────┬────────┴───────────┬────────────────────┘
         │                  │                    │
         ▼                  ▼                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    BACKEND SERVICES LAYER                            │
├──────────────┬───────────────┬──────────────┬───────────────────────┤
│ Admin        │ Public Chat   │ Mini Brain   │  Data Pipeline        │
│ Assistant    │ Routing       │ LLM Runtime  │  (Corpus/Dataset/     │
│ Service      │ Service       │ Service      │   SFT/Training)       │
│ (Phase 8)    │ (Phase 18)    │ (MB-28)      │                       │
└──────┬───────┴───────┬───────┴──────┬───────┴───────────────────────┘
       │               │              │
       ▼               ▼              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    INTELLIGENCE LAYER                                │
├──────────────┬───────────────┬──────────────┬───────────────────────┤
│ Inference    │ Memory        │ RAG          │  Admin Intent         │
│ Runtime Svc  │ Service       │ Retrieval    │  Classification       │
│ (Phase 15)   │ (Phase 17)    │ Service      │  (action_registry)    │
│ Brud model   │ 8-phase       │              │                       │
└──────┬───────┴───────┬───────┴──────┬───────┴───────────────────────┘
       │               │              │
       ▼               ▼              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    CORE MODEL LAYER                                  │
├──────────────┬───────────────┬──────────────┬───────────────────────┤
│ architecture/│ inference_    │ rag/         │  mini_brain/          │
│ (BrudSmallV2)│ runtime/      │ (21 modules) │  intelligence/        │
│ model.py     │ (gen engine)  │              │  (8 engines)          │
└──────┬───────┴───────┬───────┴──────┬───────┴───────────────────────┘
       │               │              │
       ▼               ▼              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    DATABASE LAYER (SQLite)                           │
│           78 Repositories + 766 KB Schema                           │
│              Single authoritative database file                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## THREE-TIER ARCHITECTURE SEPARATION

### Tier 1: API / Transport
- FastAPI routes
- Pydantic request/response models
- Authentication dependencies
- Rate limiting

### Tier 2: Service / Business Logic  
- Service classes (243 files)
- Orchestration (ChatOrchestrationService, PublicChatRoutingService)
- Domain-specific business rules

### Tier 3: Repository / Persistence
- Repository classes (78 files)
- SQLite via connection pool
- Schema-driven table structure

---

## CROSS-CUTTING CONCERNS

| Concern | Implementation | Status |
|---------|----------------|--------|
| Authentication | Session cookies | ACTIVE |
| Authorization | require_admin + require_csrf | ACTIVE |
| Audit logging | AuditLogRepository | ACTIVE |
| Input validation | Pydantic + safety gates | ACTIVE |
| Error handling | BrudError hierarchy | ACTIVE |
| Config management | Settings dataclass | ACTIVE |
| Logging | backend/core/logging.py | ACTIVE |
| JSON serialization | backend/core/json_utils.py | ACTIVE |

---

## ARCHITECTURAL PATTERNS IN USE

| Pattern | Where | Notes |
|---------|-------|-------|
| Repository Pattern | All DB access | CONSISTENT |
| Service Pattern | All business logic | CONSISTENT |
| Dependency Injection | FastAPI depends() | CONSISTENT |
| Plugin Pattern | Route registry | CONSISTENT |
| Strategy Pattern | Provider adapters | CONSISTENT |
| Command Pattern | Admin proposals | CONSISTENT |
| Observer Pattern | Knowledge gap observation | CONSISTENT |
| Facade Pattern | Chat orchestration | CONSISTENT |

---

## KNOWN ARCHITECTURAL TENSIONS

| Tension | Description |
|---------|-------------|
| Two admin AI systems | Phase 8 AdminAssistant vs MB-28 LlmRuntime — intentional but complex |
| Two public chat paths | /chat vs /public/chat-runtime/* — different deployment scenarios |
| Monolithic Mini Brain | 39 services, 34 core modules — structurally sound but naviqation complexity |
| Thin vs thick services | Some services 5 KB; admin_assistant_tools.py is 119 KB |
| Placeholder infrastructure | MB-01 placeholder methods in MiniBrainService |

---

## IMPLEMENTATION COMPLETENESS

| Domain | Completeness | Evidence |
|--------|-------------|---------|
| Admin Authentication | 100% | Full session + CSRF |
| Public Chat | 95% | Full pipeline, streaming TBD |
| Admin Assistant (Phase 8) | 95% | Proposal/execute/audit complete |
| Mini Brain LLM Runtime | 85% | No real plugins ship |
| Memory System | 100% | All 8 intelligence phases verified |
| RAG Pipeline | 95% | Full pipeline; no HNSW |
| Dataset Pipeline | 100% | 17-stage sample pipeline |
| Training Pipeline | 85% | Core loops active; worker process |
| Tokenizer | 100% | Custom tokenizer implemented |
| Core Architecture | 100% | BrudSmallV2 fully implemented |
| Inference Runtime | 90% | Generation works; quantization TBD |
| Vision Pipeline | 20% | Services exist, likely stub |
| Voice Pipeline | 20% | Services exist, likely stub |

---
*WS21 Complete*
