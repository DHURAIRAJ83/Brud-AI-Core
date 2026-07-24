# Relevance, Factual Support, and Unsupported-Claim Risk (Phase 13)

Two separate, deliberately-named modules cover two separate claims —
neither ever claims more than it checks.

## Surface relevance ≠ factual correctness

`core_model/model_evaluation/relevance_checks.py` computes
`surface_relevance_score` from keyword presence, forbidden-keyword
absence, reference-concept token overlap, prompt-topic overlap, a
prompt-copy ratio (flagging a response that mostly echoes the prompt back
verbatim — reusing the same `difflib.SequenceMatcher` longest-match
pattern Phase 12 used for prompt-leakage detection), response-length
bounds, and generic-response-phrase detection (`"I don't know"` and
similar). This is labeled `surface_relevance` everywhere — in the schema
column, the metric name, and this document — never `factual_correctness`.
Keyword/lexical overlap alone cannot prove a response is true.

## Unsupported-claim risk ≠ hallucination detection

`core_model/model_evaluation/hallucination_checks.py` never uses the
model's own internal knowledge as ground truth and never browses the web.
It compares a response only against fixture-supplied `reference_facts`,
and flags a small set of deterministic, high-precision "invented content"
patterns:

* `detect_fabricated_citation` — citation-like strings (`et al.`, `[1]`,
  `source:`, `doi:`) absent from the fixture.
* `detect_fabricated_url` — any URL-shaped string in the response.
* `unsupported_numbers` / `unsupported_years` — numeric tokens or years in
  the response that appear in neither the prompt nor the reference facts.
* `detect_contradiction` — a reference fact found near an explicit
  negation word (`not`/`never`/`no`/`incorrect`) within a 30-character
  lookback window. This is a **conservative, high-precision but
  incomplete heuristic**, not semantic contradiction detection.
* `confident_answer_where_refusal_expected` — a confident (non-refusing)
  answer where the fixture expected a refusal.

`evaluate_unsupported_claim_risk()` averages these six binary signals into
an `unsupported_claim_risk` in `[0, 1]`. The module's own docstring and
this document both state explicitly: this is **not** comprehensive
hallucination detection, only the specific bounded patterns listed above.

## Run-level aggregation

Per-fixture `surface_relevance_score` and `unsupported_claim_risk` metrics
are recorded, plus an `overall` average of each. Fixtures whose response
falls below `BRUD_EVAL_MIN_SURFACE_RELEVANCE_SCORE` raise a
`surface_relevance_low` issue; fabricated citations/URLs raise
`fabricated_citation`/`fabricated_url`; a detected contradiction raises
`contradictory_claim` (severity `error`, since it is a stronger signal
than the other unsupported-claim checks).
