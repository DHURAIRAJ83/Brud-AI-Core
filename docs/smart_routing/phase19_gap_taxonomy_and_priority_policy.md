# Phase 19 — Gap Taxonomy & Priority Policy Reference

Source of truth: `core_model/knowledge_gap/__init__.py` (enums),
`core_model/knowledge_gap/eligibility.py` (decision function),
`backend/services/knowledge_gap_priority_service.py` (scoring).

## 1. Event types (10, independent)

| Type | Meaning | Registry-eligible? |
|---|---|---|
| `knowledge_gap` | Factual gap: model didn't know, RAG had no/insufficient evidence, or confirmed-poor answer quality | Yes, reviewable |
| `clarification_event` | First-time ambiguous request | Yes, tracking-only (not reviewable until escalated) |
| `safety_event` | Refusal or safety-block | **No** — recorded elsewhere, never a gap |
| `operational_failure` | Model/RAG/memory/DB/provider issue, or uncertain cause | Yes, ops-visibility only |
| `language_failure` | Wrong output language / language-understanding failure | Yes, reviewable |
| `source_failure` | A specific source became unavailable/rights-blocked | Yes, reviewable |
| `tool_capability_gap` | Tool recommended but unavailable | Yes, capability-demand only |
| `web_capability_gap` | Trusted Web recommended but unavailable | Yes, capability-demand only |
| `feedback_issue` | User feedback signal not otherwise categorized | Yes, reviewable |
| `not_applicable` | Successful answer, disliked without a specific reason, no actionable signal | **No** |

## 2. Reason codes by event type

- `knowledge_gap`: `model_knowledge_missing`, `rag_content_missing`,
  `rag_retrieval_insufficient`, `rag_retrieval_failed`,
  `low_confidence`, `insufficient_evidence`, `outdated_information`,
  `domain_understanding_missing`, `answer_quality_failure`,
  `unresolved_after_clarification`.
- `operational_failure`: `model_unavailable`, `model_timeout`,
  `rag_timeout`, `database_failure`, `provider_failure`,
  `rate_limited`, `internal_error`, `memory_unavailable`.
- `language_failure`: `language_detection_failed`,
  `wrong_output_language`, `tanglish_output_leakage`,
  `mixed_language_policy_failure`, `tamil_quality_failure`,
  `unsupported_language`.
- `safety_event`: `unsafe_operational_request`, `policy_refusal`,
  `output_safety_block`, `prompt_injection_block`,
  `secret_extraction_attempt`, `personal_data_extraction_attempt`.
- `source_failure`: `source_unavailable`, `source_rights_blocked`,
  `source_retrieval_error`.
- `web_capability_gap`: `web_search_unavailable`.
- `tool_capability_gap`: `tool_execution_unavailable`.
- `clarification_event`: `clarification_pending_followup`,
  `clarification_resolved`.
- `feedback_issue` (Step 16, additive — never a DB CHECK-constraint
  value, see §11 of the main doc): `stale_information`,
  `source_conflict`, `unknown_question`, `wrong_answer`,
  `missing_evidence`, `wrong_language`, `unsafe_answer`, `unhelpful`.
- `not_applicable`: `successful_but_disliked`, `user_cancelled_request`,
  `no_actionable_signal`.

## 3. Gap eligibility decision table

Priority order (first match wins) in
`determine_gap_eligibility()`:

1. `safety_status in ("refused","output_blocked")` or
   `output_safety_blocked`/`input_safety_refused` in
   `fallbacks_attempted` → `safety_event`, not eligible,
   `retention_policy="not_retained"`.
2. `resolved_route == "clarify"` → `clarification_event`
   (`review_required=False`) unless `unresolved_after_clarification`
   → `knowledge_gap` reason `unresolved_after_clarification`
   (`review_required=True`).
3. `trusted_web_unavailable` → `web_capability_gap`.
4. `tool_unavailable` → `tool_capability_gap`.
5. `rag_scope_unavailable`/`rag_insufficient_evidence` →
   `knowledge_gap` (`rag_content_missing`/`rag_retrieval_insufficient`).
6. `memory_consent_required` → `not_applicable` (a user choice, not a
   gap). `memory_unavailable` → `operational_failure`.
7. `model_assignment_unavailable`/`classification_failed` →
   `operational_failure` (uncertain cause — never a knowledge gap).
8. A successfully executed route (`core_model`/`approved_rag`/`memory`)
   with a negative-feedback signal → `language_failure` (for
   `wrong_language`), `safety_event` (for `unsafe_answer`, not
   eligible), or `feedback_issue` (everything else). Without negative
   feedback → `not_applicable`, even if evidence/confidence were low
   (Step 14: low confidence alone never auto-captures).
9. Fallback (unmatched insufficient route) → `knowledge_gap`,
   `model_knowledge_missing`.

## 4. Lifecycle

**Status** (14, CHECK-constrained): `new`, `classified`,
`needs_clarification`, `evidence_search`, `answer_draft`,
`review_required`, `rag_trial`, `monitored`,
`training_assessment_candidate`, `resolved`, `rejected`, `blocked`,
`archived`, `deleted_payload`.

**Stage** (13, CHECK-constrained): `capture`, `privacy_processing`,
`classification`, `deduplication`, `prioritization`, `research`,
`drafting`, `human_review`, `rag_handoff`, `monitoring`,
`training_handoff`, `resolution`, `retention`.

Review-decision → status/stage transition table
(`KnowledgeGapReviewService._TRANSITIONS`):

| Decision | Status | Stage |
|---|---|---|
| `confirm_gap` | `review_required` | `research` |
| `reclassify` | `classified` | `classification` |
| `keep_separate` | `classified` | `classification` |
| `needs_evidence` | `evidence_search` | `research` |
| `send_to_rag_research` | `rag_trial` | `rag_handoff` |
| `send_to_evaluation` | `monitored` | `monitoring` |
| `mark_training_assessment_candidate` | `training_assessment_candidate` | `training_handoff` |
| `reject` | `rejected` | `resolution` |
| `block` | `blocked` | `resolution` |
| `archive` | `archived` | `retention` |
| `merge`, `resolve` | (handled by `KnowledgeGapMergeService`/`KnowledgeGapResolutionService`) | |

## 5. Clustering decisions

`same_case` (exact canonical match, auto), `probable_duplicate`
(normalized-checksum match, auto), `possible_duplicate` (Jaccard
word-shingle ≥ 0.85, **always requires Admin review**), `distinct`,
`needs_review`. Candidates are bucketed by `(domain, intent,
freshness)` before any comparison — `language` is deliberately
excluded from the bucket key so a Tamil-suffixed question and its
plain-English equivalent remain comparable (per Step 7's own worked
example), while a different `intent` always keeps two questions apart
regardless of surface similarity.

## 6. Priority scoring

`priority_score` (float, unbounded but practically 0-40) →
`priority_band` via fixed thresholds: `critical` ≥ 30, `high` ≥ 20,
`medium` ≥ 10, `low` ≥ 3, else `informational`.

Positive contributions: `frequency_weighted` (0.75/occurrence, capped
at 20), one of `recency_within_1_day` (+10) /
`recency_within_1_week` (+6) / `recency_within_1_month` (+3),
`feedback_severity_<reason>` (2-10 depending on reason), one
`route_failure_severity_<event_type>` (1-8), `repeated_rag_failure`
(+2/occurrence, capped at 5), `repeated_wrong_language_failure`
(+2/occurrence, capped at 5), `TAMIL_FIRST_PRIORITY_APPLIED` (+6, see
§7).

Negative contributions (penalties): `penalty_duplicate_uncertainty`
(-4), `penalty_privacy_risk` (-6), `penalty_low_reproducibility` (-5),
`penalty_no_available_source` (-2, `knowledge_gap` only). Score is
floored at 0.

## 7. Tamil-first priority boost

Gated by `TAMIL_FIRST_PRIORITY_REASON_CODES` (a strict allowlist):
`tamil_grammar`, `tamil_meaning`, `tamil_orthography`,
`tamil_instruction_following`, `tanglish_comprehension`,
`tamil_output_language_failure`, `tamil_ambiguity_handling`. These are
populated onto a case's `reason_codes` by
`KnowledgeGapCaptureService._augment_with_tamil_capability_reason_codes()`
from Phase 17's own `tamil_language` domain classification
(`tamil_grammar`/`tamil_orthography`/`tamil_meaning` subdomains map
1:1) or from a `wrong_output_language` feedback signal on a Tamil-
language response. **A Tamil current-affairs question never receives
this boost** — its event type is `web_capability_gap`/`knowledge_gap`
with a freshness-driven reason code, never one of the seven allowlisted
capability codes, enforced by a disjoint-set check and proven by a
dedicated regression test (`test_tamil_current_affairs_does_not_get_
tamil_boost`).

## 8. Resolution types (15, descriptive only)

`answered_by_existing_model`, `resolved_by_routing_rule`,
`resolved_by_approved_rag`, `requires_trusted_web`, `requires_tool`,
`requires_translation`, `requires_language_policy_fix`,
`requires_safety_policy_fix`, `requires_operational_fix`,
`evaluation_case_created`, `future_training_assessment`,
`not_reproducible`, `duplicate_resolved`, `rejected`, `blocked`.
Recording any of these never performs the described action.

## 9. RAG/training handoff eligibility rules

**RAG research eligible** requires all of: `event_type == "knowledge_gap"`,
content available (not `content_unavailable_for_review`), a canonical
question exists, at least one reason code in `{rag_content_missing,
rag_retrieval_insufficient, domain_understanding_missing,
model_knowledge_missing}`, and `freshness` **not** in
`{time_sensitive, real_time}`. RAG trial-proposal-eligible additionally
requires `frequency >= 2` (reproducibility).

**Training-assessment eligible** requires: `event_type` not in
`{web_capability_gap, tool_capability_gap, operational_failure,
safety_event, source_failure}`, content available, `frequency >= 2`,
`freshness` not volatile, and at least one reason code in
`{tamil_grammar, tamil_meaning, tamil_orthography,
tamil_instruction_following, tanglish_comprehension,
tamil_ambiguity_handling, wrong_output_language,
domain_understanding_missing, answer_quality_failure}`.
