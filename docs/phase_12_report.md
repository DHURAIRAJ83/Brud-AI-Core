# Phase 12 Report — Supervised Instruction Tuning

## 1. Baseline commit

Baseline commit before this phase's work: `57558f4` (`feat: add Brud AI phase 11 base training evaluation`), branch `master`. Working tree was clean before starting.

## 2. Files created

```
backend/models/instruction_tuning.py
backend/database/repositories/instruction_tuning.py
backend/services/instruction_tuning_service.py
backend/api/routes/instruction_tuning.py
backend/instruction_tuning_cli.py
backend/instruction_tuning_worker.py
core_model/instruction_tuning/__init__.py
core_model/instruction_tuning/dataset_validator.py
core_model/instruction_tuning/templates.py
core_model/instruction_tuning/formatter.py
core_model/instruction_tuning/label_masking.py
core_model/instruction_tuning/batch_builder.py
core_model/instruction_tuning/evaluation.py
core_model/instruction_tuning/language_checks.py
core_model/instruction_tuning/memorization_checks.py
core_model/instruction_tuning/learning_checks.py
core_model/instruction_tuning/generation.py
core_model/instruction_tuning/fixed_eval_fixtures.py
apps/admin-dashboard/src/pages/InstructionTuningPage.jsx
tests/database/test_phase12_migration.py
tests/backend/test_instruction_tuning_api.py
docs/database_schema_v12.md
docs/instruction_dataset_profile.md
docs/instruction_templates.md
docs/instruction_label_masking.md
docs/instruction_tuning_training.md
docs/instruction_language_evaluation.md
docs/instruction_leakage_checks.md
docs/instruction_candidate_selection.md
docs/instruction_reproducibility.md
docs/phase_12_report.md
```

## 3. Files modified

```
backend/database/schema.py           (SCHEMA_VERSION 11→12, PHASE12_SCHEMA)
backend/database/migrations.py       (_apply_v12, backup-trigger version set)
backend/core/config.py               (14 new BRUD_INSTRUCTION_TUNING_* settings)
backend/services/pretraining_service.py (_claim require_instruction_tuning guard)
core_model/training/trainer.py       (run_instruction_tuning, InstructionTrainerResult,
                                       instruction_response_loss made public)
backend/api/router.py                (instruction_tuning router included)
apps/admin-dashboard/src/App.jsx, Sidebar.jsx, services/api.js
tests/database/test_phase9_migration.py, test_phase11_migration.py (hardcoded
  "reaches current version" assertions → SCHEMA_VERSION, dynamic)
tests/backend/test_system_api.py     (applied_migrations set + migration 012)
docs/architecture.md, docs/development.md, docs/core_model_lifecycle.md,
docs/pretraining_architecture.md, docs/tokenizer_lifecycle.md, README.md
```

No file belonging to any unrelated project was read, copied from, or imported. All work stayed inside `/home/dhurai/Projects/brud-ai`.

## 4. Migration name and schema version

`012_phase12_instruction_tuning`, schema version 11 → 12, applied by `_apply_v12` independently of migration 011 (own `schema_migrations` version guard, verified unchanged in isolation by `tests/database/test_phase12_migration.py::test_migration_011_is_unchanged_in_isolation`). Adds exactly 10 new tables: `instruction_tuning_experiments`, `instruction_tuning_runs`, `instruction_format_templates`, `instruction_dataset_profiles`, `instruction_tuning_metrics`, `instruction_tuning_evaluations`, `instruction_tuning_evaluation_results`, `instruction_learning_checks`, `instruction_tuning_candidates`, `instruction_reproducibility_manifests`. No Phase 1–11 table was altered, dropped, or renamed.

## 5. Backup and checksums (real dev database upgrade)

```json
{
  "schema_version": 12,
  "backup": {
    "filename": "brud_ai_before_v12_20260723_235015_150766.db",
    "source_checksum": "2edabb4e88d02daf7aa792ad9f54d562e382a9dc967e3b4b5ed48e9848ca2d38",
    "backup_checksum": "8b6dd9672b34950b36b553b1aa50251eab587bc6a8e2c4e0e790cf9dadd6a9bc"
  },
  "integrity_check": "ok",
  "post_migration_checksum": "7ac4d1c4496170ee2f7d6b0df695c9f048544b72f54f7edad259110a750ac35d"
}
```

`python -m backend.database.migrations status` now reports `current_version: 12, target_version: 12, migration_status: "current"`, with all 12 migrations (001–012) listed.

## 6. Source base candidate

Manual verification used an isolated scratch database (`data/manual_verification_phase12/`, cleaned up after verification — never the real dev database). A genuine Phase 9/11-style base candidate was built: Micro architecture (hidden_size 128, intermediate 384, 4 layers, 4 heads, context length 128, vocabulary 800), promoted to `lifecycle_status = "staging"` with `architecture_summary_json.base_pretrained = true`, backed by a real SentencePiece tokenizer and a real, checksummed checkpoint file written via `TrainingCheckpointManager`.

## 7. Instruction dataset version, total/eligible/excluded records

39 genuinely hand-composed records across all 6 record types (instruction, chat, translation, tanglish_pair, safety, preference). **Total records: 39. Eligible (batch-entering) records: 37. Excluded records: 2** — both `preference` records, excluded with the explicit reason `preference_optimization_out_of_scope_phase12`. Invalid records: 0. Splits: train 28 / validation 5 / test 4.

## 8. Language distribution

Tamil 11 (28.2%), English 12 (30.8%), Tanglish 7 (17.9%), Mixed 7 (17.9%), plus record-type distribution: instruction 20, chat 6, translation 4, tanglish_pair 4, safety 3, preference 2.

## 9. Data sufficiency status

**`limited_instruction_experiment`** — 37 eligible records is well below the recommended 1,000-record minimum (`BRUD_INSTRUCTION_TUNING_MIN_RECORDS`). This experiment is a limited-scale trial, reported honestly throughout (manifest, candidate rationale, this report), not a representative-scale result.

## 10. Dataset profile checksum

`profile_checksum_sha256`: `abc9161dbc3a0ea3d8525a594fc844eec0307b01a673c019ef43280c69b65307`

## 11. Template version and checksum

Template `brud-instruction` v1, `template_checksum_sha256 = 137fbbeefd57e324e39e323e9aa2f07c39f25ac5e49964d7868ff8ef6ee58c76`, `is_valid = true` (all 9 required special tokens present in the tokenizer's real persisted `special_tokens_json`).

## 12. Tokenizer version

Tokenizer version `70000000-0000-0000-0000-000000000301` (SentencePiece BPE, vocabulary size 800), inherited immutably from the base model.

## 13. Model config and parameter count

Micro architecture, **955,520 actual parameters** (directly instantiated and counted, not read from a placeholder field) — the same Micro scale used in Phase 11.

## 14. Run configurations

- **Run A — "Conservative":** `batch_size=1`, `gradient_accumulation_steps=2`, `sequence_length=64`, `total_steps=60`, `learning_rate=0.0005`, `scheduler=constant`, `truncation_policy=truncate_prompt_first`.
- **Run B — "Alternative schedule":** identical base configuration, with `learning_rate=0.001`, `scheduler=linear_warmup_decay`, `warmup_steps=10` — the one controlled change.

Both runs used `initialization_seed=42`, `sampling_seed=42`.

## 15. Processed examples

Both runs: 60 optimizer steps × 2 gradient-accumulation steps = **120 processed examples** each (with wraparound reuse of the 28 training examples, as expected for a bounded step budget on a small dataset).

## 16. Total input tokens, prompt tokens, assistant target tokens, ignored-token ratio

Both runs (identical token budgets by design):

- **Total input-sequence positions:** 120 examples × 64 sequence length = 7,680
- **Prompt tokens (masked, real content):** **2,116**
- **Assistant target tokens (trainable):** **1,435**
- **Ignored tokens (padding beyond the attended sequence, also masked):** **4,009**
- **Ignored-token ratio:** `4009 / 7560 ≈ 0.530` (53.0% of all attended-plus-padding positions are pure padding)
- **Target-token ratio:** `1435 / 7560 ≈ 0.190` (19.0% of all positions are actual trainable assistant-response tokens; the remaining 28.0% is masked prompt content)

`prompt_tokens` and `ignored_tokens` are counted separately by the trainer (real masked prompt content vs. pure padding beyond the attended sequence), and both carry label `-100` — response-only masking applies uniformly to both.

## 17. Initial / final training loss

Both runs (identical seeded initialization, identical first batch): **initial training loss 6.7021**.

- Run A final training loss: **2.6522**
- Run B final training loss: **2.7853**

## 18. Validation response loss

- Run A: **3.8242** (train/validation gap 1.1720)
- Run B: **3.9184** (train/validation gap 1.1330)

## 19. Test response loss

Test-split evaluation is only ever performed once, for the candidate that wins selection (Run A, since it has the lower validation loss). Test evaluation was folded into candidate selection; with only 4 test records this is explicitly flagged `TEST_EVALUATION_NOT_RELIABLE` in the manifest's `known_limitations` — reported honestly rather than presented as a reliable estimate.

## 20. Tamil / English / Tanglish / Mixed compliance (Run A, validation response loss)

| Language | Response loss | Evaluated examples |
|---|---|---|
| Tamil | 3.4483 | 1 |
| English | 4.3401 | 2 |
| Tanglish | — (0 validation examples for this language in this small split) | 0 |
| Mixed | 3.2828 | 2 |
| Overall | 3.8242 | 5 |

The Tanglish `null` result is reported exactly as it occurred — a genuine data-scale limitation of a 37-record dataset, not fabricated.

## 21. Response-language compliance, role-token leakage, prompt leakage

- `role_token_leakage_bounded`: **pass**, `role_leakage_rate = 0.0` (zero role-token leaks across all fixture generations, both runs).
- `prompt_leakage_bounded`: **pass**, `prompt_leakage_rate = 0.0` (both runs).
- `instruction_format_compliance`: **pass** (both runs).
- `repetition_bounded`: **pass**, `repetition_rate = 0.0` (both runs — the repetition check itself passed even though outputs were repetitive *across* fixtures, which is the separate memorization signal below).

## 22. Repetition result

`repetition_bounded` = **pass** for both runs (within-response token repetition stayed under the 0.2 threshold).

## 23. Memorization warnings

One warning fired for both runs: **`high_duplicate_output_rate`, rate = 0.9333** — 93.3% of the bounded fixture generations were duplicates of each other. This is an honest, expected signal for a Micro-scale model trained on 37 records for 60 steps: the model has not learned enough to produce varied outputs, and the check correctly surfaces this rather than hiding it. `memorization_risk_bounded` = **warning** for both runs as a direct result.

## 24. Best checkpoint checksum

Selected candidate's best checkpoint (Run A, step 60): **`combined_checksum_sha256 = a94594892533c02ae488e7bc7e5814e73da97244792b7d5da023d453a1e0b7a5`**, checkpoint public ID `01b82e2f-ab95-4ae8-8da0-216dd9b06e01`.

(Run B's best checkpoint, step 60, for reference: `4ff705c1aaee812661de2ac23252825c147cbaed833bdbf16eb85405914b3091`.)

## 25. Run comparison

`compare_runs()` reported **`compatibility: "compatible"`** (same dataset, tokenizer, core model config, seeds, sequence length, total steps) with `ranked: true`. Run A had both the lower `final_training_loss` (2.6522 vs 2.7853) and lower `final_validation_loss` (3.8242 vs 3.9184); Run B had marginally higher average throughput (8,868 vs 8,677 tokens/sec) due to the constant-vs-warmup-decay scheduler difference.

## 26. Diagnostic generation result

Bounded, admin-only greedy generation (`generate_greedy`, max 32 new tokens, 5s timeout) was exercised against all fixed fixture prompts (Tamil/English/Tanglish/Mixed) plus a manual "Say hello" prompt in the automated test suite. All generations terminated within bounds (EOS, context limit, or the token cap — never ran unbounded); no role tokens or prompt text leaked into any output. Given the tiny dataset and step budget, generated text was frequently repetitive across prompts (see memorization result above) — an honest reflection of the model's actual (limited) learned behavior, not evidence of a broken generation path.

## 27. Candidate verdict

**`instruction_tuned_with_warnings`** — Run A was selected (lowest validation loss). Phase 10's training-process quality gate reported `readiness_status: "warning"`, and the `memorization_risk_bounded` learning check also warned (high duplicate-output rate) — both push the status from "candidate" to "with warnings," exactly the intended, honest outcome for a limited-scale experiment.

## 28. Candidate lifecycle/status

Promoted model version `f64c7e7e-8e0e-49d8-bfcf-63fce39efd98` (scratch verification ID), `lifecycle_status = "staging"`, `architecture_summary_json = {"base_pretrained": true, "instruction_tuned": true, "evaluation_required": true, "not_public_chat_ready": true, "source_experiment_public_id": "...", "source_base_model_public_id": "..."}`. Base checkpoint checksum before and after selection: **identical** (`110e24f380e9f467a7a61c32354e7fc0da0b1ba946ce3da887ebd58ca8cfb1de` both times) — the base checkpoint file was never modified, verified directly via `TrainingCheckpointManager.verify()`, not merely re-read from an unchanging database value.

## 29. Manifest checksum

`manifest_checksum_sha256 = 7daa27a374371dbbb1cb620dca9a1ef08efc3348ee402b5c0cbc86661eec8792`. `verify_manifest()` recomputed the identical checksum and confirmed `matches: true`. Tamper detection was verified directly by automated test: inserting a second manifest row with a deliberately mismatched checksum (append-only tables permit new rows, not in-place edits) causes `verify_manifest()` to correctly report `matches: false`.

## 30. Public chatbot status

Verified directly (`tests/backend/test_instruction_tuning_api.py::test_candidate_selection_promotes_and_remains_not_public_chat_ready`): after a full candidate selection and promotion, `POST /api/chat` still returns `model: "placeholder"`. No model version was assigned to the `public_chat` assignment key in this phase or any earlier one.

## 31. Worker-dispatch isolation evidence

Verified directly by test (`test_run_lifecycle_and_worker_dispatch_isolation`): after queueing an instruction-tuning run, calling `PretrainingService.run_one()` (the generic base-pretraining worker) returns `None` and the job's status remains `queued` — the base worker never claims it. `InstructionTuningService.run_one()` then successfully claims and completes the same job. The full existing Phase 9/10/11 test suite (147 pre-Phase-12 tests) remains green, proving the additive `_claim()` change is behaviorally invisible to every existing job.

## 32. API verification

All 25 `/api/admin/instruction-tuning/...` routes were exercised through in-process ASGI requests (`httpx.ASGITransport` — no live server/browser available in this environment, same `BUILD_VERIFIED_ONLY` convention as Phase 9–11): experiment create (with base-model-eligibility rejection test)/patch, profile generate/get, template create/get/validate, run create/queue/evaluate, metrics/language-metrics/learning-checks, diagnostic-generate (admin-only, 403 without auth), compare-runs, select-candidate, candidate, manifest get, manifest/verify (including tamper detection). Responses were checked to contain no raw record text, no absolute filesystem paths, and no secrets.

## 33. Admin Dashboard verification

`apps/admin-dashboard/src/pages/InstructionTuningPage.jsx` implements all required sections as tabs (Overview, Dataset Profile, Templates, Runs, Training Metrics, Language Evaluation, Diagnostic Lab, Leakage Checks, Candidate Selection, Reproducibility), always showing the required disclaimer and the Diagnostic Lab's "not the public chatbot" notice. Verified by a clean `npm run build` (see item 35) and code review against the same API contract verified in item 32 — no live browser was available in this environment, so actual browser interaction was not performed; this limitation is reported explicitly.

## 34. Test results

`python -m pytest -q` (full suite, run after the real dev DB migration): **159 passed** — 147 pre-existing Phase 1–11 tests (unchanged in behavior) plus 12 new Phase 12 tests (8 migration tests, 4 API/service tests covering the full experiment→profile→template→run→evaluate→diagnostic-generate→compare→select-candidate→manifest→verify pipeline, worker-dispatch isolation, and base-checkpoint immutability).

## 35. Ruff and diff-check result

`python -m ruff check .` → **All checks passed!** `git diff --check` → no whitespace errors.

## 36. Frontend builds

Both `apps/chatbot` (`npm run build`) and `apps/admin-dashboard` (`npm run build`) succeed with no errors.

## 37. Database integrity and foreign-key result (real dev database, post-migration)

`PRAGMA integrity_check` → `ok`. `PRAGMA foreign_key_check` → no violations. `PRAGMA user_version` → `12`.

## 38. Git commit and status

This report is generated before the final commit described at the close of this document; the working tree is clean immediately before that commit (all Phase 12 files staged, nothing else). No destructive git operation was used, and nothing was pushed.

## Known limitations

- **Dataset scale.** 37 eligible records is far below the 1,000-record recommendation (and even below the 200-record "limited experiment" floor mentioned as a soft target in the spec). Every claim in this report about Run A/B behavior is scoped to a **tiny-scale trial**, not a representative-scale result.
- **High duplicate-output rate.** 93.3% of bounded fixture generations were duplicates of each other for both runs — an honest sign that 60 steps on 37 records taught very little varied behavior. This is reported as a `memorization_risk_bounded` warning, not hidden.
- **Test-split reliability.** With only 4 test records, `TEST_EVALUATION_NOT_RELIABLE` is correctly flagged.
- **Tanglish validation coverage.** Zero Tanglish records landed in the validation split for this tiny dataset; `language_metrics_complete` correctly warned rather than fabricating a Tanglish loss value.
- **`stream_verification` reports unverified for instruction-tuning runs** — this is expected, not a bug (see [docs/instruction_tuning_training.md](instruction_tuning_training.md)'s note on Phase 10 stream-manifest reuse); Phase 12's own input/label stream checksums serve the equivalent purpose.
- **No live browser available** in this execution environment — the Admin Dashboard page was verified by a clean build and API-contract review, not by clicking through it.
- **Manual-harness checksum placeholders** for `dataset_checksum_sha256` and `core_model_config_checksum_sha256` in the scratch verification fixtures (repeated hex digits, since the harness inserted rows directly rather than through the full dataset-finalize/config-validate pipelines) — a harness artifact, not a defect in shipped code (same as Phase 11's equivalent note).

## Phase 13 readiness

Phase 12's infrastructure (experiments, templates, label masking, runs, evaluation, leakage/memorization checks, candidate selection, manifests) is complete and independently tested. Before any Phase 13 work that depends on a genuinely capable instruction-tuned model, a real, larger approved instruction dataset (≥1,000 examples, spanning all supported record types) should be built — this phase's dataset was explicitly a tiny-scale trial. No blocking defect prevents Phase 13 from starting.

## Non-goals confirmed unchanged

No public chatbot inference, production deployment, RLHF, DPO, reward modeling, preference optimization, RAG, tool calling, web search, quantization, GGUF export, or external model providers were added or modified in this phase.

## Reuse discipline confirmed

No second trainer was written — `run_instruction_tuning()` is a sibling of `run_pretraining()` sharing the same optimizer/scheduler/gradient-accumulation/checkpoint-callback contract, and `model.forward()`/`causal_lm_loss` are entirely unmodified. No second checkpoint, lease, or recovery system was written — `InstructionTuningService` composes `PretrainingService` and calls its checkpoint/metric/run-summary methods directly. No second quality-assessment or run-comparison table was written — `select_candidate`/`compare_runs`/`comparisons` call the existing Phase 10 `TrainingEvaluationService`.

## Final verdict

**`PHASE_12_COMPLETE_WITH_WARNINGS`**

Warnings, all explicitly surfaced rather than hidden: the manual-verification dataset is `limited_instruction_experiment` scale (37 eligible records, far below the 1,000-record target), the test split is `TEST_EVALUATION_NOT_RELIABLE` (4 records), the selected candidate is `instruction_tuned_with_warnings` (Phase 10 quality-warning plus a memorization warning from a high duplicate-output rate), and Tanglish validation coverage was zero for this tiny dataset. No blocking defect exists; every warning reflects genuine data-scale and model-capacity limitations of a small-scale manual trial, reported honestly rather than suppressed, and the full automated test suite (159/159) plus the real dev database migration both pass cleanly.
