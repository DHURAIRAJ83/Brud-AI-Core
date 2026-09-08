# WS08 Duplicate Forensic Audit — 15: Duplicate Risk Register

**Audit Date:** 2026-09-01  
**READ-ONLY AUDIT**

---

## Risk Register

| Risk ID | Class / Item | Category | Severity | Probability | E4/E5 Impact | Mitigation Status | Details |
|---|---|---|---|---|---|---|---|
| DRSK-01 | `BrudSmallV2Model` PE checkpoint mismatch | Training | **P0** | HIGH | ✅ Direct | UNMITIGATED | WS05 runner saves `pe` in state_dict (persistent=True default). E4/E5 loading with strict=True will fail. Must use strict=False or strip key. |
| DRSK-02 | No shared `BrudSmallV2Model` module | Architecture | **P0** | MEDIUM | ✅ Direct | UNMITIGATED | Copy-paste drift between runners. If E4/E5 inadvertently changes constructor, checkpoint becomes incompatible. |
| DRSK-03 | No shared training engine module | Architecture | **P0** | MEDIUM | ✅ Direct | UNMITIGATED | Training loop definition inconsistency possible across future phases. |
| DRSK-04 | `FeedbackRepository` in phase2.py (dead) | Code hygiene | **LOW** | LOW | ❌ None | INFORMATIONAL | Dead code. Not callable. Low risk of accidental import, but creates confusion. |
| DRSK-05 | `AdminReviewRequest` 14-way split | Technical debt | **P2** | LOW | ❌ None | INFORMATIONAL | 11 identical copies. Harmless but any future field change requires 11 edits. Consolidation is maintenance improvement. |
| DRSK-06 | `HardwareProbeResponse` true duplicate | Technical debt | **P2** | LOW | ❌ None | INFORMATIONAL | Identical in 2 files. No runtime confusion. Consolidation is minor cleanup. |
| DRSK-07 | `InferenceEngine` stub import at package level | Dead code | **INFO** | LOW | ❌ None | INFORMATIONAL | Imported at `core_model/__init__.py:6` but never executed. Calling `.generate()` would raise NotImplementedError loudly. |
| DRSK-08 | 6,017 adapter-it-at checkpoints (3.8GB) | Disk bloat | **P3** | N/A | ❌ None | INFORMATIONAL | Dead artifacts consuming 3.8GB. No runtime risk. Archive after E6. |
| DRSK-09 | `FakeUploadFile` × 15 test files | Test debt | **P3** | LOW | ❌ None | INFORMATIONAL | Identical test helper in 15 files. Any change requires 15 edits. Conftest.py consolidation is a P3 cleanup. |
| DRSK-10 | `CreateSessionRequest` × 12 Mini Brain modules | Nominal duplicate | **INFO** | N/A | ❌ None | BY DESIGN | Intentional specialization (B). Each carries domain-specific fields. No centralization warranted. |

---

## Risk Summary

```
P0 RISKS (Must address before E4/E5): 3
  DRSK-01: BrudSmallV2Model PE checkpoint key (strict=True load failure)
  DRSK-02: No shared model module (architecture drift risk)
  DRSK-03: No shared training engine (training loop drift risk)

P1 RISKS: 0

P2 RISKS (Technical debt, currently harmless): 2
  DRSK-05: AdminReviewRequest 14-way split (maintenance burden)
  DRSK-06: HardwareProbeResponse true duplicate (minor)

P3 RISKS (Historical / audit only): 3
  DRSK-08: 3.8GB dead checkpoints
  DRSK-09: FakeUploadFile × 15
  DRSK-10: CreateSessionRequest × 12 (by design)

INFO (No action needed): 2
  DRSK-04: FeedbackRepository phase2.py (dead)
  DRSK-07: InferenceEngine stub (dead)
```
