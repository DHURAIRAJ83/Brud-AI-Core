# Grounded-Answer Policy

## Five statuses

`grounded_answer`, `insufficient_evidence`, `retrieval_failed`,
`generation_failed`, `blocked_evidence` — persisted on both
`rag_grounded_requests.status` (terminal request status) and
`rag_grounded_answers.answer_status`.

## Safe no-answer conditions

`core_model.rag.answer_policy.should_return_no_answer()` returns
`(True, reason)` when:

- the context budget doesn't fit or zero chunks were selected
  (`context_empty`),
- every candidate was quarantined or blocked
  (`only_quarantined_chunks`),
- the top combined retrieval score is below
  `no_answer_score_threshold` (`retrieval_score_below_threshold`).

When true, `RagGenerationService._generate_and_persist()` persists the
exact Tamil string `"இந்த கேள்விக்கு போதுமான உறுதிப்படுத்தப்பட்ட தகவல்
கிடைக்கவில்லை."` (or an English equivalent for non-Tamil queries) as the
answer, **without calling generation at all** — the model is never
asked to produce an answer when the policy has already decided there
isn't enough evidence.

`decide_answer_status()` additionally forces `insufficient_evidence`
when the computed `citation_validity_rate` falls below
`minimum_citation_validity_rate`, even after generation ran — a
generated answer with too many invalid citations is treated the same as
having no answer at all, never surfaced as a confident result.

## A real bug found and fixed: stale pre-update row in the response

The no-answer early-return path originally returned
`public_row(grounded_request)` — a Python variable holding the request
row as it was fetched at *creation* time (`status='accepted'`), before
the subsequent `UPDATE ... SET status='insufficient_evidence'` executed
in the same transaction. Every insufficient-evidence response therefore
reported the request as still `accepted`, even though the database
correctly held `insufficient_evidence`. Fixed by re-fetching the request
row after the update, matching the pattern the main (generation) path
already used correctly. Caught via the automated API test
`test_grounded_answer_and_chat_lab_lifecycle`, which asserted the
request's returned status was one of the five valid terminal values.

A second, related bug was found in the same code path: the
early-return dict was missing the `disclaimer` field the main path
always includes ("Admin-only grounded diagnostic. This is not the
public chatbot."). Fixed by adding it to both return paths.

## Verified in manual Path B

An empty knowledge space with an active, empty retrieval profile,
queried for an unrelated fact ("what is the boiling point of mercury on
the planet mars"), correctly returned `grounded_request.status ==
"insufficient_evidence"`, zero citations, and the disclaimer — no
fabricated answer was produced.
