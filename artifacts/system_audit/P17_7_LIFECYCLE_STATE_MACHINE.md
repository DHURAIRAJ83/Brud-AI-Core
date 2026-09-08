# Phase 17.7 — Lifecycle State Machine Specification
**Brud Mini Brain: Formal State Transitions, Triggers & Invariants**

## 1. Dual-Dimension State Model
The Brud Mini Brain memory subsystem operates across two complementary state dimensions:
1. **Freshness State (`FreshnessState`)**: Dynamic, time-dependent decay dimension (`FRESH`, `AGING`, `STALE`, `EXPIRED`).
2. **Item Lifecycle Status (`memory_items.status`)**: Authoritative governance/operational status (`proposed`, `awaiting_confirmation`, `active`, `consolidated`, `superseded`, `expired`, `archived`, `rejected`, `revoked`, `deleted`).

```
                              [ PROPOSED / AWAITING_CONFIRMATION ]
                                                │
                                                ▼ (Admin Confirm / User Explicit)
                                        ┌───────────────┐
                     ┌──────────────────►   ACTIVE      ◄───────────────────┐
                     │                  └───────┬───────┘                   │
                     │ (Reactivate)             │ (Consolidate 17.6)        │ (Unconsolidate 17.6)
                     │                          ▼                           │
                     │                  ┌───────────────┐                   │
                     │                  │ CONSOLIDATED  ├───────────────────┘
                     │                  └───────┬───────┘
                     │                          │ (Supersede)
                     │                          ▼
                     │                  ┌───────────────┐
                     │                  │  SUPERSEDED   │
                     │                  └───────────────┘
                     │                          │ (Archive / Discard)
                     │                          ▼
                     │                  ┌───────────────┐
                     └──────────────────┤   ARCHIVED    │
                                        └───────────────┘
                                                ▲
                                                │ (Age >= TTL)
                                        ┌───────┴───────┐
                                        │    EXPIRED    │
                                        └───────────────┘
```

---

## 2. Freshness State Machine

```
   ┌───────────┐         Age >= 0.25 TTL         ┌───────────┐
   │   FRESH   ├────────────────────────────────►│   AGING   │
   └─────▲─────┘                                 └─────┬─────┘
         │                                             │ Age >= 0.75 TTL
         │                                             ▼
         │       Reinforced Observation          ┌───────────┐
         └───────────────────────────────────────┤   STALE   │
         │                                       └─────┬─────┘
         │                                             │ Age >= 1.0 TTL
         │       Reactivated (Admin Auth)              ▼
         └───────────────────────────────────────┌───────────┐
                                                 │  EXPIRED  │
                                                 └───────────┘
```

---

## 3. Transition Matrix & Guard Conditions

| Source State | Target State | Trigger / Event | Guard Conditions | Actions / Emitted Event |
|:---|:---|:---|:---|:---|
| `FRESH` | `AGING` | Time progression ($\text{Age} \ge 0.25 \times \text{TTL}$) | Category is decay-eligible | Emits `MEMORY_FRESHNESS_CHANGED` (freshness: AGING) |
| `AGING` | `STALE` | Time progression ($\text{Age} \ge 0.75 \times \text{TTL}$) | Not reinforced; no recent confirmation | Emits `MEMORY_FRESHNESS_CHANGED` (freshness: STALE) |
| `STALE` | `EXPIRED` | Time progression ($\text{Age} \ge 1.0 \times \text{TTL}$) | Not SYSTEM/ADMIN; no active dispute | Updates `status = 'expired'`, emits `MEMORY_EXPIRED` |
| `AGING` / `STALE` | `FRESH` | Verified observation / explicit confirmation | Passes duplicate/conflict validation | Updates `last_accessed_at`, resets freshness, emits `MEMORY_REINFORCED` |
| `EXPIRED` | `ARCHIVED` | Archival sweep / admin action | $\text{Age} \ge 1.5 \times \text{TTL}$ or `status == 'expired'` | Updates `status = 'archived'`, emits `MEMORY_ARCHIVED` |
| `ARCHIVED` | `ACTIVE` | Explicit admin reactivation | Admin authorization; scope intact | Updates `status = 'active'`, emits `MEMORY_REACTIVATED` |
| `ACTIVE` | `CONSOLIDATED` | Phase 17.6 Consolidation Pass | Part of eligible cluster; canonical formed | Updates `status = 'consolidated'`, emits `MEMORY_CONSOLIDATED` |
| `CONSOLIDATED` | `ACTIVE` | Phase 17.6 Unconsolidation Pass | Canonical superseded by admin | Updates `status = 'active'`, emits `UNCONSOLIDATED` |
| `ACTIVE` | `SUPERSEDED` | Phase 17.5 Dispute Resolution | `SUPERSEDE_EXISTING` strategy applied | Updates `status = 'superseded'`, emits `MEMORY_SUPERSEDED` |
