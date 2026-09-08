# Phase 17.7 — Test Plan Specification
**Brud Mini Brain: Complete 35-Scenario Verification Matrix**

## 1. Test Architecture & Coverage Strategy
The Phase 17.7 test suite will be implemented in `tests/e2e/test_p17_7_memory_lifecycle.py` and must cover at least 35 verification scenarios across all lifecycle dimensions.

---

## 2. 35-Scenario Test Matrix

| Test ID | Name | Purpose | Input Conditions | Expected Result | Target Invariant |
|:---|:---|:---|:---|:---|:---:|
| **T01** | `test_freshness_fresh_classification` | Verify memory $< 0.25\text{TTL}$ is FRESH | Memory age = 10% of TTL | `freshness_state == 'FRESH'`, penalty = 0.0 | G4 |
| **T02** | `test_freshness_aging_classification` | Verify memory $\ge 0.25\text{TTL}$ is AGING | Memory age = 30% of TTL | `freshness_state == 'AGING'`, penalty = 5.0 | G4 |
| **T03** | `test_freshness_stale_classification` | Verify memory $\ge 0.75\text{TTL}$ is STALE | Memory age = 80% of TTL | `freshness_state == 'STALE'`, penalty = 15.0 | G4 |
| **T04** | `test_freshness_expired_classification` | Verify memory $\ge 1.0\text{TTL}$ is EXPIRED | Memory age = 110% of TTL | `freshness_state == 'EXPIRED'`, penalty = 40.0 | G4 |
| **T05** | `test_task_category_ttl_expiration` | Verify TASK category fast expiration | `category = 'TASK'`, age = 2 days | Status becomes `expired`, excluded from active | G10 |
| **T06** | `test_episodic_category_decay` | Verify EPISODIC category 7-day lifecycle | `category = 'EPISODIC'`, age = 8 days | Status becomes `expired` | G10 |
| **T07** | `test_procedural_category_decay` | Verify PROCEDURAL category 30-day lifecycle | `category = 'PROCEDURAL'`, age = 15 days | State is `AGING`, step order preserved | G4 |
| **T08** | `test_semantic_category_decay` | Verify SEMANTIC category 90-day lifecycle | `category = 'SEMANTIC'`, age = 45 days | State is `AGING`, facts remain valid | G4 |
| **T09** | `test_preference_category_decay` | Verify PREFERENCE category 180-day lifecycle | `category = 'PREFERENCE'`, age = 100 days | State is `AGING`, active across sessions | G4 |
| **T10** | `test_system_governance_no_auto_expire` | Verify SYSTEM category G1 protection | `category = 'SYSTEM'`, age = 400 days | Status remains `active`, requires admin ID | **G1** |
| **T11** | `test_admin_governance_no_auto_expire` | Verify ADMIN category G1 protection | `category = 'ADMIN'`, age = 400 days | Status remains `active`, requires admin ID | **G1** |
| **T12** | `test_manual_admin_expiration` | Verify admin can expire SYSTEM/ADMIN | Admin passes `expire_memory(admin_id)` | Status becomes `expired`, event logged | **G1** |
| **T13** | `test_observation_reinforcement` | Verify repeated observation resets freshness | Aging memory receives duplicate proposal | Freshness reset to `FRESH`, evidence incremented | G4 |
| **T14** | `test_retrieval_no_evidence_inflation` | Verify read queries do not increment evidence | Retrieve memory 10 times | `access_count == 10`, `evidence_count == 1` | G4 |
| **T15** | `test_reinforcement_confidence_ceiling` | Verify confidence boost capped at 100.0 | 20 repeat observations | Confidence bounded at $\le 100.0$ | G4 |
| **T16** | `test_archival_transition` | Verify expired memory transitions to archived | `archive_memory(admin_id)` | Status becomes `archived`, event logged | G10 |
| **T17** | `test_archival_non_destructive` | Verify archived row and versions intact | Query versions and events of archived item | 100% of versions and history retained | G10 |
| **T18** | `test_archival_exclusion_from_active_retrieval` | Verify archived excluded from search | Retrieval query matching archived item | Excluded with `status_archived_excluded` | G5 |
| **T19** | `test_admin_reactivation` | Verify archived item can be reactivated | `reactivate_memory(admin_id)` | Status becomes `active`, event logged | G1 |
| **T20** | `test_temporal_validity_future_date` | Verify future `valid_from` excluded | `valid_from = now + 1 day` | Excluded with `not_yet_valid` | G4 |
| **T21** | `test_historical_fact_permanence` | Verify point-in-time fact not falsified by age | Historical migration observation | Remains active with `valid_from` annotation | G4 |
| **T22** | `test_dispute_blocks_auto_expiration` | Verify disputed memory cannot be auto-expired | Active dispute on expiring memory | Memory retained as active/disputed | G1 |
| **T23** | `test_dispute_blocks_auto_archival` | Verify disputed memory cannot be auto-archived | Active dispute on stale memory | Memory retained until arbitration | G1 |
| **T24** | `test_consolidated_freshness_inheritance` | Verify canonical derives freshness from newest source | Canonical formed from 2 sources | Canonical created_epoch = max(source epochs) | G4 |
| **T25** | `test_unconsolidation_lifecycle_restoration` | Verify unconsolidation restores source lifecycles | `unconsolidate_memory()` | Sources restored to active with proper freshness | G10 |
| **T26** | `test_participant_scope_isolation_sweep` | Verify lifecycle sweep respects G5 scope | Sweep Tenant A | Tenant B memories completely untouched | **G5** |
| **T27** | `test_category_scope_isolation_sweep` | Verify lifecycle sweep respects category | Sweep TASK only | SEMANTIC/PREFERENCE untouched | **G5** |
| **T28** | `test_g8_secret_sanitization_in_events` | Verify no secrets in lifecycle events | Reinforce memory containing sanitized token | Event JSON contains zero secret tokens | **G8** |
| **T29** | `test_observability_audit_ledger` | Verify all transitions append audit rows | Freshness, expiration, archival passes | Audit log rows present for each action | **G9** |
| **T30** | `test_sqlite_wal_atomic_rollback` | Verify transaction rollback on failure | Fault injection during state transition | Complete database rollback; no partial state | **G10/G11** |
| **T31** | `test_lifecycle_idempotency` | Verify repeated expiration sweep is idempotent | Run sweep 3 consecutive times | Zero duplicate events; state unchanged | G4 |
| **T32** | `test_cpu_performance_evaluation` | Verify freshness evaluated in $\le 0.1\text{ ms}$ | 50 candidate freshness evaluations | Total execution time $< 5.0\text{ ms}$ | G4 |
| **T33** | `test_batch_sweep_bounded` | Verify batch sweep bounded to 50 items | 100 eligible memories | Processes exactly 50 per batch chunk | G4 |
| **T34** | `test_procedural_step_sequence_safety` | Verify procedural steps not aged out of order | Procedural steps 1, 2, 3 | All steps maintain consistent decay state | G4 |
| **T35** | `test_retrieval_ranking_freshness_penalty` | Verify STALE memory ranked below FRESH | Query matching FRESH and STALE items | FRESH ranked #1; STALE ranked #2 | G4 |
