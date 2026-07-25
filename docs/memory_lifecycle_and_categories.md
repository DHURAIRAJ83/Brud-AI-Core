# Memory Item Categories, Purposes, and Lifecycle

## Categories

`MEMORY_CATEGORIES` (8, structurally enforced by a `CHECK` constraint
on `memory_items.category` — the database itself, not just
application code, rejects anything else):
`language_preference, format_preference, confirmed_name_or_alias,
learning_goal, course_progress, project_preference,
user_confirmed_fact, conversation_follow_up`.

`FORBIDDEN_MEMORY_CATEGORIES` (14) are simply not members of
`MEMORY_CATEGORIES`, so they can never be assigned even by a bug in
application code: `password, api_key, access_token, private_key,
payment_card, bank_account, authentication_cookie, precise_location,
medical_diagnosis, political_affiliation, religion,
sexual_information, criminal_record, biometric_data`. Proposing one of
these returns HTTP 422 with the specific reason
`forbidden_sensitive_category` — verified directly in manual
verification Path E.

## Purposes

`MEMORY_PURPOSES` (7): `language_preference,
response_format_preference, course_progress, learning_goal,
project_context, user_confirmed_profile, conversation_continuity`. A
purpose outside this list is rejected with reason `unbounded_purpose`.

## Content safety scan

Every proposed memory value (and every conversation turn, before it is
even persisted) is scanned by
`core_model.conversation.memory_safety.assess_memory_safety()` for
passwords, API keys, access tokens, private keys, payment cards, bank
accounts, authentication cookies (all `blocking`), absolute paths and
environment-variable dumps (`warning`), and — notably — hidden/
injection-style instructions (`blocking`, category
`hidden_instruction`: "ignore ... instructions", "reveal ... system
prompt", "act as the system", "change the memory policy", "delete the
logs", "retrieve another user's data", "execute the following
command"). A blocked memory proposal, and a blocked conversation turn,
are both rejected outright (HTTP 422) before ever being stored — this
is a stronger, earlier gate than the context-assembly-time injection
guard described in `docs/conversation_injection_guard.md`, and was
observed directly in manual verification Path J.

## Status lifecycle

`MEMORY_ITEM_STATUSES` (9): `proposed, awaiting_confirmation, active,
superseded, expired, revoked, rejected, deleted, archived`. Only
`active` items are ever retrievable — `expired`, `revoked`, `rejected`,
`deleted`, `archived`, `proposed`, and `awaiting_confirmation` are all
excluded at the retrieval query itself, not filtered after the fact.

## Deletion and expiry

`delete_memory()` and `expire_memory()` both flip status
transactionally; because retrieval always re-reads live status (no
cache to invalidate), the very next retrieval call after a delete
excludes the item — verified directly in manual verification Path G.
`delete_all_for_purpose()` supports a bulk "forget everything for this
purpose" operation and records a `deleted_forget_purpose` event per
item, never a silent bulk wipe.
