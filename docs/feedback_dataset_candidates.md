# Dataset Candidates

A dataset candidate may be created only from validated feedback plus a
completed human review recommending it plus a validated (non-rejected)
corrected response — `core_model.feedback.candidate_builder.preconditions_met()`
enforces this before `FeedbackDatasetService.create_candidate()` ever
runs, never after.

## Candidate types

`instruction|chat|translation|tanglish_pair|safety|preference|evaluation_only`.
`infer_candidate_type()` provides a deterministic, documented mapping
from subject type + feedback type when the admin does not specify one
explicitly. `preference` candidates are structurally blocked from
`export_candidate()` until a future preference-training phase is
explicitly implemented. `evaluation_only` candidates are likewise
blocked from export — they exist only as regression evidence.

## Structure and versioning

Every correction to a candidate's content creates a new immutable
`feedback_candidate_versions` row (`prompt_text`, optional `input_text`,
`output_text`, language, three checksums, a required `change_reason`)
— prior versions are never overwritten. Unlike raw feedback content,
candidate prompt/output text is stored in full: by the time a
candidate exists, its content has already passed the privacy and
safety scans (both the source feedback's and, for the admin-supplied
`prompt_text`, its own dedicated scan in `create_candidate()`).

## Status lifecycle

`draft -> validating -> review_required -> approved | approved_with_warnings
| rejected | quarantined -> exported | archived`. No candidate reaches
`approved` without passing `validate_candidate()`, which records one
`feedback_quality_assessments` row per dimension (13 dimensions: clarity,
correctness support, instruction/response/language/format/safety/citation
quality, provenance completeness, licence completeness, privacy safety,
deduplication, contamination safety) and blocks approval outright on any
`fail`.

## Preference candidates

Thumbs-up/down pairs may form a preference candidate only when the
prompt matches, model configuration is comparable, both chosen and
rejected outputs are preserved (the rejected output is stored in the
otherwise-unused `input_text` column of the version, reusing the
existing schema rather than adding a preference-only column), and a
reviewer has explicitly confirmed the preference is meaningful.
Preference candidates remain outside automatic SFT — confirmed
directly by `export_candidate()`'s hard rejection of the `preference`
type.

See `docs/feedback_deduplication_and_contamination.md` and
`docs/feedback_licence_and_provenance.md` for the validation checks,
and `docs/feedback_dataset_candidates.md`'s companion
`docs/database_schema_v18.md` for the underlying table shapes.
