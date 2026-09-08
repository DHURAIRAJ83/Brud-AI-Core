# Phase 17.6 — Category-Specific Governance Report
**Brud Mini Brain: Category Governance Matrix & G1 Autonomy Boundaries**

## 1. Category-Specific Consolidation Matrix

| Memory Category | Auto-Consolidation Permitted? | Governance Requirements | Consolidation Strategy |
|:---|:---:|:---|:---|
| **`PREFERENCE`** | **YES** | Standard G5 scope + G8 sanitization | Consolidate repeated user preferences into canonical preference profile. |
| **`SEMANTIC`** | **YES** | Provenance preservation + evidence sum | Consolidate semantically equivalent facts into single canonical fact. |
| **`EPISODIC`** | **RESTRICTED** | Temporal window matching required | Group related conversational observations within same session/day. |
| **`PROCEDURAL`** | **RESTRICTED** | Step ordering preservation required | Maintain chronological step sequence; do not jumble steps. |
| **`TASK`** | **RESTRICTED** | Short TTL decay check | Consolidate task progress; expire completed temporary tasks. |
| **`SYSTEM`** | **NO (G1 Gate)** | **Explicit Human Admin Approval Required** | Proposals generated as draft; cannot modify system knowledge autonomously. |
| **`ADMIN`** | **NO (G1 Gate)** | **Explicit Human Admin Approval Required** | Proposals generated as draft; elevated audit trail required. |

---

## 2. G1 Autonomy Boundary Enforcement
Consolidation must remain an advisory optimization engine:
- Never bypass administrative review for elevated categories (`SYSTEM`, `ADMIN`).
- Never declare a disputed memory authoritative without user or admin confirmation.
- Never resolve disputes autonomously.
