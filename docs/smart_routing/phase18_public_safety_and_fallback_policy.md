# Phase 18 — Public Chat Input/Output Safety & Fallback Policy

## 0. Scope

This is a **minimal live gate** for the public chatbot, reusing Phase
17's `classify_safety_signal()` and existing corpus-level secret/PII/
harmful-detail detectors. It is explicitly not full Phase 22 tool-aware
safety governance -- no new keyword lists or safety categories were
added in Phase 18.

## 1. Input safety gate

`core_model/public_chat/input_safety.py::evaluate_input_safety()`.

| Underlying Phase 17 signal | Public decision |
|---|---|
| `safe` | `allow` |
| `sensitive_but_allowed` | `allow_with_caution` |
| `requires_policy_review` | `needs_review` |
| `likely_disallowed` | `refuse` |
| `unknown` | `allow_with_caution` (conservative, not a block) |

A `refuse` decision routes the request to the deterministic refusal
template (Section 3). `needs_review` currently degrades to
`insufficient` rather than a special "under review" state -- Phase 18
does not implement a human-review queue for public chat (out of scope;
would belong to a future phase alongside the knowledge-gap registry).

### Must-not-incorrectly-block categories (verified)

`test_government_criticism_is_not_incorrectly_refused` proves
"criticize the government policy" resolves to something other than
`refuse`. The underlying Phase 17 lexicon is designed to distinguish
government-criticism/policy-analysis/RTI-petition-guidance/lawful-
protest-info/historical-political-discussion/defensive-cybersecurity-
education/general-safety-education from genuinely unsafe categories;
Phase 18 inherits that design unchanged.

## 2. Output safety gate

`core_model/public_chat/output_safety.py::evaluate_output_safety()`.
Reuses, in order:

1. `prompt_leakage`/`role_token_leakage` flags already computed by
   `InferenceRuntimeService.run_generation()` (system-prompt leakage).
2. `core_model.corpus.secret_detection.detect_secrets()` (secret +
   private-path leakage -- already covers absolute filesystem paths).
3. `core_model.corpus.pii_detection.detect_pii()` (PII leakage).
4. `core_model.model_evaluation.refusal_checks.detect_harmful_details()`
   (unsafe operational detail).

Any hit blocks the raw output from ever reaching the client -- the
route degrades to `insufficient` with `safety_status="output_blocked"`
and `fallbacks_attempted=["output_safety_blocked"]`, and an audit event
(`public_chat_output_safety_blocked`) is recorded with only the
blocked-reason category list, never the blocked text itself.

Malicious retrieved-content influence (a poisoned RAG chunk trying to
steer generation) is mitigated further upstream, at context-assembly
time, by `core_model.conversation.injection_guard
.assess_context_item_injection()`, already wired into
`ChatOrchestrationService` -- a flagged/quarantined chunk never reaches
generation, so the output gate does not need to re-detect it.

## 3. Deterministic routes: clarify / refuse / insufficient

No LLM call for any of these three. Bilingual (Tamil/English) template
lookups:

- **Clarify** (`core_model/public_chat/clarification.py`): exactly one
  concise question, derived from Phase 17's `AMBIGUOUS_*` reason
  codes. `route_used="clarify"`, `clarification_required=true`, no
  model/RAG/memory invocation.
- **Refuse** (`fallback_text.py::refusal_text()`): a safe refusal in
  the resolved answer language, `route_used="refuse"`,
  `safety_status="refused"`. Never presented as a knowledge gap, and
  never exposes the matched safety-rule internals.
- **Insufficient** (`fallback_text.py::insufficient_text()`): an
  honest, bounded response for any unavailable/failed route, with a
  structured `fallbacks_attempted` reason code. Never invents an
  answer; never claims a web search was performed when it was not.

## 4. Trusted-Web and Tool: honest unavailability

Phase 17 may recommend `execution_route="trusted_web"` or `"tool"`.
Phase 18 always resolves these to `route_used="insufficient"`:

- `trusted_web` recommended -> `fallbacks_attempted` includes
  `trusted_web_unavailable`, `freshness_status=
  "current_information_requires_web"`. The core model is never used as
  a silent substitute -- verified by
  `test_trusted_web_recommendation_never_answers_from_stale_model`
  and, live, by the browser check on "Python latest stable version
  என்ன?" (reply explicitly says a live lookup isn't available, never a
  guessed version string).
- `tool` recommended -> `fallbacks_attempted` includes
  `tool_unavailable`. No large calculation is approximated -- verified
  by `test_tool_recommendation_never_approximates_a_calculation` and,
  live, by the browser check on "987654 × 12345 எவ்வளவு?" (reply
  explicitly declines rather than guessing a number).

## 5. Confidence-band policy

Never a fabricated probability. `high` = a valid, grounded RAG answer,
or a deterministic clarify/refuse decision. `medium` = a stable
model-only answer, or a partially-grounded RAG answer. `low` =
incomplete evidence or any fallback path. `unknown` = route
unavailable or genuinely uncertain. A model-only answer to a
current-facts question is never `high`.

## 6. Known lexicon-coverage limitations (found during Section 17 of
   the main doc's live browser verification)

Both are Phase 17 classifier-lexicon coverage gaps, not Phase 18
routing defects -- Phase 18's job is to execute whatever Phase 17
recommends honestly, and it does so correctly in both cases (proven
against phrasings the lexicon does match). Recorded here rather than
silently patched, to avoid destabilizing Phase 17's already-sealed,
checksum-verified policy and its own canonical-regression coverage.

1. `classify_safety_signal()`'s weapon-instruction pattern matches
   "how to make a bomb at home" (-> `refuse`) but not "How do I make a
   pipe bomb at home?" (-> falls through to whatever route is
   otherwise resolved, `insufficient` in a fresh database with no
   model configured).
2. The ambiguity detector's `AMBIGUOUS_UNCLEAR_PRONOUN` pattern matches
   "What about it?" (-> `clarify`) but not the Phase 18 spec's own
   Tamil-English mixed-language worked example, "அதை apply செய்"
   (-> `insufficient` in the same fresh-database condition).

Both are candidates for a Phase 17 lexicon-robustness follow-up (widen
weapon-instruction phrase variants; add mixed-language ambiguous-
pronoun patterns), tracked as a limitation rather than fixed inline in
Phase 18.
