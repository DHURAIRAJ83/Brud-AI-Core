# PHASE 44 RUNTIME ROUTING REPORT

**Date:** 2026-08-29  
**Status:** VERIFIED  
**Workstream:** Workstream 3 & 4 — Live Internal Canary Runtime & Scope Isolation  
**Router:** `RuntimeInternalCanary` (`core_model/release/phase44_runtime_canary.py`)  

---

## 1. Request Routing Verification Matrix

| Incoming Request Scope | Governance Approval | Requested Model Target | Routing Decision | Assigned Model ID | Traffic Allowed |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`public_chat`** | Irrelevant | Default | **ALLOW** | `0.1.0-synthetic-test` | 100% |
| **`public_chat`** | Approved | `0.3.0-candidate` | **BLOCK** (`ScopeViolationError`) | None | 0% |
| **`internal_canary`** | `REVIEW_REQUIRED` (No) | `0.3.0-candidate` | **REJECT** | `0.1.0-synthetic-test` | 0% |
| **`internal_canary`** | `ADMIN_APPROVED` (Yes)| `0.3.0-candidate` | **ALLOW** | `0.3.0-candidate` | $\le 1.0\%$ |
| **`internal_canary`** | Approved | Traffic > 1.0% | **BLOCK** (`ValueError`) | None | 0% |
| **Unauthorized Scope** | Irrelevant | Any | **REJECT** | `0.1.0-synthetic-test` | 0% |

---

## 2. Public Chat Isolation Guarantee

- **Safety Invariant:** `candidate.is_public_chat_eligible = False`.
- In all scenarios, public chat requests resolve exclusively to the verified fallback model (`0.1.0-synthetic-test`).
- Any attempt to force candidate execution in Public Chat immediately triggers a `ScopeViolationError` and automated tripwire rollback.
