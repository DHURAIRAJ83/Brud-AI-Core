# Memory Consent and Policies

## Policies

`conversation_memory_policies` defines, per policy: default session
mode, whether short-term context/summary/long-term memory are allowed
at all, whether explicit consent is required, and numeric bounds
(`maximum_session_turns`, `maximum_session_age_seconds`,
`maximum_short_term_tokens`, `maximum_summary_tokens`,
`maximum_memory_items`, `default_memory_ttl_seconds`), plus
`allowed_memory_categories`/`forbidden_content_categories` allow/deny
lists layered on top of the structural category check (see
`docs/memory_lifecycle_and_categories.md`). A policy must be
`validated` then `activated` before any session may reference it —
mirrors every prior phase's draft→validated→active lifecycle pattern.

## Consent

`memory_consents`: `status` CHECK
`pending|active|expired|revoked|rejected`, scoped by
`participant_scope_key` (never a FK to any participant table — see
`docs/database_schema_v17.md`), tied to one `memory_policy`, with a
`purpose` from the fixed `MEMORY_PURPOSES` list, optional
`allowed_categories`/`prohibited_categories` overrides, and an
optional `expires_at`.

`revoke_consent()` and `expire_consent()` both immediately expire
every memory item created under that consent
(`_expire_memory_for_consent()`), in the same transaction — consent
withdrawal is not a lazy/eventual operation.

## The consent gate: `may_become_active()`

`core_model.conversation.memory_policy.may_become_active()` decides
whether a freshly-proposed memory item may reach `active` immediately,
or must wait:

- `explicit_user_request` / `system_derived` memory requires an
  **active** consent scoped to the item's category to become active
  immediately; otherwise it stays `proposed` (reason
  `consent_required`).
- `assistant_proposed` memory (with `confidence_type=assistant_inferred`)
  always requires explicit human confirmation regardless of consent —
  it is created `awaiting_confirmation` and can only reach `active`
  via an explicit `POST .../memory-items/{id}/confirm` call. This
  reflects the principle that the assistant's own inference about a
  user is never treated as user-confirmed fact.
- A proposal that conflicts with an existing active item of the same
  category/purpose (`assess_conflict()` returns
  `conflict_requires_confirmation`) also requires confirmation, never
  silent overwrite.

Verified directly in manual verification Path C (consented,
explicit_user_request memory becomes `active` immediately) and Path D
(assistant-inferred memory is excluded from retrieval until an
explicit confirm call, then becomes retrievable).
