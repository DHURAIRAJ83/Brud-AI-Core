# Master Brud AI System Audit — 12: Security & Governance Audit

**Audit Date:** 2026-09-01  
**Auditor:** Principal Security Architect & Governance Officer  
**Confidence Rating:** HIGH CONFIDENCE (Verified by source code inspection and configuration review)  

---

## 1. Security & Governance Control Matrix

| Governance / Security Control | Actual Implementation in Code | Verification Evidence | Residual Risk Level |
|---|---|---|---|
| **Admin Authentication** | Session cookies (`brud_admin_session`), bcrypt password hashing, lockout after 5 failed attempts (15 min) | `backend/services/auth_service.py`, `backend/core/config.py` | 🟢 **LOW** |
| **CSRF Defense** | Double-submit cookie pattern (`brud_csrf` cookie + `X-CSRF-Token` header) enforced on all mutating admin routes | `backend/api/auth.py::CsrfDependency` | 🟢 **LOW** |
| **Role-Based Access Control (RBAC)** | Dynamic resolution of `SUPER_ADMIN`, `ADMIN`, `AUDITOR`, `NONE`; permissions `tool.read`, `tool.propose`, `tool.execute` | `backend/services/admin_assistant_tool_governance.py` | 🟡 **MEDIUM** (Roles configured via env, not in DB) |
| **Public Chat Rate Limiting** | Sliding-window in-memory rate limiter per IP (`check_rate_limit`) | `backend/services/public_chat_rate_limiter.py` | 🟢 **LOW** |
| **Secret & Key Redaction** | Recursive scrubbing of passwords, tokens, hashes, and authorization headers before logging or returning | `backend/core/json_utils.py::redact_secrets` | 🟢 **LOW** |
| **Audit Logging** | Append-only audit events table (`audit_logs`) tracking actor, action, resource ID, outcome, and metadata | `backend/database/repositories/phase2.py` | 🟢 **LOW** |
| **Tool Execution Sandbox & RCE Prevention** | No `eval()`, `exec()`, or dynamic shell execution from user input; tools use fixed allowlists | `backend/services/deterministic_tool_registry.py`, `admin_assistant_tools.py` | 🟢 **LOW** |
| **Database Concurrency & WAL** | SQLite WAL mode enabled, 5,000ms busy timeout, automated daily backups with optional encryption | `backend/database/connection.py`, `config.py` | 🟢 **LOW** |
| **Candidate Training Isolation** | Candidate runs write exclusively to isolated subdirectories (`artifacts/candidates/phase60/`); never touch `models/active/` | `run_controlled_training_ws05.py`, `run_e3_experiments.py` | 🟢 **LOW** |
| **Production Promotion Barrier** | Code-level barrier: `candidate_traffic_share = 0.0`, maximum governance ceiling `INTERNAL_CANARY_QUALIFIED` | `core_model/release/phase44_runtime_governance.py` | 🟢 **LOW** (Strictly locked) |
| **Dataset Provenance & Air-Gap** | Cryptographic SHA-256 sealing of datasets; automated air-gap verification against Phase 53 held-out benchmark | `curate_and_seal_phase60_v001.py`, `dataset_expansion_validator.py` | 🟢 **LOW** |
| **Model Checkpoint Integrity** | Exact SHA-256 verification before model load; mismatch blocks inference runtime | `core_model/inference_runtime/model_loader.py` | 🟢 **LOW** |

---

## 2. Identified Security & Governance Risk Register

### A. High Risks (0 Identified)
- Zero critical or high security vulnerabilities identified in the active codebase. No arbitrary RCE vector, no SQL injection pathways (all database queries use parameterized SQL via SQLite adapters), and no unauthenticated mutation endpoints.

### B. Medium Risks (2 Identified)
1. **Risk M-01: Admin Roles Not Persisted in Database**
   - *Detail:* Admin accounts in `admin_accounts` table only carry an account lifecycle status (`active`, `disabled`, `locked`). The RBAC roles (`SUPER_ADMIN`, `AUDITOR`) are resolved via environment variable override (`BRUD_ADMIN_ROLE_OVERRIDES`).
   - *Impact:* An admin's role cannot be modified dynamically through the dashboard UI without updating server configuration or adding a database migration.
   - *Mitigation:* The system safely defaults to `AdminRole.ADMIN`, which has read and proposal rights, while high-risk execution still enforces two-person review.
2. **Risk M-02: Public Chat IP-Based Rate Limiting Behind Reverse Proxies**
   - *Detail:* Rate limiting relies on `request.client.host`. If deployed behind a reverse proxy (e.g. Nginx, Cloudflare) without trusted proxy header parsing (`X-Forwarded-For`), all clients could share a single rate-limit bucket.
   - *Impact:* Potential denial of service for legitimate users.
   - *Mitigation:* Ensure reverse proxy configuration explicitly configures forwarded IP middleware when deploying.

### C. Low Risks (1 Identified)
1. **Risk L-01: Local Model Memory Footprint During Concurrency**
   - *Detail:* The inference runtime enforces a 2 GB RAM guard. Under high concurrent query volume on CPU, multiple worker threads could compete for CPU memory if not bounded.
   - *Mitigation:* Public chat concurrency is bounded and sequentialized by worker settings.
