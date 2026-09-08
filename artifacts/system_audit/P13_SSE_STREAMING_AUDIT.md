# P13 — SERVER-SENT EVENTS (SSE) STREAMING AUDIT
## Brud AI Mini Brain / Admin Assistant Runtime

**Date**: 2026-09-04  
**Scope**: SSE Streaming Architecture, Event Contract & Memory Invariant (P13.7–P13.16)  
**Status**: 🟢 VERIFIED & PRODUCTION READY

---

### 1. Objective

Provide low-latency progressive response streaming to the Admin Chat UI (`ChatPanel.jsx` / `AdminAssistantWidget.jsx`) via native SSE streaming while upholding G1–G6 invariants: canonical runtime separation, advisory governance, truthful RAG citations, fail-closed training gates, and single-turn memory persistence.

---

### 2. Streaming Endpoint & Security Specification

- **Route**: `POST /api/admin/mini-brain/llm-runtime/chat/stream`
- **Media Type**: `text/event-stream`
- **Security & RBAC**:
  - `require_admin`: Hard dependency checking admin session cookie and active user identity.
  - `CsrfDependency`: Requires valid CSRF header and session token match (`X-CSRF-Token`).
  - Rate limiting & Pilot metrics: Integrated with global security middlewares.
- **Backpressure & Disconnect Handling**:
  - Generator evaluates `await request.is_disconnected()` prior to each event emission.
  - Immediate loop termination on client abort, releasing SQLite connection handles and background adapter tasks.

---

### 3. SSE Event Contract

The streaming protocol adheres to standard SSE framing (`event: <type>\ndata: <json>\n\n`):

1. **`start`**:
   ```json
   { "event": "start", "data": { "session_id": "...", "admin_id": "..." } }
   ```
2. **`metadata`**:
   ```json
   { "event": "metadata", "data": { "model": "...", "backend_type": "...", "citations": [...] } }
   ```
3. **`token`**:
   ```json
   { "event": "token", "data": { "text": "progressive token chunk" } }
   ```
4. **`done`**:
   ```json
   { "event": "done", "data": { "session_id": "...", "message_id": "...", "total_tokens": 42, "error": null } }
   ```
5. **`error`**:
   ```json
   { "event": "error", "data": { "code": "...", "message": "...", "retryable": false } }
   ```

---

### 4. Memory Persistence Invariant

- **Rule**: Tokens must never be individually written to SQLite database rows.
- **Execution**:
  - Incoming tokens are buffered in an in-memory list (`token_buffer: list[str]`).
  - Upon generation completion (`done` event), the full buffer is assembled into the complete assistant reply.
  - The assembled text is scrubbed via `redact_secrets()`, sanitized for length and formatting, and passed to `_persist_turn`.
  - Exactly ONE assistant message is committed to `mini_brain_llm_messages` and indexed in `mini_brain_llm_memory`.

---

### 5. Truthful RAG & Governance Grounding

- **RAG Citations**: When grounded chat is requested, citations are retrieved first and emitted in the `metadata` event. If zero documents match or no RAG profile is configured, `citations: []` is emitted. The model cannot claim citations it did not retrieve.
- **Advisory Governance**: Intent to perform administrative mutations ("restart server", "delete dataset", "train model") triggers `_maybe_propose_governed_action()`, generating an advisory proposal without model inference or autonomous tool execution.

---

### 6. Frontend Streaming Integration (Zero UI Redesign)

- Updated `apps/admin-dashboard/src/services/api.js` with `lrChatStream()`.
- Updated `ChatPanel.jsx`:
  - Maintains existing styling, cards, controls, and responsive layout.
  - Dispatches message with streaming placeholder.
  - Dynamically appends incoming tokens to active assistant bubble.
  - Renders citation cards seamlessly from metadata event.
  - Transparent fallback to `lrChat` in case of streaming failure or network disconnect.

---

### 7. Test Evidence

Validated in `tests/e2e/test_p13_sse_streaming.py`:
- `P13-SSE-001`: Authorized streaming request succeeds (PASS)
- `P13-SSE-002`: Unauthorized request rejected (PASS)
- `P13-SSE-003`: Missing CSRF rejected (PASS)
- `P13-SSE-004` to `007`: Full event lifecycle (`start` -> `metadata` -> `token` -> `done`) (PASS)
- `P13-SSE-008`: Structured error handling (PASS)
- `P13-SSE-009`: No Python stack trace leakage (PASS)
- `P13-SSE-012`: Final assistant message persisted exactly once (PASS)
- `P13-SSE-013`: Secrets scrubbed from stream (PASS)
- `P13-SSE-014`: RAG citations remain truthful (PASS)
- `P13-SSE-015`: Governance requests remain advisory (PASS)
- `P13-SSE-016`: Training requests remain blocked (PASS)
- `P13-SSE-017`: Non-streaming `/chat` remains functional (PASS)
