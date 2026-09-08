# WS08 Duplicate Forensic Audit — 12: Security Duplicate Impact

**Audit Date:** 2026-09-01  
**READ-ONLY AUDIT**

---

## 1. Security Assessment Methodology

For each duplicate class, we verify:
- Authentication / authorization differences
- Validation completeness
- CSRF protection
- Secret handling
- Audit logging
- Governance enforcement
- Candidate isolation

---

## 2. AdminApprovalRecord (DUP-02)

| Version | File | Security Fields |
|---|---|---|
| A | `backend/models/domain.py:496` | Pydantic model with standard fields |
| B | `core_model/release/phase43_promotion_governance.py:35` | Dataclass with governance-specific fields |

These serve different concerns: `domain.py` is the API model; `phase43` is the internal governance record.

**No shared import or confusion point. Neither version has weaker security.**

**Severity: INFO**

---

## 3. FeedbackRepository (DUP-28)

| Version | File | Security | Imported By Production? |
|---|---|---|---|
| Legacy | `backend/database/repositories/phase2.py` | May lack recent security enhancements | ❌ NO — not imported |
| Active | `backend/database/repositories/feedback.py` | Full parameterized SQL, CSRF-safe | ✅ YES |

**The legacy version is dead code — never called in production. No security bypass possible.**

**Severity: INFO**

---

## 4. AdminReviewRequest (DUP-03) — 14 copies

**Two hash groups:**
- `446c38f42e00f781` — 11 files (dataset, evaluation, language, etc.)
- `c59e92d40d9b2d1b` — 3 files (release pipeline, continuous learning, learning supervisor)

These serve different review queue domains. The `c59e92d40d9b2d1b` group has an extra field for release pipeline stage tracking. No version has weaker authentication or authorization.

**All `AdminReviewRequest` instances route through the same middleware stack (CSRF, JWT auth, audit logging).**

**Severity: INFO**

---

## 5. BrudSmallV2Model (DUP-10)

| Concern | Assessment |
|---|---|
| Could a weaker model be activated? | ❌ No — model loading uses file path, not Python class |
| Could production use WS05 weights (potentially worse quality)? | ❌ No — `is_public_chat_eligible=false` blocks all candidates |
| Could security validation differ between model versions? | ❌ No — safety filters are in PublicChatRoutingService, not in BrudSmallV2Model |

**Severity: INFO**

---

## 6. ResourceGuard (DUP-44)

| Version | File | Guards |
|---|---|---|
| Phase47 | `phase47_long_run_orchestrator.py` | CPU/RAM limits for long training runs |
| Phase48 | `phase48_training_worker.py` | Different field structure for worker-level guards |

These are **not security guards** — they are hardware resource limiters. Neither creates a security bypass path.

**Severity: INFO**

---

## 7. HardwareProbeResponse (DUP-31) — Identical Copies

Both copies are read-only response schemas that report system resource availability. No authentication or authorization logic is embedded.

**Severity: INFO**

---

## 8. InferenceEngine stub (core_model/inference/)

The dead `InferenceEngine` stub raises `NotImplementedError`. If any code accidentally called it, the failure would be **loud and immediate** — not a silent security bypass.

**Severity: INFO**

---

## 9. Production vs Dead Security Comparison

| Pair | Old/Dead | New/Active | Old has weaker security? | Callable in prod? |
|---|---|---|---|---|
| FeedbackRepository | phase2.py | feedback.py | 🟡 Possibly missing updates | ❌ Not callable |
| InferenceEngine | core_model/inference/ | inference_runtime/ | N/A — raises error | ❌ Never called |
| AdminApprovalRecord | phase43 governance | domain.py | N/A — different domain | ❌ Separate imports |
| GuardAction phase53 | phase53_memorization_guard | phase56 | N/A — different logic version | ❌ Not imported by active code |

---

## 10. Security Severity Summary

| ID | Class | Severity | Reason |
|---|---|---|---|
| SEC-01 | `FeedbackRepository` (phase2.py) | **LOW** | Dead code, not callable, but old version may lack recent SQL hygiene improvements |
| SEC-02 | `BrudSmallV2Model` (4 runners) | **LOW** | checkpoint pe-key mismatch could cause E4/E5 runner error (not security, but stability) |
| SEC-03 | All other duplicates | **INFO** | No authentication, authorization, CSRF, or secret handling differences found |

---

## 11. Security Verdict

```
CRITICAL   DUPLICATE SECURITY RISKS: 0
HIGH       DUPLICATE SECURITY RISKS: 0
MEDIUM     DUPLICATE SECURITY RISKS: 0
LOW        DUPLICATE SECURITY RISKS: 2 (FeedbackRepository legacy, BrudSmallV2 PE mismatch)
INFO       DUPLICATE SECURITY FINDINGS: 69 (nominal duplicates, no security impact)

No security-critical duplicate code situation exists in Brud AI.
No scenario where both a new secure implementation AND an old insecure implementation
are simultaneously callable from a production request path.
```
