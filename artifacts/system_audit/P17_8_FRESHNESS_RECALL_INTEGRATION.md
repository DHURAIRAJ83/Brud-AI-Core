# PHASE 17.8 — FRESHNESS RECALL INTEGRATION
# TEMPORAL DECAY, PENALTIES & TRUTH VALIDITY

**Document ID**: `P17_8_FRESHNESS_RECALL_INTEGRATION`  
**Phase**: Phase 17.8 (Brud Mini Brain — Memory Recall & Retrieval Intelligence)  
**Status**: SPECIFICATION COMPLETE (STAGE A)  

---

## 1. Architectural Principle: Freshness $\neq$ Truth Validity

A fundamental invariant of Brud Mini Brain is that **temporal age does not equate to factual falsity**:

- A preference like *"User prefers Dark Mode and Python 3.12"* that has not been accessed in 150 days is `STALE`, but remains **100% true**.
- A historical fact like *"Production migrated to Ubuntu 24.04 in August 2024"* is old, but remains **permanently historically true**.
- An operational task like *"Deploy Canary build #104"* from 3 days ago is `EXPIRED` and should not pollute active conversation.

---

## 2. Category-Specific Recall Policy

| Category | TTL (s) | Decay Speed | Freshness Ranking Impact | Live Conversation Behavior (`CURRENT`) | Retrospective Behavior (`HISTORICAL`) |
|---|---|---|---|---|---|
| **TASK** | 86,400 (1d) | Fast | Heavy penalty if aged; EXPIRED excluded. | Excluded after 1 day to prevent stale command confusion. | Retrievable for audit log. |
| **EPISODIC** | 604,800 (7d) | Moderate | Standard decay penalty (0/5/15/40). | Ranked lower as it ages; recent episodes prioritized. | Retrievable for session history. |
| **PROCEDURAL** | 2,592,000 (30d) | Slow | Mild decay penalty; sequence preserved. | Active procedures retained. | Retrievable with sequence intact. |
| **SEMANTIC** | 7,776,000 (90d) | Very Slow | Minimal decay; factual weight preserved. | Retained unless superseded. | Retrievable with full factual confidence. |
| **PREFERENCE** | 15,552,000 (180d) | Ultra-Slow | Minimal decay; user defaults preserved. | Retained across long intervals. | Retrievable for preference history. |
| **SYSTEM** | 31,536,000 (365d) | None | Zero autonomous decay (G1 locked). | Always FRESH unless admin modified. | Full administrative traceability. |
| **ADMIN** | 31,536,000 (365d) | None | Zero autonomous decay (G1 locked). | Always FRESH unless admin modified. | Full administrative traceability. |

---

## 3. Freshness Penalty Application in Ranking

```python
# In CURRENT mode:
if freshness_state == FreshnessState.FRESH:
    freshness_penalty = 0.0
elif freshness_state == FreshnessState.AGING:
    freshness_penalty = 5.0
elif freshness_state == FreshnessState.STALE:
    freshness_penalty = 15.0
elif freshness_state == FreshnessState.EXPIRED:
    freshness_penalty = 40.0

# In HISTORICAL mode:
freshness_penalty = 0.0  # Freshness does not penalize historical retrospective recall
```

---

## 4. Anti-Inflation Protection During Retrieval (G4)

- **Retrieval Access Is NOT Evidence**: Executing a memory recall query NEVER increments `evidence_count` and NEVER inflates `confidence_score`.
- **Read Access Metric**: Read events increment only `access_count` and update `last_accessed_at`, without altering core confidence or triggering fake reinforcement.
