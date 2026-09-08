# PHASE 17.8 — TEST PLAN
# 35-SCENARIO VERIFICATION MATRIX

**Document ID**: `P17_8_TEST_PLAN`  
**Phase**: Phase 17.8 (Brud Mini Brain — Memory Recall & Retrieval Intelligence)  
**Status**: TEST PLAN CERTIFIED (STAGE A)  
**Target Test Suite**: `tests/e2e/test_p17_8_memory_recall.py`  

---

## 1. Test Suite Structure & Coverage Strategy

The Phase 17.8 test suite defines 35 distinct end-to-end and unit test cases covering all retrieval modes, semantic/lexical ranking, tie-breaking, freshness decay, consolidation deduplication, dispute gating, multi-tenant isolation, G1/G8 governance, performance, and regression.

---

## 2. Test Execution Plan (35 Test Cases)

| Test ID | Test Scenario | Description & Verification Goal |
|---|---|---|
| **P17_8-001** | `test_p17_8_001_basic_memory_recall` | Standard query retrieves matching active memory items with valid combined scores. |
| **P17_8-002** | `test_p17_8_002_semantic_vector_relevance` | Vector cosine similarity elevates semantically similar memory even with minimal token overlap. |
| **P17_8-003** | `test_p17_8_003_lexical_keyword_relevance` | Exact token match elevates keyword score and overall rank. |
| **P17_8-004** | `test_p17_8_004_score_normalization_bounds` | Score formula stays strictly clamped within $[0.0, 100.0]$ across edge-case inputs. |
| **P17_8-005** | `test_p17_8_005_deterministic_ranking` | Repeated execution with identical inputs produces 100% identical rank ordering. |
| **P17_8-006** | `test_p17_8_006_deterministic_tie_breaking` | Equal scores resolved deterministically by confidence, importance, and lexicographical public ID. |
| **P17_8-007** | `test_p17_8_007_freshness_ranking_boost` | FRESH memories outrank AGING and STALE memories when semantic relevance is comparable. |
| **P17_8-008** | `test_p17_8_008_stale_memory_handling` | STALE memory receives -15 penalty in CURRENT mode but is still retrievable if highly relevant. |
| **P17_8-009** | `test_p17_8_009_expired_memory_exclusion_current` | EXPIRED memory excluded from CURRENT mode recall results. |
| **P17_8-010** | `test_p17_8_010_historical_mode_recall` | HISTORICAL mode successfully retrieves EXPIRED and ARCHIVED memories with zero freshness penalty. |
| **P17_8-011** | `test_p17_8_011_task_mode_recall` | TASK mode confines retrieval strictly to TASK and PROCEDURAL categories. |
| **P17_8-012** | `test_p17_8_012_procedural_ordering_preservation` | Recalled procedural memory items preserve sequence step order. |
| **P17_8-013** | `test_p17_8_013_preference_mode_recall` | PREFERENCE mode prioritizes user preference records without degradation. |
| **P17_8-014** | `test_p17_8_014_consolidated_canonical_recall` | Canonical memory recalled with full provenance metadata (evidence count, sources). |
| **P17_8-015** | `test_p17_8_015_source_deduplication_suppression` | Constituent source memories suppressed when parent canonical memory is retrieved. |
| **P17_8-016** | `test_p17_8_016_provenance_traceability` | Recalled canonical memory permits resolving constituent sources via lineage references. |
| **P17_8-017** | `test_p17_8_017_active_dispute_exclusion_policy` | Dispute policy `exclude_conflicting` strictly excludes memories in active disputes. |
| **P17_8-018** | `test_p17_8_018_pending_review_warning_annotation` | Dispute policy `prefer_recent` returns disputed memory with mandatory advisory warning. |
| **P17_8-019** | `test_p17_8_019_under_review_dispute_handling` | Memory under review handled safely according to conflict policy. |
| **P17_8-020** | `test_p17_8_020_superseded_memory_handling` | Superseded memories excluded from CURRENT mode but retrievable in HISTORICAL mode. |
| **P17_8-021** | `test_p17_8_021_revoked_quarantined_exclusion` | Revoked, quarantined, and rejected memories are strictly excluded across all modes. |
| **P17_8-022** | `test_p17_8_022_participant_scope_isolation` | Tenant A query returns zero memories belonging to Tenant B (G5 isolation). |
| **P17_8-023** | `test_p17_8_023_category_whitelist_isolation` | Retrieval profile `allowed_categories` strictly filters out non-whitelisted categories. |
| **P17_8-024** | `test_p17_8_024_purpose_whitelist_isolation` | Retrieval profile `allowed_purposes` strictly filters out non-whitelisted purposes. |
| **P17_8-025** | `test_p17_8_025_system_category_g1_protection` | SYSTEM memories require explicit profile authorization to be recalled. |
| **P17_8-026** | `test_p17_8_026_admin_category_g1_protection` | ADMIN memories require explicit profile authorization to be recalled. |
| **P17_8-027** | `test_p17_8_027_secret_sanitization_g8` | Query and retrieved memory display values sanitized of credentials and tokens. |
| **P17_8-028** | `test_p17_8_028_candidate_token_budget_bounds` | Max results ($\le 10$) and max token budget ($\le 600$ tokens) strictly enforced. |
| **P17_8-029** | `test_p17_8_029_cpu_performance_benchmark` | Recall evaluation of 50 candidates completes in $< 5.0\text{ ms}$ on CPU. |
| **P17_8-030** | `test_p17_8_030_repeated_query_stability` | Back-to-back queries produce identical results with zero memory drift. |
| **P17_8-031** | `test_p17_8_031_context_topic_task_boost` | Active topic and task boost from Phase 17.2 context intelligence correctly elevates rank. |
| **P17_8-032** | `test_p17_8_032_empty_result_behavior` | Queries with zero matching candidates return graceful empty result without error. |
| **P17_8-033** | `test_p17_8_033_malformed_query_handling` | Empty string, whitespace-only, and special character queries handled safely. |
| **P17_8-034** | `test_p17_8_034_audit_run_recording_integrity` | Successful retrieval records immutable run and result rows in database. |
| **P17_8-035** | `test_p17_8_035_regression_phases_17_2_to_17_7` | Full regression suite across Phases 17.2–17.7 passes with zero regressions. |

---

## 3. Execution Command (Stage B)

```bash
python3 -m pytest tests/e2e/test_p17_8_memory_recall.py -v
```
