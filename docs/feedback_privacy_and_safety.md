# Feedback Privacy and Safety Scanning

## Privacy filter

`core_model/feedback/privacy_filter.py` reuses Phase 17's
`core_model.conversation.memory_safety.detect_safety_signals()`
unchanged for secrets/hidden-instructions/paths/env-dumps, and adds
pattern-based detection for the sensitive-topic categories Phase 17
could reject structurally via a category CHECK constraint (feedback
free text has no such column to lean on): medical information,
political identity, religious identity, sexual information,
criminal-record claims, biometric information, precise addresses, and
database-credential URIs.

Statuses: `safe|redacted|requires_review|blocked`. Blocked feedback can
never become a dataset candidate — enforced both by
`preconditions_met()` in `core_model/feedback/candidate_builder.py` and
directly by `FeedbackDatasetService.approve_candidate()`.

## Safety filter

`core_model/feedback/safety_filter.py` reuses Phase 16's
`core_model.rag.injection_filter.detect_injection_signals()` unchanged
for unsafe-instruction/injection-style content, and Phase 12/13's
`core_model.instruction_tuning.evaluation` (`no_role_token_leakage`,
`no_system_prompt_leakage`, `no_excessive_repetition`) unchanged for
structural leakage/repetition checks on corrected responses.

## Storage discipline

General feedback APIs never return full raw comments or corrected
responses once blocked: `feedback_events.comment_text` is only
populated when the privacy scan does not return `blocked`, and is set
to `None` entirely on deletion (`FeedbackService.delete_event()`) —
only the checksum (`comment_checksum_sha256`) and event metadata
survive, matching "raw feedback must not remain retrievable after
deletion." Verified directly in manual verification Path C: a
synthetic API-key pattern is blocked, `comment_text` is `null` in the
event response, and the audit log never contains the raw secret.

## Two-layer defense

Injection-style content is blocked at the earliest possible point
(memory/feedback content scanning at submission time) and, for
anything that reaches storage regardless, flagged again at any later
context-assembly stage that reuses it — the same defense-in-depth
discipline established in Phase 17's
`docs/conversation_injection_guard.md`.
