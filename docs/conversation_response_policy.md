# Conversation Response Policy

`core_model/conversation/response_policy.py` is the single place that
decides a grounded chat turn's final status and what it is allowed to
claim about memory.

## Status precedence

`decide_response_status()` checks, in order: `session_closed` →
`context_blocked` (injection) → `retrieval_failed` → `consent_required`
→ `unresolved_memory_conflict` → `no_evidence_available` →
`generation_failed` → citation-validity thresholds → `completed`. Each
earlier condition takes priority — e.g. a closed session is reported
as `session_closed` even if evidence would otherwise have been
sufficient, and an unresolved memory conflict is reported before
falling through to a generic insufficient-evidence answer.

## Fail-closed guarantees

- `retrieval_failed` and `generation_failed` are real terminal
  statuses, not swallowed into a generic error — a retrieval or
  generation failure never silently falls back to an unguarded or
  fabricated answer.
- `blocked_context` (injection-blocked mandatory content, or budget
  exceeded before evidence selection) always short-circuits before any
  generation call is made.
- Citation validity is enforced numerically:
  `citation_validity_rate < minimum_citation_validity_rate` (default
  0.5) forces `insufficient_evidence` even if generation itself
  "succeeded" — a plausible-sounding answer with mostly-invalid
  citations is never reported as `completed`.

## Memory disclosure never overclaims

`memory_disclosure()` returns `memory_used`, the specific
`memory_item_public_ids`, and their `purpose`s only when memory was
actually retrieved and used for that turn — a response is never
allowed to reference "your saved preference" language when no memory
item was in fact consulted, and never claims an `awaiting_confirmation`
or `proposed` item is a confirmed fact.
