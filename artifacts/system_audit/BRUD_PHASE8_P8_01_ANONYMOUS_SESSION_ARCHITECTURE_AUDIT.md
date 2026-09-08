# BRUD AI — PHASE 8: P8-01 ANONYMOUS SESSION ARCHITECTURE & CODEBASE AUDIT

**Document:** `BRUD_PHASE8_P8_01_ANONYMOUS_SESSION_ARCHITECTURE_AUDIT.md`  
**Phase:** P8-01 (Architecture, Codebase Audit & Anonymous Session Design)  
**Date:** 2026-09-08  
**Git Baseline:** `f2a608ed1c0f6bddd0277296eb32c3cfd8f78758` (`phase-5-performance-polish`)  
**Tags Verified:**  
- Phase 6 Baseline: `v1.0.0-phase6` (`a0284a90d67395df327001b3b4deb7aa779f0715`) — FROZEN & INTACT  
- Phase 7 Baseline: `v1.1.0-p7-02` (`6f804e83e42a0e10b309040d558447a8fe537714`) — FROZEN & INTACT  
**Status:** ✅ **AUDIT COMPLETE — HARD STOPPING FOR REVIEW**

---

## 1. Executive Summary

This audit establishes the technical blueprint for **Phase 8: Anonymous Public-Chat Sessions and Conversation Continuity**.

The objective of Phase 8 is to transition the Brud AI public chat experience from a transient, stateless embed into a production-grade web application featuring:
1. **Cryptographically Secure Anonymous Session Identity** (zero required user registration or PII collection).
2. **Conversation Continuity Across Browser Refreshes** (persisting active turns securely).
3. **Session Lifecycle Control** ("New Chat" / "Clear Chat" / Auto-expiry).
4. **Zero Inference/RAG Duplication** (reusing existing tested pipelines without alteration).
5. **Strict Admin Boundary Isolation** (zero leak of administrative access, tokens, or endpoints).
6. **Preparation for Single-Origin Deployment** (safe path from iframe embed to unified routing).

---

## 2. Existing Codebase & Architectural Inventory

### 2.1 Frontends (`apps/`)

| Frontend | Current Port | State Management | Current Chat Integration |
|---|---|---|---|
| `apps/website` | 5175 (dev), 5176 (e2e preview) | React Router v6, vanilla CSS | Embeds `apps/chatbot` via `<iframe>` at `/chat`. Has no direct API calls for chat. |
| `apps/chatbot` | 5173 (dev) | React local state (`useState`) | Calls `/api/chat` directly via Vite proxy. Holds messages and `conversationId` in volatile memory only. **Refreshes destroy conversation history.** |
| `apps/admin-dashboard` | 5174 (dev) | React state + admin cookie | Fully isolated under `/api/admin/*`. Uses cookie `brud_admin_session` + CSRF headers. |

### 2.2 Backend & API Routes (`backend/api/routes/`)

1. **`chat.py` (`POST /api/chat`):**
   - Public route, rate-limited via client IP (`check_rate_limit`).
   - Accepts `PublicChatRequest(message, conversation_id, language_override, memory_consent, client_request_id)`.
   - Delegates to `PublicChatRoutingService`.
   - **Gap:** No `GET` endpoint exists to retrieve past turns of a conversation. No ownership token is verified when passing `conversation_id`.
2. **`conversation_memory.py` (`/api/admin/conversation-memory/*`):**
   - Comprehensive multi-turn session and memory management API.
   - **Admin-only:** Protected by `require_admin` and `require_csrf`. Completely inaccessible to the public.
3. **`public_chat_runtime.py` (`/api/public/chat/sessions/*`):**
   - Mini Brain (MB-23) self-improvement feedback loop.
   - Stores only content hashes (SHA-256) of messages for improvement clustering; explicitly does NOT store raw message text. Not suitable for user conversation continuity.

### 2.3 Existing Database Structures (`data/database/brud_ai.db`)

An empirical scan of `brud_ai.db` revealed three distinct session mechanisms:

```
+---------------------------------------------------------------------------------------+
| 1. Phase 1 Legacy: chat_sessions & chat_messages                                     |
|    - Exists from initial schema.                                                      |
|    - Stores session_id, role, content, metadata_json.                                 |
|    - NOT connected to Phase 17 memory, RAG scope, or context budgeting.               |
+---------------------------------------------------------------------------------------+
| 2. Phase 17 Enterprise Memory: conversation_sessions & conversation_turns             |
|    - Rich, fully featured multi-turn architecture.                                    |
|    - Tables: conversation_sessions, conversation_turns, conversation_turn_events.     |
|    - Supports session_mode ('session_memory', 'private_no_persist', etc.).            |
|    - Already wired into PublicChatRoutingService.handle_message()!                     |
|    - ISSUE: Requires an active policy in conversation_memory_policies (currently 0).  |
|    - ISSUE: Lacks an ownership credential/token to prevent unauthorized turn reading. |
+---------------------------------------------------------------------------------------+
| 3. MB-23 Telemetry: mini_brain_public_chat_sessions & _messages                       |
|    - Hash-only storage for self-improvement clustering. Cannot restore user messages.  |
+---------------------------------------------------------------------------------------+
```

---

## 3. Core Architectural Decisions for Phase 8

### 3.1 Session Entity: Reuse vs. New Table
**Decision:** **Hybrid Reuse Model (Recommended)**
- **Do NOT create redundant message tables.** `conversation_turns` already has `session_id`, `sequence_number`, `role`, `stored_content`, `language_category`, and `content_checksum_sha256`.
- **Do NOT modify Phase 17 core tables.** `conversation_sessions` schema remains unmodified.
- **Additive Security Table (`anonymous_chat_sessions`):**
  Create a lightweight mapping table that links an anonymous client credential to a `conversation_sessions` row:
  ```sql
  CREATE TABLE IF NOT EXISTS anonymous_chat_sessions (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      public_id TEXT NOT NULL UNIQUE,                       -- Public session identifier (UUID4)
      conversation_session_public_id TEXT NOT NULL UNIQUE,  -- Phase 17 conversation_sessions.public_id
      session_token_hash TEXT NOT NULL,                     -- SHA-256 hash of high-entropy secret token
      client_ip_hash TEXT NOT NULL,                         -- Salted hash of client IP for anomaly detection
      status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'expired', 'closed')),
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      last_activity_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      expires_at TEXT NOT NULL,                             -- Enforced TTL (e.g. 24h rolling, 7d max)
      FOREIGN KEY (conversation_session_public_id) REFERENCES conversation_sessions(public_id) ON DELETE CASCADE
  );
  CREATE INDEX IF NOT EXISTS ix_anon_chat_sessions_token ON anonymous_chat_sessions(session_token_hash);
  CREATE INDEX IF NOT EXISTS ix_anon_chat_sessions_expires ON anonymous_chat_sessions(expires_at);
  ```

### 3.2 Authentication & Ownership Model
- **Token Generation:** When a session is initiated, the backend generates a cryptographically secure 256-bit token (`secrets.token_urlsafe(32)`).
- **Token Storage (Client):** Returned in response body and stored in browser `sessionStorage` (cleared when browser session ends) or optionally in `localStorage` if user opts into persistence.
- **Token Storage (Server):** Only the SHA-256 hash of the token (`session_token_hash`) is stored in SQLite. Plaintext tokens are NEVER persisted.
- **Authorization Header:** For all subsequent requests to `/api/chat/session/*`, the client supplies:
  `X-Session-Token: <token>`
- **No IDOR / Hijacking:** Even if someone knows or guesses `conversation_id`, they cannot read turns or append messages without providing the matching `X-Session-Token`.

### 3.3 Active Memory Policy Remediation
In `PublicChatRoutingService`:
```python
def _active_memory_policy_public_id(self) -> str | None:
    row = connection.execute(
        "SELECT public_id FROM conversation_memory_policies "
        "WHERE lifecycle_status='active' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return row["public_id"] if row else None
```
In `brud_ai.db`, all 64 memory policies have `lifecycle_status='draft'`.
**Remediation in P8-02:**
Add a migration / seed step that safely provisions a dedicated `public_chat_default_policy` with:
- `lifecycle_status='active'`
- `default_session_mode='session_memory'`
- `allow_short_term_context=True`
- `allow_session_summary=False`
- `allow_long_term_memory=False` (prevents cross-session user profiling)
- `maximum_session_turns=50`
- `maximum_session_age_seconds=86400` (24 hours)

---

## 4. Proposed Public API Design

All endpoints reside strictly under `/api/chat/` and require NO administrative privileges:

### 4.1 `POST /api/chat/session` (Initialize Anonymous Session)
- **Description:** Creates an anonymous session and returns the session credentials.
- **Request:**
  ```json
  {
    "language_preference": "auto"
  }
  ```
- **Response:**
  ```json
  {
    "conversation_id": "c7a8b9d0-...",
    "session_token": "brud_s_...",
    "expires_at": "2026-09-09T17:00:00Z",
    "turn_count": 0
  }
  ```

### 4.2 `GET /api/chat/session/{conversation_id}/messages` (Restore History)
- **Description:** Restores conversation turns after browser refresh.
- **Headers:** `X-Session-Token: <token>`
- **Security Check:** Server validates `SHA256(X-Session-Token) == session_token_hash` and `status == 'active'`. If invalid, returns `403 Forbidden` or `404 Not Found`.
- **Response:**
  ```json
  {
    "conversation_id": "c7a8b9d0-...",
    "messages": [
      {
        "id": "t-1",
        "role": "user",
        "content": "வணக்கம்",
        "created_at": "2026-09-08T17:01:00Z"
      },
      {
        "id": "t-2",
        "role": "assistant",
        "content": "வணக்கம்! நான் Brud AI...",
        "route_used": "core_model",
        "created_at": "2026-09-08T17:01:02Z"
      }
    ],
    "turn_count": 2,
    "expires_at": "2026-09-09T17:01:00Z"
  }
  ```

### 4.3 `POST /api/chat` (Send Message — Backward Compatible)
- **Enhancement:** When `X-Session-Token` is supplied with `conversation_id`, the session is verified and its `last_activity_at` and `expires_at` are bumped (sliding window).
- **Existing Fallback:** If called without session token (as today), it functions in transient mode (`private_no_persist`), maintaining 100% backward compatibility with all existing tests.

### 4.4 `POST /api/chat/session/{conversation_id}/clear` (Clear / Reset Chat)
- **Description:** Closes session and purges stored messages immediately.
- **Headers:** `X-Session-Token: <token>`
- **Action:**
  1. Sets `anonymous_chat_sessions.status = 'closed'`.
  2. Sets `conversation_sessions.status = 'closed'`.
  3. Updates `conversation_turns.stored_content = NULL` (immediate privacy zeroing).
- **Response:**
  ```json
  {
    "conversation_id": "c7a8b9d0-...",
    "status": "closed",
    "cleared": true
  }
  ```

---

## 5. Security, Privacy & Abuse Protection

### 5.1 Security Boundary Matrix

| Threat Vector | Mitigation | Status in Design |
|---|---|---|
| **Admin Privilege Leak** | Public chat code paths never import `backend.api.auth` or `require_admin`. | ✅ Enforced |
| **Insecure Direct Object Reference (IDOR)** | No conversation turn is readable without matching `session_token_hash`. | ✅ Enforced |
| **Session Fixation** | Session IDs are minted exclusively server-side via `uuid4()`. Client cannot propose arbitrary session keys. | ✅ Enforced |
| **Token Theft / XSS** | Tokens are ephemeral, scoped only to anonymous public chat, and contain no credentials or user identities. | ✅ Enforced |
| **Timing Attacks on Tokens** | Token comparison uses `hmac.compare_digest()`. | ✅ Enforced |
| **Denial of Service / Storage Bloat** | Hard limits: max 50 turns per session, max 4000 chars per message, 24-hour auto-expiration. | ✅ Enforced |

### 5.2 Rate Limiting Architecture
- **Layer 1 (Per IP):** In-memory sliding window: 60 requests / minute per client IP.
- **Layer 2 (Per Session):** 30 messages / minute per `conversation_id`.
- **Exceeding Limit:** Returns HTTP 429 (`CHAT_RATE_LIMITED`) with standard error structure.

### 5.3 Privacy & Data Retention Policy
- **No PII:** No names, emails, IPs, or device fingerprints are stored in clear text.
- **Opt-in / Ephemeral Context:** Only turns within the active session are stored. Long-term cross-session memory is disabled (`allow_long_term_memory=False`).
- **Data Cleanup:** Expired sessions (`expires_at < NOW()`) have their `stored_content` purged automatically by a background cleanup routine or periodic maintenance task.

---

## 6. Single-Origin & Frontend Integration Roadmap

```
+-----------------------------------------------------------------------------+
| CURRENT STATE (P7-02):                                                      |
|   Public Website (:5175) -> iframe -> Canonical Chatbot (:5173) -> :8000    |
+-----------------------------------------------------------------------------+
                                      │
                                      ▼
+-----------------------------------------------------------------------------+
| PHASE 8 STEP 1 (P8-02 / P8-03):                                             |
|   - Implement anonymous session backend API in backend/api/routes/chat.py.   |
|   - Update apps/chatbot state to persist token in sessionStorage.           |
|   - Add "New Chat" button and conversation history hydration on mount.      |
|   - Verify iframe still works seamlessly with session continuity.           |
+-----------------------------------------------------------------------------+
                                      │
                                      ▼
+-----------------------------------------------------------------------------+
| PHASE 8 STEP 2 (P8-04 / P8-05):                                             |
|   - Single-origin deployment configuration (reverse proxy / Vite multi-page)|
|   - Website /chat renders canonical chatbot components directly or shares   |
|     the exact same origin.                                                  |
|   - Deprecate and remove iframe wrapper cleanly without duplicate codebases.|
+-----------------------------------------------------------------------------+
```

---

## 7. Implementation Plan & Modified Files (for P8-02)

When authorized to begin P8-02, the following files will be modified or added (no changes made in P8-01):

1. **Database Migration:**
   - `backend/database/migrations.py` — Add migration for `anonymous_chat_sessions` table and seed default public memory policy.
   - `backend/database/schema.py` — Register `anonymous_chat_sessions` in qualification schema.
2. **Backend Services & Repositories:**
   - `backend/database/repositories/anonymous_chat_session.py` [NEW] — Repository for session tokens, activity tracking, and turn retrieval.
   - `backend/services/anonymous_chat_session_service.py` [NEW] — Service for token issuance, verification, turn listing, and purge.
   - `backend/api/routes/chat.py` [MODIFY] — Add `/api/chat/session`, `/api/chat/session/{id}/messages`, `/api/chat/session/{id}/clear`.
3. **Frontend (`apps/chatbot`):**
   - `apps/chatbot/src/services/api.js` [MODIFY] — Add `initSession()`, `getSessionMessages()`, `clearSession()`.
   - `apps/chatbot/src/pages/ChatPage.jsx` [MODIFY] — Load session from `sessionStorage`, restore history on refresh, add "New Chat" / "Clear Chat" action.
4. **Testing Suite:**
   - `tests/unit/test_anonymous_chat_session.py` [NEW] — Unit tests for token security, IDOR protection, expiration, and turn listing.
   - `apps/website/e2e/tests/` — E2E test covering page reload continuity and chat clear.

---

## 8. Verification & Gate Checks

- **Git Status:** Clean (`nothing to commit, working tree clean`)
- **P6 Baseline Tag:** `v1.0.0-phase6` intact (`a0284a90d6...`)
- **P7 Baseline Tag:** `v1.1.0-p7-02` intact (`6f804e83e4...`)
- **Audit Script Result:** 11/11 Checks Passed (see `p8_01_anonymous_session_architecture_report.json`)

> **GATE DECISION: ✅ P8-01 AUDIT PASSED**
>
> **HARD STOP.** All architectural investigations, schema evaluations, security models, and migration paths are documented.
> No application code, backend runtime, database tables, or test baselines were altered.
> **Awaiting explicit user authorization before starting P8-02 implementation.**
