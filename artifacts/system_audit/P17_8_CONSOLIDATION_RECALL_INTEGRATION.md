# PHASE 17.8 — CONSOLIDATION RECALL INTEGRATION
# CANONICAL PRECEDENCE & PROVENANCE CITATION

**Document ID**: `P17_8_CONSOLIDATION_RECALL_INTEGRATION`  
**Phase**: Phase 17.8 (Brud Mini Brain — Memory Recall & Retrieval Intelligence)  
**Status**: SPECIFICATION COMPLETE (STAGE A)  

---

## 1. The Canonical Duplication Problem

In Phase 17.6, related memories are consolidated into a high-level canonical claim while preserving constituent records in `status = 'consolidated'` or `status = 'superseded'`.

If naive search is performed over all memory rows, a user query (e.g. "What database do we use?") might return:
1. Canonical: "PostgreSQL 16 is used for primary storage with SQLite for edge" (Score: 88.0)
2. Constituent 1: "Postgres database setup in AWS" (Score: 84.0)
3. Constituent 2: "SQLite edge local storage" (Score: 81.0)
4. Constituent 3: "PostgreSQL 16 config parameters" (Score: 79.0)

This causes **result bloat**, consumes token budget with duplicate semantic content, and dilutes retrieval diversity.

---

## 2. Deterministic Consolidation Deduplication Policy

Phase 17.8 establishes the following deterministic resolution rules:

1. **Canonical Precedence Rule**:
   - When a canonical memory item is accepted into the retrieval result set, all of its constituent source memory public IDs (extracted from `compression_state.source_references` or `get_consolidated_sources()`) are added to an active `suppressed_source_ids` set.
   - Any constituent memory whose `public_id` exists in `suppressed_source_ids` is excluded from the final result set in `CURRENT` mode.

2. **Constituent Standalone Rule**:
   - If a constituent memory matches a query but its parent canonical memory does NOT meet the retrieval threshold or was not formed, the constituent memory is returned as an independent valid result.

3. **Historical Mode Pass-Through**:
   - In `HISTORICAL` mode, both canonical and constituent memories may be returned, with explicit metadata linking:
     - `is_canonical: bool`
     - `parent_canonical_id: str | None`
     - `constituent_source_ids: list[str]`

4. **Provenance Attachment**:
   - Every recalled canonical memory includes its complete lineage citations:
     - `evidence_count`: Aggregated evidence count
     - `source_observation_count`: Number of raw observations synthesized
     - `source_references`: List of opaque public IDs of original observations
     - `compression_method`: `deterministic_structural`

---

## 3. Unconsolidation Reversibility Guarantee

If a canonical memory is unconsolidated via `unconsolidate_memory()` (Phase 17.6):
- The canonical memory transitions to `revoked` / `superseded`.
- The constituent memories transition back to `active`.
- Subsequent recall queries automatically discover and rank the restored constituent memories individually without any stale suppression artifacts.
