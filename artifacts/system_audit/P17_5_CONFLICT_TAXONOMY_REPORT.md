# Phase 17.5 Stage A: Conflict Taxonomy & Guard Condition Report

**Date**: 2026-09-06  
**Status**: DESIGN & SPECIFICATION ONLY (Zero Production Changes)  
**Subject**: Canonical Conflict Taxonomy, Detection Guardrails, and Distinction Rules

---

## 1. Canonical Conflict Taxonomy

Phase 17.5 establishes an unambiguous 6-category conflict taxonomy:

| Conflict Category | Definition | Real-World Example Pair | Guard Condition |
| :--- | :--- | :--- | :--- |
| **`VALUE_CONFLICT`** | Contradictory qualitative attribute values assigned to the identical entity/subject. | A: *"Primary LLM provider is Anthropic."*<br>B: *"Primary LLM provider is OpenAI."* | Subject & predicate match ($\ge 0.88$ similarity); qualitative entity values are distinct and mutually exclusive. |
| **`NUMERIC_CONFLICT`** | Contradictory numerical measurements, quantities, or threshold limits. | A: *"Context window cap is 2048 tokens."*<br>B: *"Context window cap is 4096 tokens."* | Subject & property match; extracted numeric scalar quantities differ without version qualifiers. |
| **`STATE_CONFLICT`** | Incompatible boolean or operational active states. | A: *"Audit logging is enabled in production."*<br>B: *"Audit logging is disabled in production."* | Same subject; polarity flip (enabled vs disabled, active vs inactive, allowed vs forbidden). |
| **`TEMPORAL_CONFLICT`** | Incompatible recurrence intervals, execution frequencies, or schedules. | A: *"Database backup runs every 24 hours."*<br>B: *"Database backup runs every 12 hours."* | Same operational task; differing temporal interval units or frequencies. |
| **`POLICY_CONFLICT`** | Incompatible governance rules or operational constraints. | A: *"User deletion requires 2-admin approval."*<br>B: *"User deletion is self-service."* | Conflicting constraint predicates across identical administrative scope. |
| **`VERSION_CONFLICT`** | Conflicting specifications arising from different software/model versions. | A: *"v1.0 API endpoint is /api/v1/chat."*<br>B: *"v2.0 API endpoint is /api/v2/chat."* | Distinct version tags detected; classified as version-partitioned rather than direct contradiction. |

---

## 2. The Critical Three-Way Boundary

A fundamental challenge in memory intelligence is maintaining precise boundaries between:
1. `SEMANTIC_DUPLICATE`: Same fact phrased differently $\to$ Reinforce canonical.
2. `RELATED_BUT_DISTINCT`: Same domain/topic but different facts $\to$ Store both independently.
3. `POSSIBLE_CONFLICT`: Same attribute with incompatible values $\to$ Quarantine and dispute.

### Distinction Matrix

| Case | Memory A | Memory B | Vector Similarity | Predicate Match | Value Incompatibility | Classification | Correct System Action |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Case 1: Paraphrase** | *"Backup runs every 24 hours."* | *"Database is backed up once per day."* | 0.94 | Compatible | None (24h == 1 day) | `SEMANTIC_DUPLICATE` | Reinforce canonical `evidence_count += 1` |
| **Case 2: Related Facts** | *"Backup runs every 24 hours."* | *"Backup retention is 30 days."* | 0.76 | Different (Schedule vs Retention) | None | `RELATED_BUT_DISTINCT` | Store Memory B as a separate record |
| **Case 3: Numerical Dispute** | *"Backup retention is 30 days."* | *"Backup retention is 90 days."* | 0.91 | Identical (Retention) | Incompatible (30d $\neq$ 90d) | `NUMERIC_CONFLICT` | Preserve both, emit `DisputeRecord` |
| **Case 4: State Inversion** | *"Maintenance mode is active."* | *"Maintenance mode is inactive."* | 0.92 | Identical (Mode) | Mutually exclusive states | `STATE_CONFLICT` | Preserve both, emit `DisputeRecord` |

---

## 3. Contradiction Detection Guard Conditions

To prevent false positive conflicts, the Conflict Detection Engine must verify all of the following conditions before flagging a dispute:
1. **Scope Identity**: Both candidates share identical `participant_scope_key`, `category`, and `purpose`.
2. **Entity & Subject Match**: The core subject noun phrase must align (e.g. "backup retention").
3. **Semantic Overlap**: Cosine similarity $\ge 0.65$ (below 0.65 is classified as `DISTINCT`).
4. **Mutually Exclusive Value Test**: Extracted parameters, scalar values, or polarities cannot coexist simultaneously in the same operational context.
