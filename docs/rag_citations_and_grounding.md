# Citations and Grounding Quality

## Citation building and resolution

`core_model.rag.citation_builder.build_citation_map(selected_chunks)`
assigns `S1, S2, ...` in rank order from the chunks actually selected
into the context budget — never from the model, never invented.
`extract_cited_labels()` parses `S\d+`/`[S\d+]` patterns out of the
generated text; `resolve_citations()` separates labels that resolve to
a real map entry from `unknown_labels` — an unrecognized label is never
heuristically mapped to an unrelated chunk.

## Validation

`core_model.rag.grounding_checks.validate_citation()` returns one of:

- `valid` — resolves to a chunk that was actually in context, checksum
  matches.
- `valid_with_warning` — valid but exceeds `max_citations` or repeats an
  already-cited label.
- `invalid` — resolves to a chunk, but that chunk was not in this
  request's context, or its checksum no longer matches.
- `not_present` — the label was never in the citation map at all (the
  model referenced a source ID that doesn't exist).

`invalid`/`not_present` citations additionally record a
`rag_grounding_issues` row against the request, so citation problems are
always independently auditable, not just reflected in the citation's own
status field.

## Grounding quality (never "factual correctness")

`compute_grounding_quality()` reports `citation_validity_rate`,
`citation_coverage_rate`, `unsupported_sentence_ratio`,
`unknown_citation_count`, `retrieved_context_utilization`,
`no_answer_appropriate`, and `injection_resistance`. These measure
whether an answer's claims are *traceable to the evidence it was given*
— never whether those claims are true. No metric or code path in this
phase is named or documented as measuring factual correctness.

## Verified in manual Path E

The manual verification run's Path E call returned zero citations
(the tiny CPU test profile's context budget produced an
`insufficient_evidence` result before generation was attempted — an
honest, expected outcome under that profile, see
`docs/rag_context_budget_and_prompt.md`). The full 4-status citation
validation logic itself, along with `build_citation_map` /
`extract_cited_labels` / `resolve_citations`'s never-fabricate
guarantee, is directly unit-tested in
`tests/core_model/test_phase16_rag.py`
(`test_citation_map_and_resolution`,
`test_validate_citation_rejects_unknown_and_out_of_context`).
