# Phase 17.5 — Dispute Lifecycle & State Machine Report

## 1. Dispute State Machine
Phase 17.5 implements an explicit, deterministic 5-state lifecycle for all memory disputes:

```
    ┌──────────┐
    │ DETECTED │
    └────┬─────┘
         │ (Automatic upon conflict discovery)
         ▼
 ┌────────────────┐
 │ PENDING_REVIEW │ ◄──────┐
 └───────┬────────┘        │
         │                 │ (Explicit admin action)
         ▼                 │
  ┌──────────────┐         │
  │ UNDER_REVIEW ├─────────┘
  └───┬──────┬───┘
      │      │
      │      │ (Explicit supervised resolution)
      │      ▼
      │  ┌───────────┐
      │  │ RESOLVED  │ (Terminal)
      │  └───────────┘
      │
      │ (Explicit supervised dismissal)
      ▼
 ┌───────────┐
 │ DISMISSED │ (Terminal)
 └───────────┘
```

---

## 2. Valid and Invalid State Transitions

| From State | To State | Allowed? | Transition Mechanism |
|:---|:---|:---:|:---|
| `DETECTED` | `PENDING_REVIEW` | YES | Automated transition upon dispute record creation |
| `DETECTED` | `DISMISSED` | YES | Early administrative dismissal |
| `PENDING_REVIEW` | `UNDER_REVIEW` | YES | Admin marks dispute as actively being inspected |
| `PENDING_REVIEW` | `RESOLVED` | YES | Admin applies resolution strategy directly |
| `PENDING_REVIEW` | `DISMISSED` | YES | Admin dismisses spurious dispute |
| `UNDER_REVIEW` | `RESOLVED` | YES | Admin completes review and resolves |
| `UNDER_REVIEW` | `DISMISSED` | YES | Admin concludes dispute was non-applicable |
| `UNDER_REVIEW` | `PENDING_REVIEW` | YES | Admin returns dispute to queue |
| **`DETECTED`** | **`RESOLVED`** | **NO** | **Forbidden**: Automatic jump to resolved without human action violates G1 |
| **`RESOLVED`** | **Any** | **NO** | **Forbidden**: Terminal state; immutable audit ledger |
| **`DISMISSED`** | **Any** | **NO** | **Forbidden**: Terminal state |

---

## 3. Supervised Resolution Strategies

1. **`SUPERSEDE_EXISTING`**:
   - Authorized actor explicitly determines that the new candidate memory supersedes the existing memory.
   - Existing memory transitions to `status = 'superseded'`.
   - Candidate memory transitions to `status = 'active'`.
   - Emits immutable `MEMORY_SUPERSEDED` and `DISPUTE_RESOLVED` events.

2. **`RETAIN_EXISTING`**:
   - Authorized actor explicitly determines that existing memory remains authoritative.
   - Existing memory remains `status = 'active'`.
   - Candidate memory transitions to `status = 'rejected'`.
   - Emits immutable `DISPUTE_RESOLVED` event.

3. **`RETAIN_BOTH_COEXIST`**:
   - Authorized actor explicitly determines that both memories are valid (contextual, version-specific, or legitimate multi-variant facts).
   - Existing memory remains `status = 'active'`.
   - Candidate memory transitions to `status = 'active'`.
   - Emits immutable `CONFLICT_COEXISTENCE_CONFIRMED` and `DISPUTE_RESOLVED` events.

4. **`DISMISS`**:
   - Authorized actor determines the conflict was false positive or inapplicable.
   - Candidate is rejected; existing remains untouched.
   - Emits immutable `DISPUTE_DISMISSED` event.
