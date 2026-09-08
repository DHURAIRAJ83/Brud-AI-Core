# Phase 17.6 — Consolidation Architecture Report
**Brud Mini Brain: Memory Consolidation Pipeline & Canonical Model**

## 1. Pipeline Placement of Memory Consolidation
In the Brud Mini Brain memory pipeline, Consolidation operates as an asynchronous, periodic, or on-demand post-proposal optimization process:

```
[ CAPTURE ] ──► [ SANITIZE (G8) ] ──► [ NORMALIZE ] ──► [ CLASSIFY ]
                                                              │
                                                              ▼
[ RETRIEVE ] ◄── [ REINFORCE ] ◄── [ CONFLICT CHECK ] ◄── [ DEDUPLICATE ]
      │                                                       │
      │                                                       ▼
      │                                            [ ACTIVE MEMORIES STORE ]
      │                                                       │
      │                                                       ▼
[ ANNOTATE WARNINGS ] ◄─────────────────────────── [ CONSOLIDATION ENGINE ]
                                                   • Cluster Scoped Items (G5)
                                                   • Check Eligibility Gates
                                                   • Synthesize Canonical Claim
                                                   • Aggregate Evidence & Lineage
                                                   • Transition Sources to 'consolidated'
                                                   • Record Immutable Events
```

---

## 2. Conceptual Knowledge Hierarchy

Phase 17.6 formalizes the clear operational distinction across knowledge tiers:

```
┌────────────────────────────────────────────────────────┐
│ 1. RAW OBSERVATION                                     │
│ User utterance or turn context ("Backup runs daily")   │
└──────────────────────────┬─────────────────────────────┘
                           │ G8 Sanitize + Normalize
                           ▼
┌────────────────────────────────────────────────────────┐
│ 2. MEMORY ITEM                                         │
│ Scoped record with category, purpose, timestamp        │
└──────────────────────────┬─────────────────────────────┘
                           │ Consolidation Grouping (Cosine >= 0.75, same predicate)
                           ▼
┌────────────────────────────────────────────────────────┐
│ 3. CANONICAL KNOWLEDGE RECORD                          │
│ Synthesized statement + sum(evidence_count)            │
│ + aggregated provenance + highest confidence           │
└──────────────────────────┬─────────────────────────────┘
                           │ Loss-Minimizing Structural Compression
                           ▼
┌────────────────────────────────────────────────────────┐
│ 4. COMPRESSED KNOWLEDGE STATE                          │
│ Lineage pointers to source IDs + immutable audit snapshot│
└────────────────────────────────────────────────────────┘
```

### Knowledge Tier Definitions:
- **Raw Observation**: Ephemeral turn content before normalization and verification.
- **Memory Item**: Granular, single-observation persisted record in `memory_items`.
- **Canonical Knowledge**: High-confidence, representative record representing consolidated observations on a specific predicate or attribute.
- **Compressed Knowledge**: Canonical record enriched with complete provenance pointers, aggregated evidence counts, and compression metadata without row deletion.

---

## 3. Consolidation Invariants & Rules

1. **Zero Destructive Deletion (G10/G11)**: Original memory item records transition to `status = 'consolidated'`; their raw evidence, version history, and embeddings remain 100% intact and retrievable.
2. **Scope Partitioning (G5)**: Strict partitioning on `participant_scope_key`, `category`, and `purpose`. Cross-scope grouping is strictly prohibited.
3. **Conflict Blocking Gate (Phase 17.5)**: If any candidate in a cluster is subject to an active dispute (`PENDING_REVIEW` or `UNDER_REVIEW`), consolidation of that cluster is BLOCKED.
4. **Idempotency**: Running consolidation multiple times on the same memory set must produce identical canonical outputs without creating duplicate rows or inflating evidence counts.
5. **Reversibility**: An administrator can trigger `unconsolidate_memory()` to restore constituent items to `active` and mark the canonical record `superseded`.
