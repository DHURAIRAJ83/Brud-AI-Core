# Multilingual Evaluation (Phase 13)

`core_model/model_evaluation/language_evaluation.py` provides
deterministic, script/lexical-based language-compliance checks — never an
external language-detection model, and never a claim of comprehensive
linguistic understanding.

## Reused, not redefined

`TAMIL_PATTERN` and `LATIN_PATTERN` are imported directly from
`core_model.training.dataset_profile` — the exact same regexes Phase 9–12
already established for script-ratio computation. Phase 13 never
redefines them.

## Tanglish is always its own category

Latin-script text is never classified as English purely by script. A
small, explicit `TANGLISH_MARKERS` lexical list (common transliterated
Tamil particles/endings: `nu`, `na`, `dhaan`, `irukku`, `epdi`, `sollu`,
...) gives Tanglish a bounded, honest signal distinct from English.
`tanglish_lexical_score()` is a ratio, not a hard classifier — when the
lexical list finds no markers in a Tanglish-expected fixture, the result
is `language_marker_leakage`-free but still Latin-script-consistent, and
`evaluate_language_compliance()` treats the absence of markers as
**uncertain, never a hard failure**, because a bounded lexical list cannot
exhaustively cover all Tanglish phrasing.

## `evaluate_language_compliance()`

For each expected language:

* `ta`: passes when the Tamil-script ratio meets `min_script_ratio`.
* `en`: passes when the Latin-script ratio meets `min_script_ratio` **and**
  the Tanglish lexical score stays below `min_tanglish_score` — an English
  fixture whose response reads as Tanglish is not silently counted as
  English.
* `tgl`: passes when the Latin-script ratio meets `min_script_ratio`
  (Tanglish markers strengthen confidence but their absence does not fail
  the check, per above).
* `mixed`: passes when both Tamil and Latin script are present at all.

A response containing a leaked language-marker special token
(`<ta>`/`<en>`/`<tgl>`/`<mixed>`) downgrades an otherwise-passing result to
`warning` — the model produced the right script but leaked an internal
training marker into the visible text.

## Run-level aggregation

`ModelEvaluationService.execute_run()` records one
`language_compliance` metric per fixture (1.0 pass / 0.5 warning / 0.0
fail) and one `language_compliance_score` per language as the average
across that language's fixtures. Zero fixtures for a supported language
produces a `missing_language_coverage` issue (severity `warning`) rather
than a silently-absent metric — coverage gaps are always visible.
