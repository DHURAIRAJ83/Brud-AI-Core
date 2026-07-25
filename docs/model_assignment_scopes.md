# Model Assignment Scopes (Phase 15)

Four fixed scopes, seeded by `InferenceRuntimeRepository
.ensure_default_scopes()` the first time any scope is listed or an
assignment is created:

| Scope | Enabled by default | Purpose |
|---|---|---|
| `admin_diagnostic` | yes | Admin-only, single bounded prompt, no conversation persistence required. |
| `admin_chat_lab` | yes | Admin-only, bounded multi-turn session. |
| `internal_canary` | yes | Controlled internal comparison against a small, explicit fixture-prompt set — never real public traffic. |
| `public_chat` | **no** | Disabled by default; requires a separate explicit activation gate that is never auto-passed. |

## Evaluation-readiness policy by scope (`SCOPE_MINIMUM_READINESS`)

```
admin_diagnostic  -> evaluation_passed_with_limits, or evaluation_warning
                     with explicit acknowledgement
                     (context_policy.acknowledge_evaluation_warning)
admin_chat_lab    -> evaluation_passed_with_limits
internal_canary   -> evaluation_passed_with_limits, no blocking issues,
                     recorded human-review coverage (or explicit
                     acknowledgement that none has been recorded yet:
                     context_policy.acknowledge_missing_human_review)
public_chat       -> evaluation_passed_with_limits, plus every
                     requirement in docs/... below
```

`evaluation_blocked` and `not_assessed` are always blocking, for every
scope, with no acknowledgement path.

## Explicit registry-fixture rejection

If a candidate's label, notes, model-card markdown, or release manifest
contains `registry_workflow_fixture` or `not_production_model` (Phase
14's own markers for its registry-mechanics fixture), assignment to
`public_chat` or `internal_canary` is **always** rejected — no
acknowledgement flag exists for those two scopes. Assignment to
`admin_diagnostic` is rejected too, unless
`BRUD_INFERENCE_ALLOW_REGISTRY_FIXTURE_DIAGNOSTICS=true` (default
`false`, intended only for isolated test runs — never enabled against
real development data).

## Scope is a property of the assignment, not the release

The same release can be assigned to multiple scopes simultaneously
(e.g. `admin_diagnostic` and `internal_canary`) via separate assignment
rows — scope eligibility, evaluation-readiness policy, and registry-
fixture rejection are all evaluated independently per assignment, never
cached on the release itself.

## Phase 16 reuses `admin_diagnostic`, does not add `admin_rag_lab`

RAG grounded generation and the RAG Chat Lab both require an
`admin_diagnostic`-scope assignment — no new scope value was added to
`inference_assignment_scopes.scope_key`'s CHECK constraint, because
SQLite's `foreign_keys` pragma cannot be toggled mid-transaction and
`initialize_database()` applies every migration inside one shared
transaction, making a table rebuild to widen the CHECK constraint unsafe
inside `_apply_v16`. All RAG-specific eligibility requirements (active
knowledge space, active indexes, active retrieval profile) are enforced
entirely inside `RagGenerationService`, layered on top of the same
registry-fixture and evaluation-blocked checks this scope already
enforces. See [database_schema_v16.md](database_schema_v16.md).

## Phase 17 also reuses `admin_diagnostic`

Chat orchestration sessions likewise require an
`admin_diagnostic`-scope assignment on the session's
`model_assignment_id` — no new scope value was added. All
conversation-memory-specific eligibility (active memory policy, active
retrieval profile where used, session status) is enforced entirely
inside `ChatOrchestrationService`, layered on top of the same
registry-fixture and evaluation-blocked checks this scope already
enforces. See [database_schema_v17.md](database_schema_v17.md).
