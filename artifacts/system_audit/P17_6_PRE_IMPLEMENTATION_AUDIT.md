# Phase 17.6 — Pre-Implementation Architecture Audit
**Brud Mini Brain: Memory Consolidation & Knowledge Compression (Stage A Audit)**

## 1. Executive Summary
Phase 17.6 Stage A examines the architectural feasibility of introducing deterministic **Memory Consolidation & Knowledge Compression** into the Brud Mini Brain runtime.

The purpose of Phase 17.6 is to synthesize multiple related episodic or semantic memory observations into compact, canonical knowledge records while strictly preserving 100% of underlying provenance, evidence counts, temporal boundaries, conflict dispute records, and immutable audit history.

### Core Architectural Finding
The current repository already provides:
1. **Structural Provenance-Linked Compression Hook**: `MemoryIntelligenceEngine.compress_observations()` in [memory_intelligence.py](file:///home/dhurai/Projects/brud-ai/core_model/mini_brain/intelligence/memory_intelligence.py).
2. **Deterministic Canonical Selection**: Multi-tier ordering rules in `DuplicateKnowledgeEngine.select_canonical_memory()` in [duplicate_detector.py](file:///home/dhurai/Projects/brud-ai/core_model/mini_brain/intelligence/duplicate_detector.py).
3. **Dispute Isolation & Supervision**: Bounded state machine and dispute tracking in `ConflictKnowledgeEngine` in [conflict_detector.py](file:///home/dhurai/Projects/brud-ai/core_model/mini_brain/intelligence/conflict_detector.py).
4. **Immutable Version & Event Tracing**: `memory_item_versions` and `memory_item_events` tables in SQLite WAL mode.

**However, the following capabilities are missing or partial**:
- Multi-observation clustering and related-memory grouping across distinct lexical forms.
- Reversible observation-to-canonical transformation state tracking (`is_consolidated`, `consolidated_into_id`, `is_canonical`).
- Conflict-blocking consolidation gates (disputed memories must never be silently merged into unified ranges).
- Temporal validity reconciliation (distinguishing historical versions from current active states).
- Category-specific consolidation governance (autonomous consolidation permitted for `PREFERENCE`/`SEMANTIC`, restricted for `PROCEDURAL`/`TASK`, human-gated for `SYSTEM`/`ADMIN`).

---

## 2. Capability Audit Matrix (20 Core Dimensions)

| Capability Dimension | Current Status | Codebase Evidence & Evaluation |
|:---|:---:|:---|
| 1. **Related-memory grouping** | **PARTIAL** | Semantic similarity scoring exists via `score_vectors()` in `DuplicateKnowledgeEngine` (threshold 0.65), but multi-item semantic clustering across >2 items is missing. |
| 2. **Topic-based grouping** | **PARTIAL** | `ContextIntelligenceManager` tracks active topics in session turns (`TOPIC_TAXONOMY`), but does not group persisted long-term memory items. |
| 3. **Entity-based grouping** | **MISSING** | No dedicated named entity extraction or entity-attribute grouping for long-term memory consolidation. |
| 4. **Predicate-based grouping** | **PARTIAL** | Heuristic predicate and parameter extraction exists in `DuplicateKnowledgeEngine` and `ConflictKnowledgeEngine` (`extract_numbers_and_units()`, `extract_numbers_or_parameters()`). |
| 5. **Temporal grouping** | **PARTIAL** | `valid_from` and `expires_at` exist in `memory_items`, but temporal sequence reconciliation and historical vs current distinction are missing. |
| 6. **Category-aware grouping** | **EXISTING** | Scoped strictly per category in `memory_service.py` and `duplicate_detector.py` using `LEGACY_CATEGORY_MAP` and `MemoryCategory`. |
| 7. **Purpose-aware grouping** | **EXISTING** | Scoped strictly per purpose (`purpose_is_bounded`, `MEMORY_PURPOSES` in `core_model/conversation/memory_policy.py`). |
| 8. **Provenance-aware grouping** | **EXISTING** | Retains `source_session_id`, `source_turn_id`, `public_id` list in `compression_state` inside `MemoryIntelligenceEngine.compress_observations()`. |
| 9. **Conflict-aware grouping** | **PARTIAL** | Phase 17.5 detects conflicts (`ConflictKnowledgeEngine.evaluate_conflict()`), but a formal consolidation blocking gate is missing. |
| 10. **Canonical knowledge generation** | **PARTIAL** | Single canonical item selection exists; multi-item synthesized canonical creation exists in domain hook but is not wired into `MemoryService`. |
| 11. **Observation-to-canonical transformation** | **PARTIAL** | `compress_observations()` exists in `memory_intelligence.py` but lifecycle state transition of source items to `consolidated` is not wired. |
| 12. **Evidence aggregation** | **EXISTING** | $\text{total\_evidence} = \sum \text{evidence\_count}$ and reinforcement logic verified in `duplicate_detector.py` and `memory_intelligence.py`. |
| 13. **Provenance aggregation** | **EXISTING** | `source_references: list[str]` aggregated in compression metadata dictionary. |
| 14. **Version lineage preservation** | **EXISTING** | `memory_item_versions` table with SHA-256 checksums, version numbers, and immutable rows in SQLite. |
| 15. **Source lineage preservation** | **EXISTING** | `source_reference` in `memory_item_versions` and `memory_item_events`. |
| 16. **Compression state tracking** | **PARTIAL** | JSON state inside `details_json` exists; formal `compression_state` structured dataclass and state fields are needed. |
| 17. **Compression idempotency** | **MISSING** | Repeated consolidation pass could re-aggregate already consolidated memories without explicit markers. |
| 18. **Reversible consolidation** | **MISSING** | No `unconsolidate()` or decompression rollback workflow currently exists. |
| 19. **Retrieval of original evidence** | **PARTIAL** | Can be retrieved via `get_versions()` or `memory_item_events`, but no direct single API endpoint to retrieve source evidence. |
| 20. **Auditability after consolidation** | **EXISTING** | `memory_item_events` and `audit_logs` record all lifecycle mutations with timestamps and actor references. |

---

## 3. Architecture Audit Conclusion
The core database schema and domain intelligence components are robust and backward-compatible. Phase 17.6 does NOT require destructive schema migrations. All consolidation tracking, lineage references, and reversible snapshots can be maintained cleanly via `memory_item_versions`, `memory_item_events`, and a dedicated domain consolidator engine.
