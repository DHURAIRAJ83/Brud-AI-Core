# Phase 17.6 — Temporal Integrity Report
**Brud Mini Brain: Temporal Knowledge & Chronological Progression**

## 1. Temporal Validity Rules
Consolidation preserves the chronological progression of system and user facts:
1. **Historical vs Current State Separation**: Point-in-time migration events (e.g. "Migrated to Ubuntu 24.04 in August") are not flattened into ambiguous operational statements.
2. **Validity Windows**: `valid_from` is initialized with the current UTC timestamp, and `expires_at` is preserved when present.
3. **Expired Record Exclusion**: Any record where `expires_at < now` or `freshness_state == 'EXPIRED'` is excluded from active consolidation clusters.

---

## 2. Procedural Sequence Protection
For `PROCEDURAL` category memories:
- Step ordering and sequence numbers (`step_index`, `sequence_number`) are explicitly checked.
- Different procedural steps (e.g., "Step 1: Run migration" vs "Step 2: Restart service") are never merged into a single composite instruction merely because of topic or lexical similarity.
