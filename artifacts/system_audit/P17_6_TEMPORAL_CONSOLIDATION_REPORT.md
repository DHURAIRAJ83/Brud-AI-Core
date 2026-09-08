# Phase 17.6 — Temporal Consolidation Report
**Brud Mini Brain: Temporal Knowledge Representation & Chronological Integrity**

## 1. Temporal Knowledge Taxonomy
Temporal facts describe either:
1. **Point-in-time historical events** (e.g., "Migrated to Python 3.12 in August 2026").
2. **Current operational state** (e.g., "Active Python version is 3.12").
3. **Recurring schedules** (e.g., "Nightly backup runs at 02:00 UTC").

---

## 2. Preventing Historical Flattening
Consolidation must not erase the progression of system state over time.

### Temporal Rules:
1. **Historical vs Current State**:
   - Sequential events with explicit timestamps are linked into a chronological version chain, not flattened into an ambiguous composite.
2. **Interval Consistency**:
   - Memories asserting different execution schedules for the same system component are treated as temporal contradictions unless conditioned on distinct operational environments (e.g., staging vs production).
3. **Validity Windows**:
   - `memory_items.valid_from` and `memory_items.expires_at` define the validity lifespan of the canonical record.
4. **Time-Aware Retention**:
   - Expired memories are excluded from active consolidation clusters.
