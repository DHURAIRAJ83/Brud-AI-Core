# Phase 17.6 — Implementation Boundary & Stage B Plan Report
**Brud Mini Brain: Stage B Proposed Scope, Test Strategy & Migration Safety**

## 1. Stage B File Boundaries

### Proposed New Files (Stage B):
1. `core_model/mini_brain/intelligence/memory_consolidator.py`
   - `MemoryConsolidatorEngine`: Domain logic for grouping, canonical formation, evidence summing, and reversibility.
   - `ConsolidationGroup`: Dataclass representing a cluster of related observations.
   - `ConsolidationResult`: Dataclass representing the canonical output and lineage references.
2. `tests/e2e/test_p17_6_memory_consolidation.py`
   - Complete 33-point verification suite covering all consolidation rules, lineage, conflict gates, governance, and invariants.

### Proposed Modified Files (Stage B):
1. `core_model/mini_brain/intelligence/__init__.py`
   - Export new consolidator symbols (`MemoryConsolidatorEngine`, `ConsolidationGroup`, `ConsolidationResult`).
2. `backend/services/memory_service.py`
   - Wire `consolidate_memories(participant_scope_key, category, purpose, admin_id)` endpoint.
   - Wire `unconsolidate_memory(canonical_public_id, admin_id)` endpoint for reversible rollback.

### Strictly Untouched Files:
- Database schema / migrations (`schema.py`, `migrations.py`)
- UI / Frontend code
- Prior intelligence layers (`context_intelligence.py`, `duplicate_detector.py`, `conflict_detector.py`)

---

## 2. Stage B 33-Point Test Matrix
1. Related-memory grouping (cosine >= 0.75)
2. Canonical formation & synthesis
3. Evidence count preservation ($\sum \text{evidence}$)
4. Provenance preservation (`source_references`)
5. Compression idempotency
6. No duplicate canonical records
7. No evidence count inflation
8. Unresolved dispute blocking gate
9. Resolved dispute handling (`SUPERSEDE_EXISTING`, `RETAIN_EXISTING`)
10. Coexistence handling (`RETAIN_BOTH_COEXIST`)
11. Temporal validity window preservation
12. Category isolation (`PREFERENCE` vs `SEMANTIC`)
13. Purpose isolation
14. Participant scope isolation (G5)
15. SYSTEM category human governance (G1)
16. ADMIN category human governance (G1)
17. G8 secret sanitization in consolidated claims
18. Retrieval integrity & accuracy
19. Citation & provenance traceability
20. Archive status interactions
21. Freshness state evaluation
22. Calibrated confidence preservation
23. Importance score preservation
24. Version lineage checksum verification
25. Reversibility & reconstruction (`unconsolidate_memory`)
26. Bounded candidate pool ($N \le 20$)
27. CPU performance ($\le 5\text{ ms}$)
28. G1 invariant preservation
29. G4 invariant preservation
30. G5 invariant preservation
31. G8 invariant preservation
32. G9 invariant preservation
33. G10/G11 SQLite WAL durability
