# PHASE 17.8 — ELIGIBILITY & GOVERNANCE REPORT
# STATUS, CATEGORY & DISPUTE ELIGIBILITY MATRIX

**Document ID**: `P17_8_ELIGIBILITY_GOVERNANCE_REPORT`  
**Phase**: Phase 17.8 (Brud Mini Brain — Memory Recall & Retrieval Intelligence)  
**Status**: SPECIFICATION COMPLETE (STAGE A)  

---

## 1. Lifecycle Status Eligibility by Mode

Memory eligibility is governed strictly according to the active retrieval mode:

| Lifecycle Status | CURRENT Mode | HISTORICAL Mode | TASK Mode | PREFERENCE Mode | Exclusion Reason / Action |
|---|---|---|---|---|---|
| **`active`** | ✅ ELIGIBLE | ✅ ELIGIBLE | ✅ (If Task/Proc) | ✅ (If Preference) | Standard eligible candidate. |
| **`consolidated`** | 🟡 CONDITIONAL | ✅ ELIGIBLE | 🟡 CONDITIONAL | 🟡 CONDITIONAL | Suppressed if canonical memory retrieved; else eligible. |
| **`superseded`** | ❌ EXCLUDED | ✅ ELIGIBLE | ❌ EXCLUDED | ❌ EXCLUDED | Historical trace only; excluded in live conversation. |
| **`expired`** | ❌ EXCLUDED | ✅ ELIGIBLE | ❌ EXCLUDED | ❌ EXCLUDED | Soft-expired; preserved for historical retrospective. |
| **`archived`** | ❌ EXCLUDED | ✅ ELIGIBLE | ❌ EXCLUDED | ❌ EXCLUDED | Archived memory preserved for audit/history queries. |
| **`proposed`** | ❌ EXCLUDED | ❌ EXCLUDED | ❌ EXCLUDED | ❌ EXCLUDED | Unconfirmed candidate (`status_proposed_excluded`). |
| **`awaiting_confirmation`** | ❌ EXCLUDED | ❌ EXCLUDED | ❌ EXCLUDED | ❌ EXCLUDED | Requires user confirmation before retrieval. |
| **`quarantined`** | ❌ EXCLUDED | ❌ EXCLUDED | ❌ EXCLUDED | ❌ EXCLUDED | Safety blocked (`status_quarantined_excluded`). |
| **`rejected`** | ❌ EXCLUDED | ❌ EXCLUDED | ❌ EXCLUDED | ❌ EXCLUDED | Explicitly rejected knowledge. |
| **`revoked`** | ❌ EXCLUDED | ❌ EXCLUDED | ❌ EXCLUDED | ❌ EXCLUDED | Consent revoked (`status_revoked_excluded`). |
| **`deleted`** | ❌ EXCLUDED | ❌ EXCLUDED | ❌ EXCLUDED | ❌ EXCLUDED | Soft-deleted record (`status_deleted_excluded`). |

---

## 2. Category Governance & G1 Protection

1. **SYSTEM & ADMIN Categories (G1 Protection)**:
   - Must have `status == 'active'` and explicit authorization before being returned in standard user recall.
   - Cannot be autonomously modified or expired.
   - Protected against public credential leakage.

2. **TASK Category**:
   - TTL: 1 day (86,400s).
   - In `CURRENT` mode, expired tasks are excluded to prevent obsolete operational instruction bleed.
   - In `TASK` mode, active workflow tasks are prioritized.

3. **PROCEDURAL Category**:
   - TTL: 30 days.
   - Sequence steps preserved in order.

4. **SEMANTIC Category**:
   - TTL: 90 days.
   - Freshness decay does not alter truth validity. Historical facts retain factual weight.

5. **PREFERENCE Category**:
   - TTL: 180 days.
   - Preserved across long idle periods without silent degradation.

---

## 3. Dispute Policy Governance (Phase 17.5 Integration)

When a candidate memory is linked to an unresolved dispute (`DETECTED`, `PENDING_REVIEW`, `UNDER_REVIEW`), retrieval behavior is strictly governed by the profile's `conflict_policy`:

1. **`exclude_conflicting`**:
   - Candidate is excluded from accepted results and placed into `excluded` list with `exclusion_reason = "disputed_memory_pending_resolution"`.
2. **`prefer_recent`**:
   - Candidate is retained but penalized ($P_{\text{conflict}} = 20.0$) and annotated with a mandatory advisory dispute warning string.
3. **`prefer_user_confirmed`**:
   - If candidate `confidence_type == "user_confirmed"`, it is retained with advisory warning.
   - If candidate is unconfirmed or assistant-inferred, it is excluded with `exclusion_reason = "disputed_unconfirmed_excluded"`.
