# Phase 17.7 — Memory Lifecycle & Freshness Specification
**Brud Mini Brain: Architecture Specification & Capability Mapping**

## 1. Executive Summary & Problem Definition
Phase 17.7 formally specifies the **Memory Lifecycle, Freshness, Decay, Reinforcement, Expiration, and Archival** subsystem for the Brud Mini Brain runtime.

Following the certified foundations of Context Intelligence (17.2), Memory Intelligence (17.3), Duplicate Knowledge Detection (17.4), Conflict Detection & Disputes (17.5), and Memory Consolidation (17.6), Phase 17.7 solves the critical challenge of dynamic temporal knowledge management:
1. **Freshness Assessment**: Deterministically classifying memory state as `FRESH`, `AGING`, `STALE`, or `EXPIRED`.
2. **Deterministic Decay**: Applying mathematical, bounded, CPU-first decay over time without LLM hallucinations.
3. **Evidence-Safe Reinforcement**: Boosting confidence and resetting freshness upon verified repeated observations without inflating evidence counts.
4. **Non-Destructive Expiration & Archival**: Transitioning memories to `expired` or `archived` statuses while preserving 100% of underlying historical records, versions, and audit logs.
5. **Consolidation & Dispute Integration**: Ensuring canonical records inherit constituent lifecycle dynamics and dispute records remain protected against silent expiration.
6. **Strict Category Governance**: Enforcing G1 human-in-the-loop authorization gates for `SYSTEM` and `ADMIN` memories.

---

## 2. Existing Repository Audit: Existing vs Missing vs Proposed

| Dimension / Component | Status | Codebase Evidence & Evaluation |
|:---|:---:|:---|
| `FreshnessState` Enum | **EXISTS** | `FRESH`, `AGING`, `STALE`, `EXPIRED` defined in `core_model.mini_brain.intelligence.memory_intelligence`. |
| Category TTL Constants | **EXISTS** | `CATEGORY_TTL_SECONDS` in `memory_intelligence.py` (TASK: 1d, EPISODIC: 7d, PROCEDURAL: 30d, SEMANTIC: 90d, PREFERENCE: 180d, SYSTEM/ADMIN: 365d). |
| `MemoryLifecycleState` Enum | **EXISTS** | `PROPOSED`, `REVIEW_REQUIRED`, `ACTIVE`, `ARCHIVED`, `EXPIRED`, `SUPERSEDED`, `QUARANTINED` in `memory_intelligence.py`. |
| Database Item Statuses | **EXISTS** | `memory_items.status` column in SQLite supports `proposed`, `awaiting_confirmation`, `active`, `consolidated`, `superseded`, `expired`, `archived`, `rejected`, `revoked`, `deleted`. |
| Decay Function | **PARTIAL** | Basic step-function thresholding in `evaluate_freshness()`; continuous mathematical decay curve is **MISSING**. |
| Dynamic Freshness Evaluation Service | **MISSING** | `MemoryService` currently relies on static `valid_from`/`expires_at` without on-demand freshness re-evaluation or batch lifecycle transitions. |
| Memory Archival Endpoint | **MISSING** | No dedicated `archive_memory()` or `reactivate_memory()` service methods in `MemoryService`. |
| Consolidated Freshness Inheritance | **MISSING** | Canonical records do not yet dynamically track constituent freshness decay. |
| Dynamic Reinforcement Endpoint | **PARTIAL** | Reinforced event recording exists in proposal deduplication; on-demand reinforcement API is **PROPOSED**. |
| Immutable Lifecycle Events | **PARTIAL** | `reinforced`, `expired`, `deleted` exist; `MEMORY_FRESHNESS_EVALUATED`, `MEMORY_ARCHIVED`, `MEMORY_REACTIVATED` are **PROPOSED**. |

---

## 3. Core Architectural Principles
1. **Never Equate Expired/Archived with Deleted**: In Brud Mini Brain, knowledge is never destructively wiped. Expiration and archival are non-destructive lifecycle states.
2. **Strict Metric Separation**:
   - **Confidence**: Truth certainty / verification quality $[0.0, 100.0]$.
   - **Importance**: Domain utility / operational priority $[0.0, 100.0]$.
   - **Freshness**: Chronological recency and validity state (`FRESH`, `AGING`, `STALE`, `EXPIRED`).
   - **Evidence Count**: Number of distinct verified observations ($N \ge 1$).
   - **Access Frequency**: Retrieval usage metrics (`UNUSED`, `RARELY_USED`, `OCCASIONALLY_USED`, `FREQUENTLY_USED`).
3. **Retrieval != Evidence**: Merely querying a memory increases `access_count` but MUST NEVER increment `evidence_count`.
4. **G1 Autonomy Invariant**: `SYSTEM` and `ADMIN` memories must never be autonomously degraded, expired, or archived without explicit administrative review.
