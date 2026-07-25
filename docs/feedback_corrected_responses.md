# Corrected Responses

A corrected response is an immutable *proposed replacement* — it never
overwrites the original model output. The original output's checksum
lives permanently on `feedback_subjects.output_checksum_sha256`;
`feedback_corrected_responses.original_output_checksum_sha256` merely
references it for comparison.

## Lifecycle

`draft -> validated | validated_with_warnings | rejected | superseded`.
Creating a new correction for the same feedback event automatically
supersedes any prior non-terminal correction
(`FeedbackReviewService.create_corrected_response()`), so the
correction history stays fully visible but only one is ever "current."

## Validation

`core_model.feedback.correction_validation.validate_correction()`
checks, in order: non-empty, valid Unicode, response length within
policy, no secrets/sensitive content (via the privacy filter), no
unsafe-instruction content or prompt/system leakage (via the safety
filter), no role-token leakage, requested-language match (via Phase
16's `core_model.rag.language_routing.classify_language()`), and that
every proposed citation ID resolves against the subject's own
accessible citation set (`feedback_subjects.citation_public_ids_json`)
— an unknown citation ID is always rejected, and a citation not in the
original context can only be added via a fresh, explicitly-verified
retrieval, never fabricated.

Any blocking issue (secrets, unsafe content, prompt/role leakage,
unresolved citations, contamination) sets `status=rejected`; a
non-blocking issue (language mismatch) sets
`status=validated_with_warnings`; a clean result is `validated`.

Verified directly: manual verification Path D shows a correction
citing an unknown ID rejected with `citation_ids_unresolved`; Path B/E/F
show valid Tamil/Tanglish/English corrections reaching `validated`.
