# Phase 17.9: Temporal Reasoning Specification

## 1. Objective
Establish deterministic temporal reasoning over retrieved memories to answer:
- *"What was true then?"* (Historical truth)
- *"What is true now?"* (Current active truth)
- *"What changed and what replaced what?"* (State evolution / supersession)

---

## 2. Core Temporal Invariants (Phase 17.7 Preservation)
- **Freshness is NOT Truth Validity**: Stale or aging memories are not deemed false.
- **Historical Mode Invariance**: Historical retrieval preserves historical facts as valid context without decay penalty.
- **Supersession Order**: When memory $B$ supersedes memory $A$ ($t_B > t_A$), $B$ represents current active state while $A$ is retained as historical lineage.

---

## 3. Temporal State Classification Matrix

| Temporal State | Condition | Reasoning Interpretation | Downstream Context Rendering |
| :--- | :--- | :--- | :--- |
| `CURRENT_ACTIVE` | Status = `active`, not superseded | Ground truth for current system/user state | Directly cited as active fact |
| `HISTORICAL_VALID` | Status in (`active`, `consolidated`), older timestamp | Fact that held historically; remains true in past context | Annotated: `[Historical Context: observed at <timestamp>]` |
| `SUPERSEDED_PAST` | Status in (`expired`, `archived`), replaced by newer version | Past fact that has been explicitly replaced | Annotated: `[Superseded: replaced by <newer_id>]` |
| `TEMPORARY_EPISODIC`| Category = `EPISODIC`, short TTL | Transient observation valid only in specific temporal frame | Annotated: `[Transient State: valid until <ttl>]` |
