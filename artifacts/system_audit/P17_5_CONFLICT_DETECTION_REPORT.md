# Phase 17.5 — Conflict Detection Report
**Brud Mini Brain: Intelligence 2.0 Conflict Knowledge Engine**

## 1. Executive Summary
Phase 17.5 Stage B has implemented the deterministic Conflict Detection & Resolution subsystem in `core_model/mini_brain/intelligence/conflict_detector.py` and integrated it cleanly into `backend/services/memory_service.py`.

The conflict knowledge engine detects genuine contradictions between scoped memories, categorizes them according to a 6-type conflict taxonomy, calculates bounded conflict confidence scores (0.0–100.0), creates structured dispute records, and enforces supervised human dispute resolution without autonomous truth decisions.

---

## 2. Core Architectural Components

### 2.1 Domain Module
- **Module**: `core_model/mini_brain/intelligence/conflict_detector.py`
- **Exports in `__init__.py`**:
  - `ConflictClassification`
  - `ConflictConfidence`
  - `DisputeState`
  - `ResolutionStrategy`
  - `DisputeRecord`
  - `ConflictMatchResult`
  - `ConflictKnowledgeEngine`

### 2.2 Conflict Knowledge Engine Workflow
```
Incoming Proposed Memory (G8 Sanitized)
              │
              ▼
Phase 17.4 Deduplication Pipeline
              │
              ├─ Exact Duplicate ──────────► Reinforce Canonical Row
              ├─ Normalized Duplicate ─────► Reinforce Canonical Row
              ├─ Semantic Duplicate ───────► Reinforce Canonical Row
              └─ Possible Conflict / Distinct
                            │
                            ▼
Phase 17.5 Conflict Knowledge Engine
              │
              ├─ Scoped Candidates Evaluation (Max 20, same participant/category/purpose)
              ├─ Property & Attribute Compatibility Check (e.g., schedule vs retention)
              ├─ Multi-signal Contradiction Analysis
              │   ├─ Version mismatch check
              │   ├─ Polarity / boolean state opposition
              │   ├─ Scalar measurement / numeric contradiction
              │   ├─ Temporal scheduling window incompatibility
              │   ├─ Policy / administrative rule clash
              │   └─ Qualitative attribute value incompatibility
              │
              ├─ Conflict Confidence Computation (Bounded 0–100)
              │
              ├─ Genuine Conflict Detected?
              │   ├── YES:
              │   │     • Create DisputeRecord (State: DETECTED -> PENDING_REVIEW)
              │   │     • Record immutable CONFLICT_DETECTED & DISPUTE_CREATED events
              │   │     • Retain existing active memory
              │   │     • Set new memory status to awaiting_confirmation
              │   │     • Require authorized human resolution
              │   │
              │   └── NO:
              │         • Retain memories as separate (RELATED_BUT_DISTINCT or DISTINCT)
              │         • Continue standard lifecycle
```

---

## 3. Strict Safety & Governance Guarantees
1. **Zero Autonomous Truth Decisions (G1)**: Conflict detection solely establishes that a contradiction exists. It NEVER asserts which claim is true.
2. **Strict Scope Isolation (G5)**: Conflict detection evaluates memories strictly within `participant_scope_key`, `category`, and `purpose`. No cross-participant candidate comparison is ever performed.
3. **Candidate Boundary (G4)**: Upper candidate evaluation limit is hard-capped at `MAX_CANDIDATES = 20`.
4. **Pre-Analysis Secret Sanitization (G8)**: All text passes regex-based credential and token redaction before comparison, vector scoring, dispute creation, and event logging.
5. **Human Resolution Only**: Final arbitration requires explicit administrator action (`SUPERSEDE_EXISTING`, `RETAIN_EXISTING`, `RETAIN_BOTH_COEXIST`, `DISMISS`).
