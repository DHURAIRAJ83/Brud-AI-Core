# Phase 17.9: Memory Relationship Audit

## 1. Objective
Audit the repository to determine whether Brud Mini Brain currently supports or lacks multi-memory relationship reasoning across candidates.

---

## 2. Relationship Type Inventory & Status Classification

| Relationship Type | Status in Repository | Existing Mechanism / Source | Phase 17.9 Requirement |
| :--- | :--- | :--- | :--- |
| **Same-Topic Memories** | **PARTIAL** | `ContextIntelligenceEngine` detects active topics; `MemoryRecallEngine` applies $\Delta_{\text{topic}}$. Cross-memory clustering is missing. | Implement deterministic intra-packet topic clustering. |
| **Same-Task Memories** | **PARTIAL** | `TASK` retrieval mode exists in `MemoryRecallEngine`; tasks filtered by category. | Implement task chain grouping across multiple steps. |
| **Same-Event Memories** | **PARTIAL** | Timestamp metadata exists in `created_at` / `memory_item_events`. | Implement temporal window clustering for co-occurring events. |
| **Temporal Sequences** | **PARTIAL** | Sequence order partially tested in P17.6 / P17.8; no explicit chain builder. | Implement topological step sequence sorting by step index / timestamp. |
| **Cause / Effect Signals** | **MISSING** | No causal link model exists in conversation memory. | Infer causal signals via causal lexical triggers (`because`, `leads to`, `caused by`) and temporal precedence. |
| **Prerequisite / Dependency** | **MISSING** | `workflow_graph.py` exists for Knowledge Core but is not integrated with dynamic conversation memory. | Adapt dependency detection for dynamic memory items. |
| **Supporting Evidence** | **PARTIAL** | `evidence_count` and canonical consolidation exist; multi-item evidence corroboration is unlinked. | Group corroborating memories into evidence clusters. |
| **Derived Conclusions** | **MISSING** | Memories treated as discrete observations. | Link parent observations to consolidated canonical conclusions. |
| **Preference Inheritance** | **MISSING** | Preferences retrieved as flat items. | Rank explicit user preferences over inferred / default preferences. |
| **Memory Supersession** | **EXISTS** | `MemoryLifecycleEngine` + `ConflictKnowledgeEngine` support `SUPERSEDE_EXISTING`. | Partition superseded historical items from current active state. |
| **Canonical-to-Source Lineage** | **EXISTS** | `memory_consolidator.py` tracks `source_references` and provenance. | Preserve and expose bidirectional canonical-source relationships. |
| **Contradiction Relationships** | **EXISTS** | `conflict_detector.py` identifies semantic and factual contradictions. | Partition conflicting items into segregated reasoning branches with advisory warnings. |

---

## 3. Structural Decision
- **Decision**: **Domain-Only Relationship Engine (Option B)**.
- **Justification**: No new database tables or migrations are needed. Relationships can be derived deterministically in-memory during recall planning using existing metadata (`display_value`, `category`, `purpose`, `created_at`, `current_version_id`, `compression_state`, `is_disputed`).
