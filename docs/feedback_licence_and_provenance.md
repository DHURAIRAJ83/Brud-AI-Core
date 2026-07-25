# Licence and Provenance

Every dataset candidate must record: feedback source type, content
creator type, consent status, licence status, allowed use, retention
policy, source-deletion status, and reviewer attribution where
required. `core_model.feedback.provenance.assess_provenance()` is the
single place this is decided.

## Licence statuses

`approved|restricted|unknown|blocked|not_applicable`. Unknown or
blocked licence always blocks training-data approval when
`BRUD_FEEDBACK_REQUIRE_KNOWN_LICENCE` is true (the default) — never
silently treated as approved.

## Source deletion

If the underlying feedback/session content has since been deleted,
`assess_provenance()` downgrades an `approved` licence to `restricted`
rather than trusting a stale approval — a human must re-confirm the
licence decision, since the candidate's own reviewed text may still be
retained (it no longer contains the deleted source content) but the
provenance chain has changed.

## Provenance completeness

A candidate whose content creator is not `admin_authored` or
`reviewer_corrected` requires an explicit reviewer attribution public
ID to be considered provenance-complete; missing attribution blocks
approval the same way an unknown licence does.
