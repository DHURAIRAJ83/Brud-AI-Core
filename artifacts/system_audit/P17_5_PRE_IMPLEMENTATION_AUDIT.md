# Phase 17.5 Stage A: Pre-Implementation Architecture Audit & Capability Mapping

**Date**: 2026-09-06  
**Status**: COMPLETE (Audit Only — Zero Production Changes)  
**Phase**: Phase 17.5 — Brud Mini Brain: Conflict Detection & Resolution  
**Baseline**: 213 / 213 PASS (Phase 17.2: 18/18, Phase 17.3: 15/15, Phase 17.4: 19/19)

---

## 1. Executive Summary

Phase 17.4 established multi-tier duplicate knowledge control (`EXACT`, `NORMALIZED`, `SEMANTIC`, `RELATED_BUT_DISTINCT`, `POSSIBLE_CONFLICT`, `DISTINCT`) and successfully proved that high semantic similarity with parameter contradictions must be quarantined as `POSSIBLE_CONFLICT` rather than merged.

This pre-implementation audit investigates the architecture required for **Phase 17.5: Conflict Detection & Resolution**.

### Core Tenets of Phase 17.5
1. **Conflict Detection $\neq$ Truth Determination**: Detecting that two statements contradict each other does not authorize the system to pick one as ground truth.
2. **Conflict Resolution $\neq$ Autonomous Authorization**: An AI model must never silently overwrite or supersede authoritative system/admin/user memories without authorized governance or administrative review.
3. **Immutability & Provenance Preservation**: Conflicting records must retain their full provenance, evidence trails, timestamps, and confidence ratings without data destruction.

---

## 2. Existing vs Missing Capability Matrix

| Capability Area | Component / File | Current Status | Description & Audit Finding | Target Phase |
| :--- | :--- | :--- | :--- | :--- |
| **Parameter Contradiction Detection** | `core_model/mini_brain/intelligence/duplicate_detector.py` | **EXISTING** | Basic regex-based parameter/interval extraction detects conflicting numbers/units (e.g. 24h vs 12h) during semantic comparison. | Phase 17.4 |
| **Exact / Normalized Deduplication** | `core_model/conversation/memory_deduplication.py`, `duplicate_detector.py` | **EXISTING** | Detects exact text and normalized string matches. | Phase 17.3 & 17.4 |
| **Polarity / Negation Contradiction** | `core_model/mini_brain/intelligence/conflict_detector.py` *(proposed)* | **MISSING** | Detection of direct affirmative vs negated claims (e.g., "Feature X is enabled" vs "Feature X is disabled"). | **Phase 17.5** |
| **Multi-Class Conflict Taxonomy** | Domain models | **MISSING** | Explicit categorization of conflicts (`VALUE_CONFLICT`, `NUMERIC_CONFLICT`, `STATE_CONFLICT`, `TEMPORAL_CONFLICT`, `POLICY_CONFLICT`, `VERSION_CONFLICT`). | **Phase 17.5** |
| **Bounded Conflict Confidence Engine** | Domain models | **MISSING** | Scored 0–100 confidence metric measuring likelihood that a contradiction exists (distinct from truth probability). | **Phase 17.5** |
| **Conflict Lifecycle State Machine** | Domain / DB models | **PARTIAL** | DB has `status` on `memory_items` and `conflict_status` on `memory_retrieval_results`, but lacks structured `dispute` entity and lifecycle transitions (`DETECTED` $\to$ `CLASSIFIED` $\to$ `PENDING_REVIEW` $\to$ `RESOLVED`). | **Phase 17.5** |
| **Conflict-Aware Retrieval Handling** | `backend/services/memory_service.py`, `memory_ranking.py` | **PARTIAL** | `conflict_penalty` exists in `compute_combined_score` and `conflict_policy` exists on profiles (`prefer_recent`, `prefer_user_confirmed`, `exclude_conflicting`), but lacks contextual conflict warning generation. | **Phase 17.5** |
| **Temporal Change vs Conflict** | `core_model/conversation/memory_normalization.py` | **MISSING** | Distinguishing historical facts ("used model Y last year") from current state contradictions ("uses model X now"). | **Phase 17.5 / 17.7** |
| **Versioned Change vs Conflict** | Domain models | **MISSING** | Distinguishing system version boundaries (e.g. v1.0 context vs v2.0 context) from factual contradictions. | **Phase 17.5** |
| **Supervised Human Arbitration Gate** | `backend/services/memory_service.py` | **EXISTING** | `confirm_memory`, `correct_memory`, and `reject_memory` exist in `MemoryService` with admin audit logging. | Phase 16 / 17.3 |
| **Dispute Resolution Event Ledger** | `backend/database/schema.py` (`memory_item_events`) | **PARTIAL** | `memory_item_events` supports immutable JSON payloads; specific `CONFLICT_DETECTED` and `CONFLICT_RESOLVED` event types are needed. | **Phase 17.5** |

---

## 3. Discovered Risks and Architectural Anti-Patterns to Avoid

1. **The "Recency Equals Truth" Fallacy**:
   - *Risk*: Automatically superseding an older user-confirmed fact with a newer unconfirmed statement.
   - *Architecture Guard*: `creation_source` and `confidence_type` rank higher than `created_at`. Unconfirmed assistant-inferred statements can never overwrite `user_confirmed` or `admin_created` memories.
2. **The "Frequency Equals Truth" Fallacy**:
   - *Risk*: A repeated erroneous claim increasing `evidence_count` and overpowering an established canonical fact.
   - *Architecture Guard*: Semantic reinforcement only occurs on compatible claims; contradictory claims fork into `POSSIBLE_CONFLICT` and are isolated from evidence accumulation.
3. **Cross-Participant Scope Bleed (G5 Violation)**:
   - *Risk*: Comparing facts across different users or tenants, leaking private information or creating false disputes.
   - *Architecture Guard*: Conflict detection candidate retrieval is strictly partitioned by `participant_scope_key`.
4. **Secret Leakage in Dispute Diffs (G8 Violation)**:
   - *Risk*: Displaying raw contradictory credentials or tokens in conflict audit logs or UI diffs.
   - *Architecture Guard*: Full G8 sanitization before token extraction, comparison, dispute generation, and audit logging.

---

## 4. Stage A Audit Conclusion

The existing architecture in `core_model/mini_brain/intelligence/` and `backend/services/memory_service.py` provides a clean foundation to introduce a dedicated `ConflictDetectionEngine` and `ConflictResolutionManager` without modifying core database schema or breaking the 213-test regression baseline.
