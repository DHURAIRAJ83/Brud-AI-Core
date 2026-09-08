# BRUD AI — SECURITY AUDIT (WS17)
**Audit Date:** 2026-09-07

---

## AUTHENTICATION

| Mechanism | Implementation | Status |
|-----------|----------------|--------|
| Session-based auth | `require_admin` dependency | ACTIVE |
| Session cookie | `admin_cookie_name` setting | ACTIVE |
| Session validation | `AdminRepository.validate_session()` | ACTIVE |
| Session invalidation on logout | `AdminRepository.invalidate_session()` | ACTIVE |
| Password hashing | bcrypt via `security.py` | ACTIVE |

---

## CSRF PROTECTION

| Mechanism | Implementation | Status |
|-----------|----------------|--------|
| CSRF token | Double-submit cookie | ACTIVE |
| CSRF validation | `require_csrf` dependency | ACTIVE |
| Applied to | All admin mutating endpoints (POST/PATCH/DELETE) | ACTIVE |
| CSRF DB validation | `AdminRepository.validate_csrf()` | ACTIVE |

---

## RATE LIMITING

| Mechanism | Implementation | Status |
|-----------|----------------|--------|
| Public chat rate limit | `check_rate_limit()` in chat.py | ACTIVE |
| Rate limit middleware | `RateLimitMiddleware` in core/rate_limit_middleware.py | ACTIVE |
| Config | `public_chat_rate_limit_max_requests`, `_window_seconds` | ACTIVE |
| Storage | In-memory sliding window | ACTIVE (no Redis) |

---

## SECURITY HEADERS

- `SecurityHeadersMiddleware` applied in `main.py`
- Headers: X-Content-Type-Options, X-Frame-Options, HSTS, CSP
- **Status:** ACTIVE

---

## INPUT VALIDATION

| Layer | Mechanism | Status |
|-------|-----------|--------|
| API Layer | Pydantic models (request validation) | ACTIVE |
| Core validation | `backend/core/validation.py` | ACTIVE |
| Input Safety | `evaluate_input_safety()` [public_chat/input_safety.py] | ACTIVE |
| Memory Safety | `assess_memory_safety()` [conversation/memory_safety.py] | ACTIVE |
| Injection Guard | `assess_context_item_injection()` [conversation/injection_guard.py] | ACTIVE |
| RAG Injection | `core_model/rag/injection_filter.py` | ACTIVE |

---

## OUTPUT VALIDATION

| Layer | Mechanism | Status |
|-------|-----------|--------|
| Output Safety | `evaluate_output_safety()` [public_chat/output_safety.py] | ACTIVE |
| RAG Grounding | `grounding_checks.py` | ACTIVE |
| Memory Recall Filter | `apply_access_filters()` | ACTIVE |

---

## AUTHORIZATION

| Resource | Mechanism | Status |
|----------|-----------|--------|
| Admin pages | `require_admin` dependency | ACTIVE |
| Mutating admin ops | `require_csrf` dependency | ACTIVE |
| Admin assistant actions | `BLOCKED_ACTION_SUBSTRINGS` + allowlist | ACTIVE |
| Memory access | Scope keys + consent | ACTIVE |
| RAG access | Access filter per scope | ACTIVE |
| Tool governance | `ToolAuthorizationError` + permissions | ACTIVE |

---

## AUDIT LOGGING

| Event | Repository | Status |
|-------|-----------|--------|
| Auth events | `AuditLogRepository` | ACTIVE |
| Proposal creation | `AuditLogRepository` | ACTIVE |
| Proposal execution | `AuditLogRepository` | ACTIVE |
| Chat events | `ChatOrchestrationRepository` | ACTIVE |
| Memory events | `ConversationMemoryRepository` | ACTIVE |
| Tool events | `DeterministicToolExecutionRepository` | ACTIVE |
| Mini Brain events | `MiniBrainLlmRuntimeRepository` | ACTIVE |

---

## SAFETY GATES IN EXECUTION PATHS

### Public Chat Safety Chain
1. Rate limit check
2. Input safety evaluation → REJECT if unsafe
3. Capability gate check
4. Route execution (controlled)
5. Output safety evaluation → REDACT if unsafe
6. Language policy enforcement

### Memory Safety Chain
1. Policy existence check
2. Consent verification
3. Category allowlist check
4. Purpose bounded check
5. Safety scan
6. Normalization

### Admin Assistant Safety Chain
1. Auth (require_admin)
2. CSRF (require_csrf)
3. Action allowlist (BLOCKED_ACTION_SUBSTRINGS)
4. Tool governance (ToolAuthorizationError)
5. Write governance (execute_with_governance)
6. Fingerprint staleness check (prevent stale execution)
7. Audit log

---

## SECURITY GAPS

| Gap | Severity | Notes |
|-----|----------|-------|
| In-memory rate limiter | MEDIUM | Lost on restart, not distributed |
| No RBAC beyond admin/non-admin | MEDIUM | All admins have same permissions |
| SQLite (no encryption at rest) | MEDIUM | Database file not encrypted |
| Provider API keys in SQLite | MEDIUM | Keys stored in application DB |
| No IP allowlist for admin | LOW | Any authenticated admin from any IP |
| No MFA | LOW | Single-factor session auth |

---

## FINDINGS

1. **COMPLETE:** Authentication, CSRF, rate limiting all active
2. **COMPLETE:** Input and output safety gates on all public chat paths
3. **COMPLETE:** Audit logging across all critical operations
4. **ACTIVE:** Injection guards at multiple layers (context, RAG, memory)
5. **GAP:** In-memory rate limiter lost on restart
6. **GAP:** No RBAC — all admins equal
7. **GAP:** Provider API keys in application SQLite DB

---
*WS17 Complete*
