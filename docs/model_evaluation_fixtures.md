# Evaluation Fixtures (Phase 13)

Unlike Phase 11/12's hardcoded fixed evaluation sentences
(`core_model/training/...` and `core_model/instruction_tuning/fixed_eval_fixtures.py`),
Phase 13 fixtures are **admin-authored via the API**, never hardcoded in
this codebase. `core_model/model_evaluation/fixtures.py` only validates
and checksums whatever an admin submits — it does not supply fixture
content itself.

## Structural validation

`validate_fixture()` (bounded by `FixtureValidationThresholds`, backed by
`BRUD_EVAL_MAX_PROMPT_CHARS` / `BRUD_EVAL_MAX_REFERENCE_CHARS` /
`BRUD_EVAL_MAX_NEW_TOKENS_CEILING`) rejects:

* an unrecognized `category` or `language`
* an empty or over-length `prompt`
* an over-length `system_prompt` or `reference_answer`
* a non-positive or over-ceiling `max_new_tokens`

and warns (non-blocking) when:

* `refusal_expected` is set outside `safety_refusal`/`unsafe_instruction_handling`
* a structured category (`translation`/`classification`/`definition`) has no `expected_format`
* a safety category has no `severity`

Fixture-set creation is atomic: if any fixture in a submitted batch fails
structural validation, the whole batch is rejected — no partial fixture
set is ever persisted.

## Checksums

* `fixture_checksum()` hashes a fixed field subset (category, language,
  prompt, system_prompt, expected_response_language, expected_format,
  expected_keywords, forbidden_keywords, reference_answer,
  reference_facts, refusal_expected, max_new_tokens, timeout_seconds,
  severity) — the exact content that determines behavior during
  execution.
* `fixture_set_checksum()` hashes the sorted list of individual fixture
  checksums, giving one stable value per fixture-set submission.

## Coverage, not sufficiency of truth

`FixtureCoverageThresholds` and `evaluation_sufficiency_status()` classify
a fixture set as `sufficient` / `limited_evaluation` / `insufficient`
purely by count — the same honest three-tier pattern Phase 9–12 use for
dataset/experiment sufficiency. `coverage_warnings()` reports (never
silently fixes) missing or under-represented languages/categories:
Tamil, English, Tanglish, Mixed, safety, and robustness coverage are each
checked against a configurable minimum.

## 20 fixture categories

```
language_compliance, instruction_following, response_relevance,
format_compliance, translation, definition, summarization, classification,
transformation, reasoning_basic, code_switching, tanglish_understanding,
safety_refusal, unsafe_instruction_handling, prompt_leakage, role_leakage,
system_prompt_leakage, repetition, robustness, unicode_handling
```

Every category maps to one or more evaluator modules
(`docs/multilingual_evaluation.md`, `docs/instruction_following_evaluation.md`,
`docs/factual_support_evaluation.md`, `docs/safety_refusal_evaluation.md`,
`docs/evaluation_leakage_repetition.md`) — a fixture is never evaluated by
a category it wasn't submitted under.
