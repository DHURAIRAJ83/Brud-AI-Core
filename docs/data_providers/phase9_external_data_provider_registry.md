# Phase 9 — External Data Provider Registry

Status: complete. Schema version 29 -> 30 (migration
`030_external_data_provider_registry`). See
[phase9_external_data_provider_registry_plan.md](phase9_external_data_provider_registry_plan.md)
for the full pre-implementation baseline audit and architecture
rationale.

A governed registry of external organizations/websites Brud AI could
potentially pull training/RAG source material from -- access mode,
authentication, connector capability, trust, and lifecycle. This phase
is provider *management* only: no dataset search, no sample import, no
download, no training/RAG activation. Registering, verifying, or
enabling a provider never writes to `data_sources` or any governance/
lineage table.

## 1. Architecture

**One new registry, structurally isolated from two existing systems it
is easily confused with.**

- **Not the Source & Rights Registry** (`data_sources`, Data Studio
  Phase 2): that table records rights for *one specific piece of
  content already inside Brud AI*. This phase's `external_data_providers`
  records *where Brud AI could look*, before anything has been
  discovered. No shared tables, no shared services, no shared API
  prefix.
- **Not AI inference provider routing** (`inference_model_assignments`,
  Phase 15): that answers "which trained model serves a chat request."
  This phase answers "which external data source could be connected
  to." Investigation also revealed a legacy, effectively dead
  `model_assignments` table with an `assignment_key='admin_assistant'`
  CHECK value -- confirmed unrelated and untouched.
- **Pure policy** (`core_model/data_providers/`): provider types,
  access modes, authentication types, trust statuses, lifecycle
  statuses, domain types, capability types, credential types/statuses,
  connection-test results -- one `is_usable_for_discovery()` pure
  function is the single source of truth for "can this provider be
  used for discovery right now" (enabled AND outside every inactive
  lifecycle state).
- **Repository** (`backend/database/repositories/external_data_providers.py`):
  one `ExternalDataProviderRepository` over all 6 tables, with an
  idempotent `ensure_builtin_providers()` seed (mirroring Phase 15's
  `ensure_default_scopes()` precedent) called lazily from `list_providers()`/
  `get_provider_by_code()` -- never baked into migration DDL.
- **Connector contract** (`backend/services/external_data_connectors/`):
  a strict `ExternalDataProviderConnector` protocol
  (`test_connection`/`get_provider_metadata`/`get_capabilities`), a
  shared `BaseHttpConnector` doing one bounded, redirect-free GET
  against the provider's own already-registered domain (never an
  admin-supplied arbitrary URL -- this is what keeps it from being an
  SSRF/crawler vector), and 7 built-in connectors. `default_http_transport`
  is the only real-network code in this phase; every connector accepts
  an injectable transport so tests never touch the network.
- **Services** (`backend/services/external_data_provider_service.py`):
  `ExternalDataProviderService` (CRUD + 5 audited lifecycle transitions:
  enable/disable/restrict/block/archive, archive terminal),
  `ExternalDataProviderVerificationService` (domain verification +
  evidence-gated trust evaluation -- the *only* automatic trust upgrade
  is `unverified -> domain_verified`, and only after a domain was
  independently, separately marked verified with a written evidence
  note; every higher tier requires a human admin's own reasoned
  `set_trust_status` call), `ExternalDataProviderCredentialService`
  (reference-only, Step 4's exact status contract),
  `ExternalDataProviderConnectionService` (bounded connection tests,
  auto-bumps `draft -> connection_tested` on first success/partial,
  never auto-enables), `ExternalDataProviderCapabilityService`
  (structurally forces `enabled=False` for any download/upload/write
  capability regardless of what was requested).

## 2. Schema (migration 030)

All new, all additive.

| Table | Purpose | Mutability |
|---|---|---|
| `external_data_providers` | One row per provider (built-in template or custom). | Mutable; delete blocked by trigger -- archived, never removed. |
| `external_data_provider_domains` | Official/api/download/documentation/authentication/mirror domains, each independently verifiable. Unique per `(provider_id, domain, domain_type)`. | Mutable verification fields; delete blocked. |
| `external_data_provider_capabilities` | What a provider can be asked to do, per capability type. Unique per `(provider_id, capability_type)`. | Mutable (upsert); delete blocked. |
| `external_data_provider_credentials` | Credential *references* only. Unique per `(provider_id, credential_type)`. | Mutable (replace/revoke); delete blocked. |
| `external_data_provider_connection_tests` | One row per bounded connection-test run. | Append-only. |
| `external_data_provider_events` | Registry-specific audit trail (in addition to, not instead of, the global `audit_logs`). | Append-only. |

**A real bug caught before any data depended on it**: the domains
table's uniqueness was first written as `UNIQUE(provider_id, domain)`,
which would have made it impossible for a provider like Hugging Face
to register the same host under two different `domain_type`s. Caught
while writing the built-in seed data (GitHub's `github.com`
official/`api.github.com` api needed distinct rows, and this surfaced
the constraint gap), fixed to `UNIQUE(provider_id, domain, domain_type)`
before any real provider data existed -- confirmed by re-running the
full migration and repository test suites, both still green.

## 3. Provider types, access/auth models, trust/lifecycle

Machine-readable enums (`core_model/data_providers/__init__.py`),
matching the task's own recommended values exactly: 9 `PROVIDER_TYPES`,
5 `ACCESS_MODES`, 7 `AUTHENTICATION_TYPES`, 8 `TRUST_STATUSES` (4 of
which are `EVIDENCE_REQUIRED_TRUST_STATUSES`), 9 `LIFECYCLE_STATUSES`
(5 of which are `INACTIVE_LIFECYCLE_STATUSES`), 6 `DOMAIN_TYPES`, 9
`CAPABILITY_TYPES` (4 of which are permanently
`CAPABILITY_TYPES_DISABLED_IN_PHASE_9`), 6 `CREDENTIAL_TYPES`, 5
`CONNECTION_TEST_RESULTS`, 14 `PROVIDER_EVENT_TYPES`.

## 4. Credential security

No encrypted/reversible secret storage exists anywhere in this
codebase (`pwdlib.PasswordHash` for admin passwords is one-way only) --
confirmed by direct repository-wide search before writing any Phase 9
code. Per the task's own explicit fallback:

- Only a `reference_key` (an environment variable *name*) is stored --
  never a secret value.
- `configured` is derived at read time (`os.environ.get(reference_key)`
  non-empty), never stored, never cached.
- Every credential API response is exactly `{credential_type,
  configured, status, last_rotated_at, last_tested_at}` -- verified by
  a dedicated API test asserting the exact key set and asserting the
  real secret value never appears anywhere in the response body.
- **Documented limitation** (honest, not silently glossed over): this
  is reference-based, not a real secrets vault -- no rotation
  enforcement, no OS-level access audit on who reads the environment
  variable. Acceptable for this phase's scope (registry + bounded
  connection testing, no data movement); a real secrets-manager
  integration is explicit Phase 10+ territory.

## 5. Connector contract

```python
class ExternalDataProviderConnector(Protocol):
    def test_connection(self, config: ConnectorConfig, transport: HttpTransport) -> ConnectionTestResult: ...
    def get_provider_metadata(self, config: ConnectorConfig) -> dict[str, Any]: ...
    def get_capabilities(self, config: ConnectorConfig) -> list[str]: ...
```

7 built-in connectors: `AI4BharatConnector`, `HuggingFaceConnector`,
`GitHubConnector`, `WikimediaConnector`, `BhashiniConnector`,
`GenericPublicApiConnector` (fallback for any custom provider),
`ManualProviderConnector` (never attempts a network call at all --
`manual_source` providers have no API to reach, and it says so
honestly rather than fabricating a reachability result). No connector
implements search, download, or write in this phase.

## 6. Built-in providers seeded (Step 6)

8 rows, all starting `draft` / `unverified` / `enabled=False`: 5 real
providers with real official domains recorded but *unverified* until
an admin explicitly verifies them (AI4Bharat, Hugging Face, GitHub,
Wikimedia, Bhashini), and 3 clearly-labeled templates with **no**
domain seeded at all (Government Open Data Portal, University /
Research Repository, Custom Provider) -- seeding a specific domain for
an entire category of institution would itself be an unverifiable
claim. No credentials, no licences, no dataset permissions, no
connection-test results are ever seeded.

## 7. Backend APIs

All under `/api/admin/external-data-providers`, admin-only,
CSRF-protected, matching the task's recommended endpoint list plus two
additive endpoints the task's own service design required
(`POST /{id}/domains/{domain_id}/verify`, `POST /{id}/trust-status`) --
without either, Step 7's evidence-based verification workflow would
have no way to actually record a domain verification or a manually
justified higher trust tier.

## 8. Frontend

`apps/admin-dashboard/src/pages/ExternalDataProvidersPage.jsx`, added
to the Data nav group. 8 tabs (Overview, Providers, Add Provider,
Domains, Capabilities, Credentials, Connection Tests, History). The
provider table shows every field the task specifies (Provider, Type,
Access mode, Authentication, Trust, Lifecycle, Anonymous read,
Enabled) plus per-tab credential-status/connection-test/history detail
once a provider is selected. Capabilities tab visibly marks
download/upload/write-metadata as "never enabled in this phase" rather
than hiding them. No secret value is ever rendered.

## 9. Admin Assistant integration

4 new read-only tools (`list_external_data_providers`,
`get_external_data_provider`, `get_provider_capabilities`,
`get_provider_connection_status`, mode `data`) and 6 new controlled
actions (`register_external_data_provider` moderate,
`verify_external_data_provider` moderate,
`test_external_data_provider_connection` low,
`enable_external_data_provider` moderate,
`disable_external_data_provider` low,
`configure_provider_credential_reference` high, requires a reason),
all wired through Phase 8's existing propose -> preview ->
confirm-with-stale-check -> execute -> verify -> audit pipeline --
**every one** of the 6 actions is fully wired to a real executor (not
just the one representative example other phases settled for), proven
by a dedicated end-to-end test suite that includes a genuine
concurrent-mutation race (`register_external_data_provider` correctly
refused at confirm time when another admin registered the same
`provider_code` in between).

**A real, meaningful gap found and fixed during manual verification**:
the task's own flagship example (asking the assistant "about
AI4Bharat" and getting back Provider/Status/Access/Connection lines)
did not work out of the box -- the 4 new read-only tools were reachable
via the tool registry, but Phase 8's chat orchestrator had no intent
route that used them; a provider question fell through to the
LLM-unavailable fallback instead. Fixed by adding a deterministic
`_match_external_data_provider()` lookup (matches the longest real
registered provider name/code found in the message) to
`admin_assistant_chat_service.py`, tried before the LLM path -- now
answers entirely from the real registry, in the exact format the task
specifies, and never claims dataset licence approval.

## 10. Help registry

A new bilingual (EN/TA) entry added to the existing
`apps/admin-dashboard/src/data/helpRegistry.js` (Data Help page),
covering: provider vs. dataset, provider trust vs. dataset licence,
public/gated/private access, authentication, credentials, connection
tests, read-only discovery, and why provider approval never approves
training -- following the exact structure (purpose/prerequisites/
workflowSteps/commonIssues/safetyNote) every other Data Help entry
already uses.

## 11. Tests

- `tests/core_model/test_data_providers_policy.py` (16) -- pure enums.
- `tests/database/test_phase30_migration.py` (17), `test_external_data_provider_repository.py` (17).
- `tests/backend/test_external_data_connectors.py` (11),
  `test_external_data_provider_service.py` (27),
  `test_external_data_providers_api.py` (16).
- `tests/backend/test_admin_assistant_external_data_provider_integration.py` (9)
  -- the 4 tools + all 6 controlled actions end-to-end, including the
  stale-check race test.
- `tests/backend/test_admin_assistant_chat_service.py` extended (+2)
  for the deterministic provider-lookup path.
- `apps/admin-dashboard/src/pages/ExternalDataProvidersPage.test.jsx` (9).
- Full regression: 1881 backend/core_model/database tests (run in
  disk-safe batches -- this environment's `/tmp` tmpfs cannot hold
  the full multi-thousand-test suite's SQLite/WAL temp files in one
  uninterrupted pass, confirmed environmental, not a code issue) and
  100 frontend tests, all passing.

## 12. Manual browser verification

Flows A-E (built-in providers visible with no fake credentials;
register/verify/test/enable a custom provider end to end; configure a
Hugging Face credential reference with the secret never displayed and
an honest connection-test result; block a provider and confirm its
history remains readable; ask the Admin Assistant about AI4Bharat and
get a real, registry-backed, licence-disclaiming answer) plus login
isolation, hard refresh, bookmarked route, mobile 390px, and Tamil
language all verified against the real running dev server and real
backend -- see section 13 for the two real bugs this surfaced.

## 13. Bugs found and fixed

1. **Domain uniqueness constraint too strict** (schema): see section 2.
2. **A real UI trust/timing gap**: switching the selected provider left
   the previous provider's name and (fully clickable) lifecycle-action
   buttons visible until the new provider's data finished loading --
   the mutation itself would have targeted the correct provider (its
   id updates synchronously), but an admin watching the screen could
   have been misled about which provider a button was about to act on.
   Fixed by clearing the detail panel immediately on selection instead
   of leaving stale data displayed.
3. **A real, meaningful missing capability**: see section 9 (Admin
   Assistant provider lookup).
4. Two connector-transport timeouts observed during manual
   verification were real, *expected* behavior, not bugs: this sandbox
   has no outbound internet access, so `test_connection`'s bounded
   5-second timeout was hit for each anonymous/credentialed connection
   test -- confirming the connector never hangs indefinitely even when
   a target host is completely unreachable.

## 14. Limitations / explicitly deferred

Per the task's own explicit out-of-scope list: no live dataset
search/comparison, no dataset-card harvesting, no licence snapshot
capture, no sample download, no quarantine, no RAG sandbox, no
training approval/execution, no automatic provider discovery, no web
crawler, no automated login flows, no browser credential automation,
and no real secrets-vault integration beyond the reference-only model
in section 4.

## 15. Phase 10 handoff

A future dataset-discovery phase should: (a) implement real
`search`/`list_files`/`read_dataset_card` connector methods behind the
same `ExternalDataProviderConnector` contract, gated by the existing
`external_data_provider_capabilities.enabled` flags; (b) create one
`data_sources` row per discovered item through the existing, unmodified
Source & Rights Registry -- never a shortcut around it; (c) only
attempt download/sample-import behind a *new*, explicit capability
enablement this phase deliberately never allows
(`CAPABILITY_TYPES_DISABLED_IN_PHASE_9`); (d) consider a real
secrets-manager integration if credential volume grows beyond what
environment-variable references can reasonably manage.

**Do not proceed to Phase 10 in this session.**
