# Phase 17.6 — Conflict Gate Report
**Brud Mini Brain: Conflict-Aware Consolidation & Dispute Protection**

## 1. Conflict Gate Execution & Rules
The Phase 17.6 Consolidation Engine directly integrates with the Phase 17.5 `ConflictKnowledgeEngine` and dispute state machine.

### Active Dispute Filtering:
Any candidate participating in an unresolved dispute in state:
- `DETECTED`
- `PENDING_REVIEW`
- `UNDER_REVIEW`

is strictly filtered out prior to clustering.

### Numerical & Parameter Contradiction Gate:
Before two statements with cosine similarity $\ge 0.75$ are merged, the engine checks for parameter and scalar contradictions using `DuplicateKnowledgeEngine.has_predicate_contradiction()` and `ConflictKnowledgeEngine.classify_contradiction()`.

If a numerical or temporal conflict exists (e.g., "Backup runs every 24 hours" vs "Backup runs every 12 hours"):
1. The candidates are flagged as conflicting.
2. Grouping is blocked.
3. No fabricated consensus ranges are created.
4. The records remain distinct and await supervised human resolution.

---

## 2. Resolved Dispute Handling
- **`SUPERSEDE_EXISTING`**: The older superseded memory is archived; only the new authorized memory is active and eligible for future consolidation.
- **`RETAIN_EXISTING`**: The rejected candidate memory is marked `rejected`; only the authoritative existing memory participates in consolidation.
- **`RETAIN_BOTH_COEXIST`**: Coexisting memories with differing parameters or scopes remain distinct and are not merged into a single composite claim.
- **`DISMISS`**: Erroneous dispute marks are cleared, allowing standard consolidation to resume.
