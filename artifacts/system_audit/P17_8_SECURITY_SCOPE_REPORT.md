# PHASE 17.8 — SECURITY & MULTI-TENANT SCOPE REPORT
# INVARIANT GOVERNANCE (G1–G14), ISOLATION & SANITIZATION

**Document ID**: `P17_8_SECURITY_SCOPE_REPORT`  
**Phase**: Phase 17.8 (Brud Mini Brain — Memory Recall & Retrieval Intelligence)  
**Status**: SPECIFICATION COMPLETE (STAGE A)  

---

## 1. Multi-Tenant Scope Isolation (G5)

Multi-tenant security is enforced at both the database query layer and domain ranking layer:

1. **Database Filtering**:
   - `MemoryService.retrieve()` executes `active_memory_items_for_participant(connection, participant_scope_key)`.
   - SQL queries are strictly parametrized by `WHERE participant_scope_key = ?`.

2. **Domain Layer Barrier**:
   - `MemoryRecallEngine.recall_memories()` re-validates each candidate's `participant_scope_key`.
   - If any candidate does not match the query's `participant_scope_key`, it is immediately dropped with `cross_participant_denied`.

3. **Multi-Scope Mutation / Leakage Prevention**:
   - Memory retrieval runs and results recorded in `memory_retrieval_runs` store the explicit `participant_scope_key` to maintain tenant audit boundaries.

---

## 2. G8 Secret Sanitization across Recall Output

1. **Query Scrubbing**:
   - All input queries are scrubbed via `sanitize_message()` before tokenization or vector embedding to prevent indexing raw secrets.
2. **Result Content Scrubbing**:
   - Retrieved display values and normalized values undergo sanitization before assembly into response context.
3. **Audit Log Scrubbing**:
   - Search queries stored in `memory_retrieval_runs` are hashed (`query_checksum_sha256 = hashlib.sha256(query).hexdigest()`) to prevent secret persistence in database logs.

---

## 3. G1 Governance & System Isolation

- **Elevated Approval Required**: SYSTEM and ADMIN memories cannot be returned to unprivileged participants unless explicitly configured in the active profile's `allowed_categories`.
- **Zero Autonomous Elevation**: Retrieval queries cannot promote or activate unconfirmed/quarantined SYSTEM or ADMIN memories.
- **Audit Logging**: Every recall run records `admin_id` / `actor_id` in audit logs (`_audit(connection, "memory_retrieval_executed", ...)`).
