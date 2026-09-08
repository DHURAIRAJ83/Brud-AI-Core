# Phase 17.6 — Conflict-Aware Consolidation Report
**Brud Mini Brain: Conflict Boundaries & Dispute Handling in Consolidation**

## 1. Conflict Boundaries & Consolidation Gating
Consolidation must never synthesize contradictory assertions into a single misleading statement.

### Strict Consolidation Gate Rules:
1. **Unresolved Disputes Block Consolidation**:
   - If memory $A$ or memory $B$ has an active dispute in state `DETECTED`, `PENDING_REVIEW`, or `UNDER_REVIEW`, neither item may be consolidated.
   - The consolidation engine filters out all disputed items before grouping candidates.

2. **Resolved Disputes Handling**:
   - **`SUPERSEDE_EXISTING`**: Only the new superseding memory is active and eligible for future consolidation. The superseded item is archived.
   - **`RETAIN_EXISTING`**: The candidate item is rejected. The authoritative original remains eligible.
   - **`RETAIN_BOTH_COEXIST`**: Both memories remain active as legitimate distinct claims with version or context qualifiers (e.g., "Version 1 port is 8080", "Version 2 port is 9090"). They are marked non-mergeable with each other.
   - **`DISMISS`**: Dispute was spurious; original memories continue under standard consolidation rules.

---

## 2. Prohibition of Fabricated Ranges & False Consensus
- **Anti-Pattern**:
  - Memory A: "Backup runs every 24 hours."
  - Memory B: "Backup runs every 12 hours."
  - Prohibited Output: "Backup runs every 12 to 24 hours." (Fabrication)
- **Required Behavior**:
  - Flagged as `TEMPORAL_CONFLICT` in Phase 17.5.
  - Excluded from consolidation clusters.
  - Awaits authorized human resolution.
