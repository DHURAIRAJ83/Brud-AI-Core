# Database Schema v13 (Phase 13)

Migration `013_phase13_multilingual_evaluation` upgrades schema version
12 → 13. It is a separate, independent migration function (`_apply_v13`)
from migration 012 — Phase 12's `_apply_v12` is unchanged in behavior and
content.

## New tables

| Table | Purpose | Mutability |
|---|---|---|
| `model_evaluation_suites` | One row per versioned evaluation suite: name/version, supported languages, generation configuration, automated thresholds, human-review rubric, readiness-gate configuration, and lifecycle status. | Mutable while `draft`; frozen by service-layer guard once `validated`/`active` |
| `model_evaluation_fixture_sets` | One row per admin-submitted bundle of fixtures for a suite, with a fixture count and checksum. | Append-only |
| `model_evaluation_fixtures` | One row per admin-authored evaluation prompt: category, language, prompt/system_prompt, expected language/format/keywords, reference answer/facts, refusal expectation, bounded generation limits, checksum. | Append-only |
| `model_evaluation_runs` | One row per evaluation execution: suite, candidate core model version, checkpoint, tokenizer, generation configuration, status, fixture/completion counts, timings. | Mutable lifecycle row |
| `model_evaluation_outputs` | One row per fixture's generated output within a run: raw generated text, token counts, stop reason, checksum. | Append-only |
| `model_evaluation_metrics` | Per-run (and per-language/category) computed metric values, with structural detail JSON. | Append-only |
| `model_evaluation_issues` | Per-run automated findings (29 fixed issue codes), each with a severity (`info`/`warning`/`error`/`blocking`). | Append-only |
| `model_evaluation_human_reviews` | Per-output human review scores/verdict/comment; multiple reviews per output are allowed and never overwritten. | Append-only |
| `model_evaluation_comparisons` | Compatibility assessment between two runs (`compatible`/`partially_compatible`/`incompatible`) with a field diff. | Append-only |
| `model_chat_readiness_assessments` | The final evidence-based readiness verdict for a run, with dimension scores and blocking/warning rationale. | Append-only |
| `model_evaluation_manifests` | Manifest JSON + SHA-256 checksum for a run. | Append-only |

All tables above except `model_evaluation_suites` and
`model_evaluation_runs` carry `BEFORE UPDATE`/`BEFORE DELETE` triggers that
raise `RAISE(ABORT, ...)` — history is genuinely append-only.

## Key columns

```
model_evaluation_suites:
  status CHECK IN (draft, validated, active, retired, archived)
  UNIQUE(name, version)

model_evaluation_fixtures:
  category CHECK IN (20 fixed categories: language_compliance,
    instruction_following, response_relevance, format_compliance,
    translation, definition, summarization, classification, transformation,
    reasoning_basic, code_switching, tanglish_understanding, safety_refusal,
    unsafe_instruction_handling, prompt_leakage, role_leakage,
    system_prompt_leakage, repetition, robustness, unicode_handling)
  language CHECK IN (ta, en, tgl, mixed)
  severity CHECK IN (low, medium, high, critical)

model_evaluation_runs:
  candidate_core_model_version_id  (FK core_model_versions, RESTRICT)
  checkpoint_id                    (FK pretraining_checkpoints, RESTRICT)
  tokenizer_version_id             (FK tokenizer_versions, RESTRICT)
  status CHECK IN (draft, validated, queued, running, completed,
                    completed_with_warnings, failed, cancelled, archived)

model_evaluation_issues:
  issue_code CHECK IN (29 fixed codes covering language, relevance,
    factual-support, safety/refusal, leakage, degeneration, unicode, and
    human-review coverage findings)
  severity CHECK IN (info, warning, error, blocking)

model_chat_readiness_assessments:
  status CHECK IN (evaluation_passed_with_limits, evaluation_warning,
                    evaluation_blocked, not_assessed)
```

## Relationship to existing tables

No Phase 8–12 table is duplicated. Phase 13 tables reference and reuse:

* `core_model_versions` for the eligible candidate — a Phase 12-promoted
  row with `architecture_summary_json.base_pretrained`,
  `.instruction_tuned`, and `.evaluation_required` all `true`.
* `pretraining_checkpoints` for the verified checkpoint backing that
  candidate (looked up by matching `model_checksum_sha256` against the
  candidate's `weights_checksum_sha256`, exactly the value Phase 12's
  `_promote_instruction_candidate` set).
* `tokenizer_versions` for the candidate's inherited tokenizer.

Phase 13 introduces one genuinely new comparison table
(`model_evaluation_comparisons`) rather than reusing Phase 10's
`training_run_comparisons`, because it compares a different entity
(evaluation runs, not pretraining jobs) with a different compatibility
contract (suite version, fixture-set checksum, generation-config checksum,
tokenizer version, threshold-configuration checksum).

## Naming note

The package `core_model/model_evaluation/` (not `core_model/evaluation/`)
holds all of Phase 13's new pure functions. `core_model/evaluation/`
already exists from Phase 8 (`ModelEvaluationEvaluator` stub and
`architecture_checks.py`, both still in active use by
`backend/services/core_model_service.py`); reusing that name would have
collided with it.

## Migration safety

* `_apply_v13` is guarded by `SELECT 1 FROM schema_migrations WHERE version = 13` — safe to call repeatedly.
* `initialize_database()`/`upgrade_database()` now include 12 in the set of versions that trigger a pre-upgrade verified backup (previously 1–11).
* Fresh databases go straight to v13; a v12 database upgrades additively; a v13 database is a no-op.
* Verified via `tests/database/test_phase13_migration.py`: fresh→13, isolated v12 behavior unchanged, v12→13 upgrade, v13→13 no-op, idempotent re-application, deterministic table/index/trigger sets, mutability of the two lifecycle tables, and append-only enforcement on the other nine.
* Real dev database migrated v12→v13 with a verified backup; `PRAGMA integrity_check` = `ok`, `PRAGMA foreign_key_check` = no violations.

## Not in this migration

No Phase 13 table stores absolute filesystem paths or secrets.
`model_evaluation_outputs.generated_text` does store the raw generated
text (unlike most append-only evidence tables elsewhere in the schema) —
this is deliberate: it is the direct evidence a human reviewer needs to
judge a candidate's behavior, and the table is admin-only, access-controlled,
and never exposed to the public chatbot. `model_evaluation_manifests` and
`model_evaluation_metrics` store checksums and aggregate/structural values
only, never raw prompt or response text.
