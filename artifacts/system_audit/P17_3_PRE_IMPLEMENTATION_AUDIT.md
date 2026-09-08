# P17.3 Pre-Implementation Audit: Memory Intelligence

**Audit Date**: 2026-09-06  
**Auditor**: Antigravity AI Engineering Assistant  
**Target Scope**: Phase 17.3 — Memory Intelligence Layer  
**Baseline Status**: Phase 16 Production Go-Live Ready (163/163 Tests Passed, G1–G14 Active) + Phase 17.2 Context Intelligence (18/18 Tests Passed)

---

## 1. Existing Memory Architecture Inspection

| Component | File Path | Existing Capability | Classification |
|---|---|---|---|
| **Memory Service** | `backend/services/memory_service.py` | Consent validation, memory creation/update, SQLite WAL queries, cosine similarity embedding search. | `REUSE` / `EXTEND` |
| **Memory Repository** | `backend/database/repositories/conversation_memory.py` | CRUD operations on `conversation_memory_policies`, `memory_items`, `memory_item_versions`, `memory_embeddings`. | `REUSE` / `EXTEND` |
| **Database Schema** | `backend/database/schema.py` (`PHASE17_SCHEMA`) | Immutable triggers on versions/events, WAL mode, foreign keys to policies/sessions/turns. | `REUSE` / `EXTEND` |
| **Deduplication** | `core_model/conversation/memory_deduplication.py` | Exact string equality check and category/purpose collision check. | `REUSE` / `EXTEND` |
| **Ranking & Retrieval** | `core_model/conversation/memory_ranking.py`, `memory_retrieval.py` | Combined scoring with weights; access filtering by category and confidence. | `REUSE` / `EXTEND` |
| **Memory Intelligence** | `core_model/mini_brain/intelligence/memory_intelligence.py` | **MISSING**: 7-Category Taxonomy, Importance/Confidence/Freshness lifecycle, Reinforcement, Promotion/Demotion, Semantic Compression, Governance boundaries. | `NEW` |

---

## 2. Memory Taxonomy & Category Mapping

The 7 required Intelligence 2.0 memory categories map to legacy category sub-types without breaking backward compatibility:

| Intelligence 2.0 Category | Description | Legacy Sub-categories Mapped | Retention / TTL Policy | Governance Level |
|---|---|---|---|---|
| **`EPISODIC`** | Specific past interaction / event | `learning_goal`, `conversation_follow_up` | Short-to-Medium (7 days) | Standard Consent |
| **`SEMANTIC`** | Stable factual knowledge | `user_confirmed_fact`, `confirmed_name_or_alias` | Long (90 days) | User / Admin Confirmed |
| **`PROCEDURAL`** | Operational workflows & guidelines | `course_progress`, `format_preference` | Long (90 days) | Standard |
| **`TASK`** | Active or historical task state | `project_preference`, `conversation_follow_up` | Short (24 hours - 7 days) | Standard |
| **`PREFERENCE`** | User/Admin preferences (e.g. language, format) | `language_preference`, `format_preference` | Long (180 days) | User / Admin Confirmed |
| **`SYSTEM`** | Core system operational facts | `system_derived` | Permanent / Controlled | Admin Approval Required |
| **`ADMIN`** | Administrator-specific operational knowledge | `admin_created_for_test` | Long / Permanent | Elevated Governance |

---

## 3. Memory Lifecycle State Machine

```mermaid
flowchart TD
    Capture[1. CAPTURE & SANITIZE (G8)] --> Normalize[2. NORMALIZE (Text / Casing / Script)]
    Normalize --> Classify[3. CLASSIFY (7-Category Taxonomy)]
    Classify --> Score[4. SCORE (Importance 0-100 & Confidence 0-100)]
    Score --> DuplicateCheck{Duplicate / Reinforce?}
    DuplicateCheck -- Exact/Normalized Match --> Reinforce[5. REINFORCE (evidence_count += 1, update confidence)]
    DuplicateCheck -- New Fact --> Store[6. STORE (Active / Proposed / Quarantined)]
    Store --> AccessTracking[7. ACCESS TRACKING (access_count, last_accessed_at)]
    AccessTracking --> DecayCheck[8. DECAY & FRESHNESS (fresh -> aging -> stale -> expired)]
    DecayCheck --> CompressCheck{Compressible?}
    CompressCheck -- Yes --> Compress[9. COMPRESS (Canonical Representation + Provenance)]
    CompressCheck -- No --> ActiveRetain[Retain in Active State]
    DecayCheck -- Stale/Unused --> Demote[10. DEMOTE -> ARCHIVE]
    DecayCheck -- Expired --> Expire[11. EXPIRE / DELETE]
```

---

## 4. Governance, Security, and Storage Risk Assessment

1. **Governance for SYSTEM & ADMIN Categories**:
   - New observations in `SYSTEM` and `ADMIN` categories are marked as `proposed` / `awaiting_confirmation` and cannot become `active` without explicit administrative confirmation.
2. **Secret Redaction (G8)**:
   - Secret scrubbing (`message_sanitizer`) must be applied across raw input, normalized memory, compressed memory, and audit traces.
3. **Storage & Memory Explosion Prevention**:
   - Repeated facts increment `evidence_count` on the single canonical memory record rather than creating multiple database rows.
   - Bounded retrieval limits: `MAX_MEMORY_RESULTS = 10`, `MAX_MEMORY_TOKENS = 600`.
4. **Zero WAL Disruption**:
   - All persistence continues to use SQLite WAL mode with `PRAGMA synchronous = NORMAL`.
