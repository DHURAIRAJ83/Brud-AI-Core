# Phase 17.9: Procedural Memory & Workflow Reasoning Specification

## 1. Objective
Specify how `TASK` and `PROCEDURAL` memory items are assembled into deterministic, ordered execution chains (Step 1 → Step 2 → Step 3).

---

## 2. Sequence Extraction & Topological Ordering
Procedural steps in dynamic memory items are ordered using:
1. **Explicit Step Numbering**: Parsing `step_index` or regex prefix patterns (e.g. `Step 1:`, `1.`, `Phase 1:`, `[Step 2]`).
2. **Temporal Order**: In the absence of explicit step numbers, creation epoch order ($t_1 < t_2 < t_3$) determines execution flow.
3. **Prerequisite Identification**: Lexical signals such as `requires`, `after`, `prerequisite:`, `depends on` establish directional dependency edges.

---

## 3. Workflow Chain Invariants
- **No Fabricated Intermediate Steps**: If Step 1 and Step 3 exist without Step 2, the reasoning engine must explicitly flag `missing_steps = [2]` rather than hallucinating an unobserved transition.
- **Cycle Detection**: Direct and indirect dependency cycles are caught via standard deterministic graph cycle checks; cycles trigger a `WorkflowCycleWarning` and fallback to topological timestamp ordering.
