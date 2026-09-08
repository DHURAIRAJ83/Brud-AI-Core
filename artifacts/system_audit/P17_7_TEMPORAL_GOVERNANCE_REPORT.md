# Phase 17.7 — Temporal Governance & Category Matrix
**Brud Mini Brain: Category Lifecycle Governance & Historical Integrity**

## 1. 7-Category Lifecycle Governance Matrix

| Memory Category | Base TTL | Freshness Decay? | Expiration Behavior | Archival Policy | Reinforcement Policy | Auto-Transition? | Human Approval Required? |
|:---|:---:|:---:|:---|:---|:---|:---:|:---:|
| **`TASK`** | 1 day (86.4k s) | Fast Decay | Soft-expire after TTL; excluded from active tasks | Auto-archived after 2 days | Yes, if task re-confirmed | **YES** | No |
| **`EPISODIC`** | 7 days (604.8k s) | Moderate Decay | Aging after 2d; stale after 5d; expire after 7d | Auto-archived after 14 days | Yes, if topic re-visited | **YES** | No |
| **`PROCEDURAL`** | 30 days (2.59M s) | Slow Decay | Preserve step order; stale after 22d | Manual review before archive | Yes, on workflow execution | **YES** | No |
| **`SEMANTIC`** | 90 days (7.78M s) | Very Slow Decay | Remains valid unless contradicted | Long-term archival | Yes, on repeat observation | **YES** | No |
| **`PREFERENCE`** | 180 days (15.55M s) | Ultra Slow Decay | Remains active across long sessions | Retained in preference profile | Yes, on user setting touch | **YES** | No |
| **`SYSTEM`** | 365 days (31.54M s) | **DISABLED** | **NO AUTO-EXPIRATION** | **NO AUTO-ARCHIVAL** | Admin confirmation only | **NO (G1 Gate)** | **EXPLICIT ADMIN APPROVAL REQUIRED** |
| **`ADMIN`** | 365 days (31.54M s) | **DISABLED** | **NO AUTO-EXPIRATION** | **NO AUTO-ARCHIVAL** | Admin confirmation only | **NO (G1 Gate)** | **EXPLICIT ADMIN APPROVAL REQUIRED** |

---

## 2. Temporal Timestamp Semantics & Integrity
All temporal comparisons use normalized UTC timestamps (`YYYY-MM-DD HH:MM:SS`):
- `created_at`: Immutable creation timestamp (system clock UTC).
- `updated_at`: Last state or version modification timestamp.
- `valid_from`: Explicit start of semantic validity (defaults to `created_at`).
- `expires_at`: Explicit expiration boundary (null for permanent knowledge).
- `last_accessed_at`: UTC timestamp of most recent retrieval or reinforcement touch.

### Clock-Skew & Historical Facts Policy:
1. **Clock Skew Tolerance**: Timestamps within $\pm 60\text{ seconds}$ are treated as concurrent.
2. **Historical Fact Permanence**: Point-in-time observations (e.g. "Migrated database on 2026-08-15") remain historically valid forever; they are flagged with `valid_from` and are NOT auto-deleted or marked false merely due to age.
