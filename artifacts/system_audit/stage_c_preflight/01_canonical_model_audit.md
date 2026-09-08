# Stage C Pre-Flight Audit — 01: Canonical Model Implementation Audit

**Audit Date:** 2026-09-01  
**Audit Context:** Phase 60 WS07 Stage C Pre-Flight  
**Governance Mode:** STRICT READ-ONLY, ZERO MUTATION (`training_execution_authorized = FALSE`)

---

## 1. Executive Summary & Canonical Identification

Following the exhaustive forensic audit across all 9 `BrudSmallV2Model` occurrences (4 production runners, 5 test fixtures), we have determined the canonical implementation for `BrudSmallV2Model`.

```text
CANONICAL_MODEL_FILE   = artifacts/candidates/phase60/ws07/e3/run_e3_experiments.py
CANONICAL_MODEL_CLASS  = BrudSmallV2Model (line 75)
REASON                 = Chronologically latest (WS07 E3), correct buffer persistence (persistent=False), full repetition-controlled decoding (θ=1.25 + 3-gram no-repeat), verified state_dict compatibility.
EVIDENCE               = SHA-256 matching E3 runner, tested on E3-A through E3-E splits.
```

---

## 2. Comprehensive Comparison Matrix of Production Implementations

| Attribute | Runner P1 (WS05) | Runner P2 (WS06) | Runner P3 (WS07 Stage A) | Runner P4 (E3 Experiments) — CANONICAL |
|---|---|---|---|---|
| **File Path** | `artifacts/candidates/phase60/run_controlled_training_ws05.py` | `artifacts/candidates/phase60/run_capability_evaluation_ws06.py` | `artifacts/candidates/phase60/ws07/run_ws07_stage_a_diagnostics.py` | `artifacts/candidates/phase60/ws07/e3/run_e3_experiments.py` |
| **Line Number** | 47 | 46 | 49 | 75 |
| **Implementation Hash** | `e8056a70bc11` | `5f5834fb2070` | `518a7b39d5e8` | `6aecf087c213` |
| **Vocab Size** | 1024 | 1024 | 1024 | 1024 |
| **d_model** | 128 | 128 | 128 | 128 |
| **nhead** | 4 | 4 | 4 | 4 |
| **num_layers** | 2 | 2 | 2 | 2 |
| **dim_feedforward** | 256 | 256 | 256 | 256 |
| **PE Buffer Persistence** | `persistent` default (`True`) | `persistent=False` | `persistent=False` | `persistent=False` |
| **State Dict Key Count** | 28 keys (includes `pe`) | 27 keys (excludes `pe`) | 27 keys (excludes `pe`) | 27 keys (excludes `pe`) |
| **Parameter Count** | 528,128 | 528,128 | 528,128 | 528,128 |
| **Generation Engine** | None (Training only) | Greedy / Temperature sampling | Controlled (θ=1.25, 3-gram) | Controlled (θ=1.25, 3-gram, EOS guard) |
| **Inference Status** | Training runner | Capability Probe runner | Diagnostic runner | Multi-experiment runner |

---

## 3. Detailed Non-Canonical Implementations

The non-canonical implementations in the repository MUST NOT be deleted during Pre-Flight or Stage C. They serve essential historical audit and regression testing roles:

1. **P1 (`run_controlled_training_ws05.py`)**: Authoritative training runner for WS05 baseline. Generated the frozen WS05 checkpoint (`30dbb8927c...`).
2. **P2 (`run_capability_evaluation_ws06.py`)**: Authoritative functional evaluation runner for WS06. Evaluates candidate checkpoints against the 24 CAP probes.
3. **P3 (`run_ws07_stage_a_diagnostics.py`)**: Diagnostics runner for WS07 Stage A failure modes (FM-01 through FM-04).
4. **Test Fixtures (T1-T5)**: Self-contained test mocks in `tests/evaluation/` ensuring unit and integration test isolation.

---

## 4. Pre-Flight Action Plan for Stage C Model Module

To eliminate copy-paste drift before starting Stage C (E4/E5), we propose establishing a single shared architecture file:

```text
PROPOSED CANONICAL MODULE = core_model/architecture/brud_small_v2.py
```

This file will expose:
- `BrudSmallV2Model` (528k baseline)
- `BrudSmallV4Model` / `BrudSmallScaledModel` (E5 ~3.16M architecture for T=512)

No files will be deleted. Existing runner scripts will optionally import from this canonical module.
