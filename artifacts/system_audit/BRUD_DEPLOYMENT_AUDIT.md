# BRUD AI — DEPLOYMENT AUDIT (WS19)
**Audit Date:** 2026-09-07

---

## DEPLOYMENT CONFIGURATION

| File | Status | Notes |
|------|--------|-------|
| `deploy/` directory | PARTIALLY_ACTIVE | Deployment scripts |
| `config/` directory | ACTIVE | Config files |
| `backend/core/config.py` | ACTIVE | Settings class |
| `requirements.txt` | ACTIVE | Python dependencies |
| `apps/admin-dashboard/package.json` | ACTIVE | Frontend dependencies |
| `apps/chatbot/package.json` | ACTIVE | Chat frontend dependencies |

---

## RUNTIME CONFIGURATION (Settings class)

| Setting | Type | Notes |
|---------|------|-------|
| `database_path` | str | SQLite database location |
| `database_wal` | bool | WAL mode flag |
| `admin_cookie_name` | str | Session cookie name |
| `csrf_cookie_name` | str | CSRF cookie name |
| `csrf_header_name` | str | CSRF header name |
| `public_chat_rate_limit_max_requests` | int | Rate limit count |
| `public_chat_rate_limit_window_seconds` | int | Rate limit window |
| `cors_origins` | list | Allowed CORS origins |

---

## ENTRY POINTS

| Entry Point | File | Purpose |
|------------|------|---------|
| Backend API | `backend/main.py` | FastAPI app |
| Training Worker | `backend/training_worker.py` | Training process |
| Instruction Tuning Worker | `backend/instruction_tuning_worker.py` | SFT process |
| Admin CLI | `backend/admin_cli.py` | Admin command line |
| Corpus CLI | `backend/corpus_cli.py` | Corpus command line |
| Inference CLI | `backend/inference_runtime_cli.py` | Inference CLI |
| Admin Dashboard | `apps/admin-dashboard/` | Vite dev or dist build |
| Public Chatbot | `apps/chatbot/` | Vite dev or dist build |

---

## PROCESS ARCHITECTURE

```
[FastAPI Process]
  - Loads all routes at startup
  - ConnectionPool initialized in lifespan
  - All admin + public requests handled here

[Training Worker Process(es)]
  - Spawned by PretrainingService / InstructionTuningService
  - Separate process, communicates via DB status rows
  - Uses core_model/training/ and core_model/instruction_tuning/

[Frontend Build]
  - Admin Dashboard: Vite SPA served as static files
  - Chatbot: Vite SPA served as static files
```

---

## PRODUCTION READINESS

`backend/services/production_readiness_service.py` (140+ KB) — ACTIVE
- Comprehensive production readiness checks
- Pre-deployment validation
- Multiple gates: data quality, model quality, RAG quality, safety

`core_model/production_readiness/` — ACTIVE
`core_model/capabilities/production_observability_service.py` — ACTIVE
`core_model/capabilities/disaster_recovery_service.py` — ACTIVE

---

## DEPLOYMENT FINDINGS

1. **ACTIVE:** Single SQLite database (no distributed DB required)
2. **ACTIVE:** FastAPI backend serves API
3. **ACTIVE:** Two separate frontend apps (admin + chatbot)
4. **ACTIVE:** Background training processes spawned by API
5. **COMPLETE:** Production readiness service (140+ KB)
6. **LIMITATION:** No containerization detected (no Dockerfile found)
7. **LIMITATION:** In-memory rate limiter — not distributed
8. **PARTIALLY_ACTIVE:** Deploy directory has scripts — not fully automated

---
*WS19 Complete*
