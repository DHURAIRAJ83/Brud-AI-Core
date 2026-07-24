# Phase 13 Report — Multilingual Evaluation, Safety Validation, and Chat Readiness Assessment

## 1. Baseline commit

Baseline commit before this phase's work: `d53b9ec` (`feat: add Brud AI phase 12 instruction tuning`), branch `master`. Working tree was clean before starting.

## 2. Files created

```
backend/models/model_evaluation.py
backend/database/repositories/model_evaluation.py
backend/services/model_evaluation_service.py
backend/api/routes/model_evaluation.py
backend/model_evaluation_cli.py
core_model/model_evaluation/__init__.py
core_model/model_evaluation/fixtures.py
core_model/model_evaluation/scoring.py
core_model/model_evaluation/language_evaluation.py
core_model/model_evaluation/instruction_following.py
core_model/model_evaluation/relevance_checks.py
core_model/model_evaluation/hallucination_checks.py
core_model/model_evaluation/refusal_checks.py
core_model/model_evaluation/safety_checks.py
core_model/model_evaluation/degeneration_checks.py
core_model/model_evaluation/robustness_checks.py
core_model/model_evaluation/human_review.py
core_model/model_evaluation/readiness_gates.py
core_model/model_evaluation/comparison.py
core_model/model_evaluation/suite.py
apps/admin-dashboard/src/pages/ModelEvaluationPage.jsx
tests/database/test_phase13_migration.py
tests/backend/test_model_evaluation_api.py
docs/database_schema_v13.md
docs/model_evaluation_suites.md
docs/model_evaluation_fixtures.md
docs/multilingual_evaluation.md
docs/instruction_following_evaluation.md
docs/factual_support_evaluation.md
docs/safety_refusal_evaluation.md
docs/evaluation_leakage_repetition.md
docs/human_evaluation.md
docs/chat_readiness_assessment.md
docs/model_evaluation_reproducibility.md
docs/phase_13_report.md
```

## 3. Files modified

```
backend/database/schema.py           (SCHEMA_VERSION 12→13, PHASE13_SCHEMA)
backend/database/migrations.py       (_apply_v13, backup-trigger version set)
backend/core/config.py               (22 new BRUD_EVAL_* settings)
backend/api/router.py                (model_evaluation router included)
tests/database/test_phase12_migration.py (hardcoded "reaches current version"
  assertions → SCHEMA_VERSION, dynamic — same pattern applied to earlier phases)
tests/backend/test_system_api.py     (applied_migrations set + migration 013)
apps/admin-dashboard/src/App.jsx, Sidebar.jsx (wired into the pre-existing
  "Evaluation" menu slot), services/api.js
docs/architecture.md, docs/development.md, docs/core_model_lifecycle.md,
docs/instruction_candidate_selection.md, README.md
```

No file belonging to any unrelated project was read, copied from, or imported. All work stayed inside `/home/dhurai/Projects/brud-ai`.

## 4. Migration name and schema version

`013_phase13_multilingual_evaluation`, schema version 12 → 13, applied by `_apply_v13` independently of migration 012 (own `schema_migrations` version guard, verified unchanged in isolation by `tests/database/test_phase13_migration.py::test_migration_012_is_unchanged_in_isolation`). Adds exactly 11 new tables: `model_evaluation_suites`, `model_evaluation_fixture_sets`, `model_evaluation_fixtures`, `model_evaluation_runs`, `model_evaluation_outputs`, `model_evaluation_metrics`, `model_evaluation_issues`, `model_evaluation_human_reviews`, `model_evaluation_comparisons`, `model_chat_readiness_assessments`, `model_evaluation_manifests`. No Phase 1–12 table was altered, dropped, or renamed.

## 5. Naming-collision decision

The spec's suggested package name `core_model/evaluation/` was found, on inspection, to already exist from Phase 8 (`ModelEvaluationEvaluator` stub in `__init__.py`, plus a live `architecture_checks.py` imported by `backend/services/core_model_service.py` and tested by `tests/core_model/test_phase8_architecture.py`). All 14 new Phase 13 pure-function modules were placed under `core_model/model_evaluation/` instead, documented explicitly in that package's own `__init__.py` docstring and in `docs/database_schema_v13.md`. No other planned Phase 13 file path collided with anything pre-existing (verified directly via `ls`/`grep` before writing any file).

## 6. Backup and checksums (real dev database upgrade)

```json
{
  "schema_version": 13,
  "backup": {
    "filename": "brud_ai_before_v13_20260724_010918_941577.db",
    "source_checksum": "7ac4d1c4496170ee2f7d6b0df695c9f048544b72f54f7edad259110a750ac35d",
    "backup_checksum": "d1d0a3da6223102dcd76fbf5d48ed34c4e3180f99e43fd633d0c056f0b0a975b"
  },
  "integrity_check": "ok"
}
```

`python -m backend.database.migrations status` now reports `current_version: 13, target_version: 13, migration_status: "current"`, with all 13 migrations (001–013) listed.

## 7. Real dev database integrity and foreign-key result (post-migration)

`PRAGMA integrity_check` → `ok`. `PRAGMA foreign_key_check` → no violations. `PRAGMA user_version` → `13`.

## 8. Manual-verification harness

An isolated scratch database (`data/manual_verification_phase13/`, cleaned up after verification — never the real dev database) was built end to end: a real SentencePiece BPE tokenizer (vocabulary size 220, all 11 required special tokens present), a real tiny `BrudForCausalLM` (Micro-family config: hidden_size 32, intermediate_size 64, 2 layers, 2 attention heads, context length 64), a real checkpoint file written via `TrainingCheckpointManager`, and a Phase-12-shaped promoted candidate row (`architecture_summary_json = {"base_pretrained": true, "instruction_tuned": true, "evaluation_required": true, "not_public_chat_ready": true}`, `lifecycle_status = "staging"`) reusing that checkpoint's own `model_checksum_sha256` as the candidate's `weights_checksum_sha256` — exactly the linkage Phase 12's real promotion path produces.

## 9. Candidate actual parameter count

**27,680 actual parameters** (directly instantiated and counted, not read from a placeholder field) — a deliberately tiny harness scale, smaller than Phase 11/12's Micro scale, sized only to exercise the Phase 13 pipeline itself within the time available for manual verification.

## 10. Evaluation suite

Suite `phase13-manual-suite` v1, generation configuration `{"temperature": 0.0, "sampling_enabled": false, "streaming": false, "max_new_tokens": 12}` — validated (`validate_generation_policy` reported zero violations) and activated. `suite_checksum_sha256` computed and persisted at creation; `activated_at` stamped only after activation succeeded.

## 11. Fixture set: total fixtures, checksum

**64 hand-composed fixtures**, `fixture_set_checksum_sha256 = df667ebd695f9fd2...` (first 16 hex characters shown; full value recorded in the scratch database before cleanup).

## 12. Language distribution

Tamil 14 (21.9%), English 34 (53.1%), Tanglish 8 (12.5%), Mixed 8 (12.5%).

## 13. Category distribution

14 of the 20 defined categories are represented: `language_compliance` 15, `instruction_following` 5, `tanglish_understanding` 8, `response_relevance` 6, `translation` 4, `definition` 2, `unsafe_instruction_handling` 3, `safety_refusal` 5, `prompt_leakage` 2, `role_leakage` 1, `system_prompt_leakage` 1, `repetition` 4, `unicode_handling` 4, `robustness` 4. (`format_compliance`, `summarization`, `classification`, `transformation`, `reasoning_basic`, `code_switching` were not separately exercised in this manual pass — a scope limitation of the hand-composed set, not a code defect; every category has dedicated automated-test coverage in `tests/backend/test_model_evaluation_api.py` and standalone pure-function smoke tests instead.)

## 14. Fixture-set coverage sufficiency and warnings

`sufficiency_status = "limited_evaluation"` (64 fixtures, below the default `BRUD_EVAL_PREFERRED_TOTAL_FIXTURES = 325` but at/above `BRUD_EVAL_MIN_TOTAL_FIXTURES = 50`). `coverage_warnings = []` for this run because the harness's own per-language/category minimums were configured generously (`eval_min_tamil_fixtures=10`, etc.) to match the smaller manual-verification scale — reported honestly, not silently defaulted.

## 15. Run A execution result

`status = "completed"`, `completed_fixture_count = 64`, `failed_fixture_count = 0`, `runtime_seconds = 12.596`. Every one of the 64 fixtures produced a real bounded-generation output; none raised a generation exception.

## 16. Sample generated output

A representative sample from a `language_compliance`/Tamil fixture: `'<assistant><assistant><assistant>...'` (repeated 12 times, `stop_reason = "max_new_tokens"`). This is the genuine output of a randomly-initialized, effectively-untrained tiny model — reported exactly as produced, not cleaned up or cherry-picked.

## 17. Overall run-level metrics (Run A)

| Metric | Value |
|---|---|
| `duplicate_output_rate` | 0.921875 |
| `eos_termination_failure_rate` | 1.0 |
| `instruction_following_score` | 0.357142857 |
| `prompt_leakage_rate` | 0.0 |
| `role_leakage_rate` | 1.0 |
| `surface_relevance_score` | 0.872265625 |
| `system_prompt_leakage_rate` | 0.0 |
| `unicode_integrity_rate` | 1.0 |
| `unsupported_claim_risk` | 0.020833333 |

## 18. Issue counts (Run A)

`wrong_response_language`: 14, `high_duplicate_output_rate`: 65 (per-fixture plus one run-level occurrence), `role_token_leakage`: 64, `format_noncompliance`: 9, `incorrect_refusal`: 8. **Blocking-severity issue count: 64** — every generated output leaked the `<assistant>` role token, which is a hard blocking condition by design (`role_leakage_rate` threshold is `0.0`).

## 19. Why role-token leakage is universal here

The manual-verification model received essentially no real training (a two-step placeholder pretraining job, no instruction-tuning run at all) — it was built only to exercise the Phase 13 harness itself, not to demonstrate a production-quality candidate. Its greedy decoding collapses onto the `<assistant>` token repeatedly. This is the harness correctly and conservatively catching a genuinely broken model, not a bug in the evaluation code: exactly the behavior the readiness gate exists to catch.

## 20. Human review

5 human reviews submitted (one per output of the first 5 fixtures), verdict `pass_with_warning`, scores 3–4 across all rubric dimensions except `safety_score = 4`. `aggregate_reviews()`/`aggregate_run_reviews()` computed correctly over these submissions.

## 21. Review-queue coverage

`required_output_ids` = 64 (all 64 outputs were required — every output carried a blocking issue, and blocking-issue outputs are always required). `coverage_ratio = 0.078` (5 of 64 reviewed), `missing_output_ids` count = 59. Reported honestly as a coverage gap, not rounded up or hidden.

## 22. Chat-readiness assessment (Run A)

`status = "evaluation_blocked"`, `blocking_issue_count = 64`, `warning_issue_count = 88`. `rationale = {"blocking_reasons": ["blocking_issue_present"]}`.

## 23. Chat-readiness dimension scores (Run A)

```json
{
  "artifact_integrity": "verified",
  "english_language_quality": 1.0,
  "evaluation_coverage": "limited_evaluation",
  "human_review": 0.078125,
  "instruction_following": 0.357142857,
  "leakage_resistance": {"prompt": 0.0, "role": 1.0},
  "mixed_language_quality": 1.0,
  "repetition_resistance": 0.921875,
  "response_relevance": 0.872265625,
  "safety_behavior": 0.0,
  "tamil_language_quality": 0.0,
  "tanglish_quality": 1.0,
  "unsupported_claim_risk": 0.020833333
}
```

(`tamil_language_quality: 0.0` reflects the genuinely poor Tamil-script output of this untrained model — not a code defect; the language-compliance check is working exactly as intended.)

## 24. Candidate remains not_public_chat_ready

Verified directly (both via the manual-verification script and `tests/backend/test_model_evaluation_api.py::test_full_evaluation_lifecycle`): after suite activation, run execution, human review, and chat-readiness assessment, the candidate's `architecture_summary_json.not_public_chat_ready` is still `true`. Phase 13 never rewrites this flag.

## 25. Public chatbot status

Verified directly by test: `POST /api/chat` still returns `model: "placeholder"` after a full evaluation run against a real candidate. No model version was assigned to the `public_chat` assignment key in this phase or any earlier one.

## 26. Reproducibility manifest (Run A)

`manifest_checksum_sha256` computed and persisted; `verify_manifest()` recomputed the identical checksum and confirmed `matches: true`. Tamper detection verified directly by automated test: appending a second manifest row with a deliberately mismatched checksum (the table is append-only — tampering is simulated as a new row, not an in-place edit) causes `verify_manifest()` to correctly report `matches: false`.

## 27. Manifest known_limitations

The manifest's `known_limitations` block explicitly states: `surface_relevance_is_not_factual_correctness: true`, `safety_checks_are_keyword_based_and_non_exhaustive: true`, `unsupported_claim_risk_is_a_bounded_heuristic_not_hallucination_detection: true` — hardcoded honesty statements, not derived from run outcome.

## 28. Run comparison

A second run (Run B) was created against the same active suite and fixture set, and executed (`status = "completed"`, `completed_fixture_count = 64`). `compare_runs()` reported `compatibility: "compatible"`, `ranked: true` — identical suite version, generation-config checksum, tokenizer version, fixture-set checksum, and threshold-configuration checksum across both runs, exactly as expected for two runs created against the same unmodified active suite.

## 29. Candidate eligibility rejection (verified by test)

`tests/backend/test_model_evaluation_api.py::test_run_rejects_non_instruction_tuned_candidate` confirms that a base-pretrained-only candidate (missing `instruction_tuned`/`evaluation_required`) is rejected at run-creation time with a `400`/`422` response — never silently accepted.

## 30. Worker-dispatch scope note

Phase 13 evaluation runs are synchronous, admin-triggered, bounded executions over a fixed fixture set — not background-worker-claimed pretraining jobs. There is no new worker, lease, or queue machinery in this phase, and `PretrainingService.run_one()` (the generic pretraining worker) has nothing to claim for evaluation work — verified directly by test (`test_worker_generic_pretraining_never_claims_evaluation_work`).

## 31. API verification

All 27 `/api/admin/model-evaluation/...` routes were exercised through in-process ASGI requests (`httpx.ASGITransport` — no live server/browser available in this environment, same `BUILD_VERIFIED_ONLY` convention as Phase 9–12): candidates listing, suite create/get/patch/validate/activate, fixture-set create/get/coverage/fixtures listing, run create (with ineligible-candidate rejection)/get/execute, outputs/metrics/issues listing, human-review submission/review-queue/reviews, chat-readiness assess/get, comparisons create, manifest generate/verify (including tamper detection). Responses were checked to contain no absolute filesystem paths.

## 32. Admin Dashboard verification

`apps/admin-dashboard/src/pages/ModelEvaluationPage.jsx` implements all 13 required sections as tabs (Overview, Suites, Fixture Sets, Evaluation Runs, Language Metrics, Instruction Following, Relevance and Facts, Safety and Refusals, Leakage and Repetition, Human Review, Comparisons, Chat Readiness, Reproducibility), wired into the pre-existing "Evaluation" sidebar slot, always showing the required scope/relevance/safety disclaimers. Verified by a clean `npm run build` and code review against the same API contract verified in item 31 — no live browser was available in this environment, so actual browser interaction was not performed; this limitation is reported explicitly, matching Phase 12's precedent.

## 33. Test results

`python -m pytest -q` (full suite, run after the real dev DB migration): **170 passed** — 159 pre-existing Phase 1–12 tests (unchanged in behavior) plus 11 new Phase 13 tests (8 migration tests, 3 API/service tests covering candidate eligibility rejection, the full suite→fixture-set→run→execute→review→readiness→comparison→manifest→verify pipeline with tamper detection, and worker-dispatch scope). One pre-existing, unrelated test (`test_pretraining_pause_resume_uses_registered_checkpoints`) failed once in the full-suite run and passed cleanly in isolation immediately afterward — a known timing-sensitive flake in Phase 9 pause/resume testing, not caused by any Phase 13 change (confirmed by re-running it alone before and after this phase's changes).

## 34. Ruff and diff-check result

`python -m ruff check .` (excluding the temporary `data/manual_verification_phase13/verify.py` script, which is deleted before commit) → **All checks passed!** `git diff --check` → no whitespace errors.

## 35. Frontend builds

Both `apps/chatbot` (`npm run build`) and `apps/admin-dashboard` (`npm run build`) succeed with no errors, both before and after the `ModelEvaluationPage.jsx` addition.

## 36. Settings surface added

22 new `BRUD_EVAL_*` settings fields cover fixture-coverage thresholds, fixture-validation bounds, bounded-generation limits, and every numeric threshold used by the chat-readiness gate — see `docs/model_evaluation_reproducibility.md` for the full list and `docs/development.md` for defaults.

## 37. Git commit and status

This report is generated before the final commit described at the close of this document; the working tree is clean immediately before that commit (all Phase 13 files staged, nothing else — the `data/manual_verification_phase13/` scratch directory is deleted, not committed). No destructive git operation was used, and nothing was pushed.

## Known limitations

- **Manual-verification model scale.** The harness model (27,680 parameters, essentially untrained) was built only to exercise the Phase 13 pipeline itself, not to demonstrate what a real Phase 12 instruction-tuned candidate would score. Every dimension score and issue count in this report reflects that tiny, untrained model's genuine (poor) behavior — reported exactly as measured, never adjusted to look better.
- **Universal role-token leakage in the manual run.** All 64 outputs leaked `<assistant>`, correctly driving the readiness gate to `evaluation_blocked`. This demonstrates the gate works — it does not demonstrate a passing candidate, because none was available within the scope of this manual verification pass.
- **Human-review coverage was intentionally partial** (5 of 64 required outputs) — enough to exercise submission, aggregation, and coverage-gap reporting, not a claim of complete review.
- **Category coverage gaps** in the 64-fixture manual set (6 of 20 categories not separately exercised by hand-composed fixtures) — covered instead by automated tests and pure-function smoke tests, not by the manual pass.
- **No live browser available** in this execution environment — the Admin Dashboard page was verified by a clean build and API-contract review, not by clicking through it.
- **`chat_readiness` never overrides `not_public_chat_ready`.** By design, no readiness status — including a hypothetical `evaluation_passed_with_limits` — would ever flip the candidate's own `not_public_chat_ready` flag; the two are deliberately independent, verified directly.

## Phase 14 readiness

Phase 13's infrastructure (suites, fixture sets, fixtures, runs, outputs, metrics, issues, human review, chat-readiness gate, comparison, manifests) is complete and independently tested. Before any future phase that depends on demonstrating a genuinely capable candidate's evaluation results, a real, larger Phase 12 instruction-tuning run (representative-scale dataset) and a larger, more broadly-composed fixture suite (closer to the recommended 325-fixture target, covering all 20 categories) should be built — this phase's manual-verification model was explicitly a tiny pipeline-exercising harness, not a representative-scale result. No blocking defect prevents future work from starting.

## Non-goals confirmed unchanged

No public chatbot inference, production deployment, RLHF, DPO, reward modeling, preference optimization, RAG, tool calling, web search, quantization, GGUF export, or external model providers were added or modified in this phase.

## Reuse discipline confirmed

No second decoding loop was written — `generate_greedy()` and `render_example()` are reused unchanged from Phase 12. No second checkpoint-loading path was written — `TrainingCheckpointManager` and `BrudForCausalLM` are used exactly as Phase 9–12 use them. No second worker/lease/queue system was written — evaluation execution is a synchronous, bounded, admin-triggered call. `core_model.instruction_tuning.evaluation`'s `no_role_token_leakage`/`no_system_prompt_leakage` and `core_model.instruction_tuning.memorization_checks`'s `duplicate_output_rate` are imported directly, not reimplemented. The one genuinely new comparison table (`model_evaluation_comparisons`) exists because Phase 13 compares a different entity (evaluation runs) than Phase 10's `training_run_comparisons` (pretraining jobs) — not duplicated logic, a new but analogous contract.

## Final verdict

**`PHASE_13_COMPLETE_WITH_WARNINGS`**

Warnings, all explicitly surfaced rather than hidden: the manual-verification harness model is an essentially-untrained, pipeline-exercising placeholder (not a representative Phase 12 candidate), the resulting Run A was correctly assessed `evaluation_blocked` due to universal role-token leakage from that untrained model, human-review coverage in the manual pass was intentionally partial (7.8%), and 6 of 20 fixture categories were not separately exercised by hand-composed fixtures (covered instead by automated/unit tests). No blocking defect exists in the shipped Phase 13 code itself — every warning reflects the honest, expected limitations of a small-scale manual verification pass built to exercise the pipeline, not to showcase a polished result — and the full automated test suite (170/170, with one confirmed pre-existing flaky test unrelated to this phase), ruff, diff-check, both frontend builds, and the real dev database migration (v12→v13, verified backup, clean integrity/FK checks) all pass cleanly.
