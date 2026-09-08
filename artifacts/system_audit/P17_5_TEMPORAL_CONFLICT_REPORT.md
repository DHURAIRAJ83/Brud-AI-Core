# Phase 17.5 Stage A: Temporal & Version Reasoning Report

**Date**: 2026-09-06  
**Status**: ARCHITECTURAL SPECIFICATION ONLY (Zero Production Code Changes)  
**Focus Area**: Distinguishing Temporal Evolution & Software Versions from True Contradictions

---

## 1. Temporal Knowledge Evolution vs Direct Contradiction

Knowledge often changes over time without representing a logical error or factual dispute:
- *Historical Reality*: *"In 2024, the server ran on Python 3.10."*
- *Present Reality*: *"In 2026, the server runs on Python 3.12."*

Both statements are factually correct within their respective temporal scopes. Treating them as a conflict degrades system intelligence.

### Architectural Strategy
1. **Temporal Marker Extraction**:
   - The engine scans for temporal qualifiers (e.g., `"now"`, `"currently"`, `"previously"`, `"historically"`, `"in 2024"`, `"as of v2"`).
2. **`valid_from` and `expires_at` Lifecycle Fields**:
   - The `memory_items` schema already provides `valid_from` and `expires_at` timestamp columns.
   - When a statement explicitly describes historical context, the engine associates temporal bounds rather than flagging a mutual contradiction.
3. **Temporal Non-Conflict Classification**:
   - When temporal markers indicate historical succession rather than concurrent incompatibility, the candidate is classified as `TEMPORAL_UPDATE` (or `RELATED_BUT_DISTINCT`), preserving historical records.

---

## 2. Version-Aware Contradiction Management

Software specifications change across major versions:
- *Version 1.0*: *"Context window cap is 2048 tokens."*
- *Version 2.0*: *"Context window cap is 4096 tokens."*

### Architectural Strategy
1. **Version Tag Detection**:
   - Regex patterns detect version identifiers (e.g., `v1`, `v2.0`, `Phase 16`, `Intelligence 2.0`).
2. **Version Partitioning**:
   - If Memory A has tag `v1.0` and Memory B has tag `v2.0`, they are classified as `VERSION_CONFLICT` / `VERSIONED_CHANGE`.
   - The system allows coexistence of version-scoped memories while providing clear version metadata during retrieval.

---

## 3. Recommended Phase Boundaries

- **Phase 17.5**: Detect basic temporal & version markers to prevent false positive disputes on obvious historical/versioned statements.
- **Phase 17.7 (Temporal Knowledge Management)**: Full temporal timeline indexing, historical snapshot querying, and automated temporal validity intervals.
