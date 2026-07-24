# Instruction-Following Evaluation (Phase 13)

`core_model/model_evaluation/instruction_following.py` provides bounded,
deterministic per-fixture checks, each reported individually — never
collapsed into a single opaque pass/fail without category detail.

## Checks

| Check | What it verifies |
|---|---|
| `check_one_line` | Response fits on a single non-empty line, for `expected_format="one_line"` |
| `check_list_count` | A numbered/bulleted list has the expected item count (pass exact, warning if some items found, fail if none) |
| `check_requested_length` | Response stays under a requested character bound |
| `check_translation_direction` | Target-language script ratio meets a minimum (caller supplies which script) |
| `check_classification_label` | Response contains one of the expected classification keywords |
| `check_definition_format` | Response is non-empty and not itself phrased as a question |
| `check_refusal_requirement` | A fixture with `refusal_expected=true` actually produced a refusal |
| `check_format_compliance` | Dispatches to `one_line`/`numbered_list` structural checks, or reports `not_evaluated` for an unknown `expected_format` |

## Scoring

`evaluate_instruction_following()` runs `format_compliance`,
`requested_length`, `refusal_requirement`, and (when `expected_keywords`
is set) `classification_label`. `not_evaluated` checks are excluded before
scoring; the remaining checks score `pass=1.0`/`warning=0.5`/`fail=0.0`,
averaged. This mirrors the same partial-credit pattern
`core_model.model_evaluation.relevance_checks.evaluate_surface_relevance`
uses.

## Run-level aggregation

One `instruction_following_score` metric is recorded per fixture; the
run-level `overall` metric is the mean across all fixtures that produced
a score. A fixture with one or more `failed_checks` raises a
`format_noncompliance` issue (severity `warning`) — visible per-output,
not just folded into the aggregate.
