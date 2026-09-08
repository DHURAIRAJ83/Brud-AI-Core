# Master Brud AI System Audit — 07: Memory System Audit

**Audit Date:** 2026-09-01  
**Auditor:** Principal AI Systems Architect  
**Confidence Rating:** HIGH CONFIDENCE (Verified by source code in `backend/services/memory_service.py` and `core_model/conversation/`)  

---

## 1. Memory Subsystem Matrix

| Memory Layer | Code Implementation | Responsible Modules | Storage Medium | Operational Status |
|---|---|---|---|---|
| **Short-term Context Memory** | Token-budgeted sliding window over current session turns | `core_model/conversation/context_budget.py` | In-memory / per-request | ✅ **OPERATIONAL** |
| **Conversation Memory (Sessions & Turns)** | Append-only session and turn records with language tagging | `backend/services/conversation_session_service.py` | SQLite (`conversation_turns`) | ✅ **OPERATIONAL** |
| **Conversation Summarizer** | Periodic windowed summary compression | `core_model/conversation/summary_builder.py` | SQLite (`conversation_summaries`) | ✅ **OPERATIONAL** (Rule-based) |
| **Long-term Declarative Memory** | Explicit key-value fact items with consent verification | `backend/services/memory_service.py` | SQLite (`memory_items`) | ✅ **OPERATIONAL** |
| **Episodic Memory** | Session event log and turn interaction traces | `backend/database/repositories/conversation_memory.py` | SQLite (`memory_events`) | ✅ **OPERATIONAL** |
| **Semantic Memory Retrieval** | 64-dim n-gram vector matching over memory items | `backend/services/memory_service.py` | SQLite BLOB + NumPy dot product | ✅ **OPERATIONAL** |
| **Memory Consent & Privacy** | Explicit user consent requirement (`ConsentCreate`) | `backend/services/memory_service.py` | SQLite (`memory_consents`) | ✅ **OPERATIONAL** |
| **Session & Tenant Isolation** | Scope key enforcement (`participant_scope`) | `backend/services/public_memory_scope_resolver.py` | SQLite foreign keys | ✅ **OPERATIONAL** |
| **Memory Forgetting / TTL / Revocation** | Explicit memory item deletion, revocation, and expiry | `backend/services/memory_service.py` | Soft & hard delete in SQLite | ✅ **OPERATIONAL** |

---

## 2. Actual Runtime Behavior vs Architectural Documentation

1. **Consent-Gated Long-Term Memory:**
   - In `backend/services/memory_service.py`, a long-term memory item can **never** become `active` unless an explicit `ConsentCreate` record exists for that participant and the item passes `assess_memory_safety()`.
   - If consent is revoked, future queries immediately filter out the item with zero cache lag.
2. **Short-Term Context Budgeting:**
   - `core_model/conversation/context_budget.py` allocates a maximum token ceiling across recent messages, system prompt, retrieved memory, and RAG chunks.
   - If the conversation exceeds the budget, older turns are evicted or compressed into summaries.
3. **Key Gap in Runtime Memory Execution:**
   - While the SQLite storage, consent, and retrieval systems are robustly implemented, **neural model context retention at 128 tokens is severely limited**.
   - In `CAP-08` evaluation ("My name is Kumar... What is my name?"), the small model weights fail to recall the name when the query is separated by conversational padding, even though the memory subsystem correctly retrieved the record.
