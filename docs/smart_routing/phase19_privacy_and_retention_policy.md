# Phase 19 — Privacy & Retention Policy

## 1. Default: no raw text, ever

Neither the raw public question nor the generated answer is stored by
default anywhere in the knowledge-gap registry. Every case/occurrence
row stores only: a SHA-256 `input_hash`, a privacy-redacted
`redacted_question`, a deterministically canonicalized
`canonical_question`, and structured classification metadata
(language/domain/intent/freshness/event_type/reason_codes). This
mirrors `public_chat_routing_events`'/`public_chat_feedback_events`'s
existing Phase 18 convention exactly.

## 2. Redaction pipeline

`KnowledgeGapPrivacyService.process()`:

1. **Secrets first** (`core_model.corpus.secret_detection.detect_secrets()`,
   reused verbatim). A genuine hit (password, API key, private key,
   payment card, bank account, session ID, DB connection string) →
   `content_unavailable_for_review=True`, only the hash is retained,
   *no* redacted text is stored at all — honoring
   `secret_detection.py`'s own documented "never redact-and-keep"
   policy for genuine credentials.
2. **PII** (`core_model.corpus.pii_detection.detect_pii()`/`redact_pii()`,
   reused verbatim for detection). Hits are redacted using Step 6's own
   placeholder vocabulary — `[EMAIL]`, `[PHONE]`, `[ADDRESS]`,
   `[IDENTIFIER]` (aadhaar-like/pan-like/passport-like/medical-record
   patterns) — remapped from the corpus module's own `<X_REDACTED>`
   tokens as a presentation-layer substitution, not a second detection
   implementation.
3. **`[PERSON]`** — a narrow, best-effort heuristic matching explicit
   self-introduction phrases only (`"my name is ..."`, `"நான் ...
   என்பவன்/என்பவள்"`). No general-purpose NER exists anywhere in this
   codebase to reuse, and building one is out of Phase 19's scope —
   documented as a known limitation, not silently claimed as complete
   coverage.
4. **`[PRIVATE_CONTEXT]`** — applied only when the occurrence's route
   was `memory` and the message contains a conversational
   back-reference pattern (`"that thing I told you"`-shaped phrases).
   Defensive: raw memory content is never pulled into this pipeline in
   the first place (occurrences never store memory contents).
5. Any residual ambiguity in redaction confidence (the `requires_review`
   secret-signal tier) also falls back to hash-only, rather than
   guessing at a placeholder substitution for a pattern the underlying
   detector itself only rates as "needs review."

## 3. Canonicalization never reconstructs raw text

`KnowledgeGapCanonicalizationService` operates only on the
already-redacted text and performs surface normalization (Unicode NFC,
whitespace/punctuation cleanup, Latin-script lowercasing, bounded
Tanglish/technical-term alias expansion) — it never translates, never
infers or reconstructs what a redacted placeholder originally was, and
never merges two questions on keyword overlap alone (that is
`KnowledgeGapClusteringService`'s job, gated by domain/intent bucketing
plus exact/normalized/Jaccard matching).

## 4. Retention policies

`RETENTION_POLICIES = ("standard", "extended_review", "hash_only",
"not_retained")`:

- `standard` — redacted + canonical text retained, normal review flow.
- `hash_only` — set automatically when secret detection fires; no
  redacted text is ever written.
- `not_retained` — safety events and `not_applicable` classifications;
  no case is created in the registry at all for these.
- `extended_review` — reserved for a future, more sensitive review
  tier; not currently assigned by any code path in this phase.

## 5. Structural cross-user isolation

No table in the registry has any end-user-identifying column
(`user_id`, `session_id`, `ip_address`, `user_agent`, or
`conversation_id`) — verified by a dedicated schema-introspection test
(`test_no_table_has_any_end_user_identifying_column`) that enumerates
every column of all ten tables. This means cross-user data leakage is
structurally impossible by construction, not merely prevented by an
access-control check. The one place a `conversation_id` is read at
all (`PublicChatRoutingRepository.count_resolved_route_for_conversation()`,
for bounded clarification-attempt tracking) reads it from the
*existing*, already-sanctioned `public_chat_routing_events` table
transiently at request time — it is never copied into any Phase 19
table.

## 6. Deletion and forgetting

`KnowledgeGapDeletionService` implements a four-state, Admin-governed
workflow (`requested → confirmed → executed`, or `rejected`/
`cancelled`), append-only (`knowledge_gap_deletion_requests`, one new
row per state transition, never an UPDATE). Execution
(`execute_case_deletion`) clears exactly two columns
(`redacted_question`, `canonical_question` → `NULL`) and sets
`content_unavailable_for_review=True`, `status="deleted_payload"`,
`retention_policy="not_retained"` — the case row itself, every
occurrence, every review/note/resolution/status-event row, and the
deletion-request history all remain, satisfying the rule that deletion
must never silently erase audit obligations. There is no automatic
cleanup scheduler in this phase — every step requires an explicit
Admin action.

## 7. Research notes are also privacy-scanned

`KnowledgeGapResearchService.add_note()` runs the same
`KnowledgeGapPrivacyService` PII/secret scan over note text before
persistence that public questions go through. A note containing a
genuine credential is rejected outright (`ValidationError`, surfaced
as HTTP 422) rather than silently redacted-and-stored — an Admin
writing an investigation note must remove the sensitive content and
resubmit.

## 8. What an Admin-facing API/UI response never contains

Verified by dedicated tests across `test_knowledge_gap_admin_api.py`
and `test_knowledge_gap_security_and_performance.py`:

- Raw question or answer text (only `canonical_question`/
  `redacted_question`, both privacy-processed).
- A genuine secret/credential in any form (hash-only fallback).
- Any user/session/IP-identifying value (structurally absent).
- An internal RAG source ID, checkpoint path, or private filesystem
  path.
- Evidence of a training run or RAG index having been created (the
  handoff-eligibility endpoints only ever return boolean flags +
  reason codes).
