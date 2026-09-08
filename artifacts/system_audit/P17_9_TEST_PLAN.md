# Phase 17.9: Test Plan Specification

## 1. Test Suite Overview
- **Target File**: `tests/e2e/test_p17_9_memory_reasoning.py`
- **Minimum Target Scenarios**: 35 Scenarios (`P17_9-001` through `P17_9-035`)
- **Regression Target**: Zero regressions across Phase 17.2–17.8 and full E2E historical suite.

---

## 2. Test Scenario Matrix

| Scenario Range | Requirement Category | Key Verification Items |
| :--- | :--- | :--- |
| `P17_9-001` → `P17_9-005` | Multi-Memory Relationship Detection | Pairwise similarity, topic alignment, temporal co-occurrence, and edge weights. |
| `P17_9-006` → `P17_9-010` | Evidence Aggregation & Corroboration | Clustering corroborating items, aggregate confidence bounding, source diversity weighting. |
| `P17_9-011` → `P17_9-014` | Temporal Reasoning & State Partitioning | Current vs historical facts, supersession tracking, TTL / episodic decay handling. |
| `P17_9-015` → `P17_9-018` | Contradiction & Dispute Safety | Epistemic 5-way partitioning, `exclude_conflicting` vs `prefer_recent` advisory warnings. |
| `P17_9-019` → `P17_9-022` | Procedural Sequence Assembly | Step index parsing, topological execution ordering, cycle detection, missing step flags. |
| `P17_9-023` → `P17_9-025` | Preference Consistency Reasoning | Explicit vs inferred precedence, scope hierarchy, anti-inflation verification. |
| `P17_9-026` → `P17_9-029` | Reasoning Packet Assembly & Bounding | Coherence score $[0.0, 100.0]$, token budgeting, `.to_context_block()` formatting. |
| `P17_9-030` → `P17_9-033` | Security & Governance Gates | G1 system/admin protection, G5 tenant isolation, G8 secret redaction, G4 anti-inflation. |
| `P17_9-034` → `P17_9-035` | Performance & Historical Regression | CPU latency benchmark ($< 3\text{ ms}$), zero regressions on Phase 17.2–17.8. |
