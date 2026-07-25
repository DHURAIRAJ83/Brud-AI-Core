# Deduplication and Contamination

## Deduplication

`core_model/feedback/deduplication.py` checks a candidate's normalized
prompt+output against existing dataset records, other feedback
candidates, and any other reference set the caller supplies, returning
the single most specific status:
`unique|exact_duplicate|normalized_duplicate|near_duplicate|prompt_duplicate|response_duplicate|prompt_response_duplicate`.
Exact and normalized matches use SHA-256 checksums; near-duplicate
detection reuses Phase 16's `core_model.rag.chunk_validation.near_duplicate_ratio`
(`difflib.SequenceMatcher`) unchanged, thresholded by
`BRUD_FEEDBACK_NEAR_DUPLICATE_THRESHOLD` (default 0.9).

Verified directly in manual verification Path H: a second candidate
with the identical prompt and output as an already-exported candidate
is flagged `exact_duplicate` at validation time.

## Contamination

`core_model/feedback/contamination.py` checks a candidate's normalized
prompt+output checksum against the training split, validation split,
test split, model evaluation fixtures (Phase 13), feedback regression
fixtures, and the subject's own original output — returning every
issue found, not just the first. Blocking issue codes
(`BLOCKING_CONTAMINATION_STATUSES`): `test_leakage`,
`evaluation_fixture_leakage`, `regression_fixture_leakage`,
`hidden_prompt_leakage`. A blocking issue always sets the candidate to
`quarantined` and a subsequent approval attempt is rejected outright —
verified directly in manual verification Path G, where a candidate
matching an existing Phase 13 evaluation fixture is quarantined and
its approval attempt returns HTTP 422.

Non-blocking issues (`training_duplicate`, `validation_leakage`,
`subject_output_copy`) are still recorded as
`feedback_candidate_issues` rows for reviewer visibility, without
forcing quarantine on their own.
