# Phase 9 Plan — External Data Provider Registry

Written before implementation, per this phase's Step 1. Synthesizes
direct inspection of every existing system this phase touches or must
stay clearly separate from.

## 1. Existing systems (confirmed by direct inspection)

### 1.1 There is no existing "external dataset provider" concept anywhere

`git grep`/service inventory confirms zero existing tables or services
about *where Brud AI could fetch data from on the open web*. The only
provider-shaped things that exist today are:

- **`model_assignments`** (Phase 1/2, `backend/database/schema.py`
  line ~165) — a legacy, effectively dead table mapping an
  `assignment_key` (`public_chat, admin_chat_test, admin_assistant,
  tanglish_normalizer, embedding, fallback`) to a `model_registry`/
  `model_versions` row. No service ever reads or writes it except a
  bare `ModelAssignmentRepository.create()/get_by_public_id()`
  (`backend/database/repositories/phase2.py`).
- **`inference_model_assignments`** (Phase 15,
  `backend/services/model_assignment_service.py`) — the real, working
  system: which *released model* serves which *runtime scope*
  (`admin_diagnostic, admin_chat_lab, internal_canary, public_chat`).
- **`inference_runtime_profiles`/`inference_runtime_instances`** —
  which *hardware/runtime configuration* loads a model.

**All three of these are about which trained model answers a chat
request.** None of them describe an external website, API, or
organization that *data* could be pulled from. This is the core reason
Step 0's rule ("do not confuse AI model providers with external
dataset providers") is easy to satisfy structurally: there is no
existing code to accidentally collide with. The new
`external_data_providers` table and services are named, routed, and
registered under a completely distinct vocabulary
(`external_data_provider_*` / `/api/admin/external-data-providers`)
with zero shared tables, models, or services.

### 1.2 The Source & Rights Registry is the closest existing system, and is deliberately not reused

`backend/services/data_source_service.py::SourceRegistryService` +
`data_sources` table (Data Studio Phase 2) record, for one specific
**piece of content already inside Brud AI**: who created it, what
licence/rights apply, and which of six target uses (`rag, training,
evaluation, commercial, public_export, redistribution`) are allowed.
It has no columns for a website's authentication type, connector type,
or connection-test history — it is deliberately per-record, not
per-external-system.

Phase 9's `external_data_providers` describes a **place Brud AI could
potentially look**, before any specific piece of content has been
identified or brought in — access mode, authentication, connector
capability, trust in the *provider* as an organization. Registering a
provider never creates a `data_sources` row and never implies rights
for any dataset that might later be discovered there — enforced by
simply never writing to `data_sources` anywhere in this phase's code
(Phase 9 has no dataset-discovery logic at all, per the task's own
explicit scope boundary). A later phase (10+) that performs real
dataset discovery through a registered provider is expected to create
its *own* `data_sources` row per discovered item, going through the
existing, unmodified Source & Rights Registry exactly as a manually
found source would.

### 1.3 No encrypted/reversible secret storage exists

`backend/database/repositories/admin.py` uses `pwdlib.PasswordHash`
for admin login passwords — a one-way hash, correct for passwords
verified by the same system that set them, structurally unusable for
a credential that must later be *sent back out* to an external API
(e.g. a Hugging Face bearer token). A repo-wide search for
`cryptography`/`Fernet`/AES/any reversible-encryption library found
none. This confirms the task's own documented fallback applies:
**Phase 9 stores no secret values at all.** A credential "reference"
is the *name* of an environment variable the real secret lives in
(e.g. `BRUD_PROVIDER_SECRET__huggingface__default`), resolved via
`os.environ` only at the moment a connection test actually runs, never
persisted to SQLite, never returned by any API. This is an honest,
documented limitation (Step 4/Section 7 of this doc), not a stand-in
for real secret management — a Phase 10+ concern if ever needed.

`backend/core/json_utils.py::redact_secrets()` (existing, already
reused by Phase 8's tool registry) is reused again here for any
free-form `configuration_json` a connector might log.

### 1.4 Existing Admin Assistant foundation (Phase 8) is reused, not duplicated

`core_model/admin_assistant/dashboard_registry.py` (27-page registry,
`ASSISTANT_MODES`), `action_registry.py` (allowlisted proposable
actions, risk tiers, `BLOCKED_ACTION_SUBSTRINGS`),
`backend/services/admin_assistant_tools.py` (`READ_ONLY_TOOLS`,
`ToolDefinition`, `run_tool()`), and `backend/services/
admin_assistant_service.py` (`ACTION_EXECUTORS`, `propose/review/
execute/cancel`, stale-check fingerprints, preview generators) are all
additively extended in this phase: 4 new read-only tools, up to 6 new
controlled actions, 1 new `dashboard_registry` page entry
(`external_data_providers`, mode `data`). No existing registry entry,
tool, or action is renamed, removed, or reordered.

### 1.5 Migration/schema/audit conventions confirmed unchanged

`SCHEMA_VERSION = 29` today (`backend/database/schema.py` line 3);
`_apply_v29` is the last applied migration
(`backend/database/migrations.py`). The established pattern
(`PHASE{N}_SCHEMA` string constant + `_apply_v{N}(connection)` +
`schema_migrations` insert + `PRAGMA user_version`) is followed
verbatim for migration 030. `AuditLogRepository.append()`
(`backend/database/repositories/phase2.py`) is the single existing
audit sink, reused for every provider mutation and connection test —
no second audit table.

## 2. Why data providers are separate from inference providers

An **inference provider** (Phase 15's `inference_model_assignments`)
answers "which trained model generates this chat reply, and on what
hardware." A **data provider** (this phase) answers "which external
organization/website could Brud AI potentially pull training/RAG
source material from, and under what access terms." They have no
shared lifecycle, no shared trust model, no shared credentials, and
conflating them would make an admin's "is this provider safe to use
for training data" question inseparable from "is this provider safe
to route chat generation to" — two completely different risk
questions. Kept structurally separate: distinct tables, distinct
service module names (`ExternalDataProvider*Service` vs
`ModelAssignmentService`/`InferenceRuntimeService`), distinct API
prefixes, distinct Admin Assistant tool/action names.

## 3. Schema plan (migration 030)

All new, all additive. `SCHEMA_VERSION` 29 -> 30.

| Table | Purpose | Mutability |
|---|---|---|
| `external_data_providers` | One row per known external data provider (built-in or custom). | Mutable (lifecycle/trust/enabled fields); never hard-deleted, only `archived`. |
| `external_data_provider_domains` | Official/api/download/documentation/authentication/mirror domains claimed for a provider, each independently verifiable. | Mutable per-domain verification fields. |
| `external_data_provider_capabilities` | What a provider can be asked to do (search/read metadata/download/etc.), per connector, disabled by default for anything beyond read. | Mutable (admin toggles). |
| `external_data_provider_credentials` | Credential **references** only (env var name, type, status) — never secret values. | Mutable (add/replace/revoke), never returns secret. |
| `external_data_provider_connection_tests` | One row per connection-test run: bounded, read-only, result + evidence. | Append-only (a history log). |
| `external_data_provider_events` | Append-only lifecycle/audit trail specific to this registry (verification decisions, enable/disable/restrict/block, credential changes) — in addition to, not instead of, the existing global `audit_logs`. | Append-only. |

Indexes: `provider_code` unique on `external_data_providers`;
`(provider_id, domain)` unique on domains;
`(provider_id, capability_type)` unique on capabilities;
`(provider_id, credential_type)` unique on credentials (one active
reference per credential type per provider);
`provider_id` indexes on the two log tables for history lookups.

## 4. Connector plan

A strict, minimal Python protocol (`core_model` cannot own it since it
must perform real I/O — it lives in `backend/services/
external_data_connectors/`, mirroring the existing
`backend/services/` convention of one impure module per integration
point):

```python
class ExternalDataProviderConnector(Protocol):
    def test_connection(self, config: ConnectorConfig) -> ConnectionTestResult: ...
    def get_provider_metadata(self, config: ConnectorConfig) -> dict[str, Any]: ...
    def get_capabilities(self, config: ConnectorConfig) -> list[str]: ...
```

Every built-in connector (`AI4BharatConnector`, `HuggingFaceConnector`,
`GitHubConnector`, `WikimediaConnector`, `BhashiniConnector`,
`GenericPublicApiConnector`, `ManualProviderConnector`) implements only
`test_connection`/`get_provider_metadata`/`get_capabilities` — no
search, no download, no write, matching the task's explicit "Phase 9
must not yet implement full dataset search/download." Each connector
receives an injectable HTTP transport callable
(`Callable[[str, dict], HttpResponse]`) so tests never make a real
network call — `test_connection` composes the transport result into a
bounded `ConnectionTestResult`, never raising past its own boundary
(network errors become `status="failed"`, not an unhandled exception).

## 5. Credential handling (concrete decision)

No encrypted-secret infrastructure exists (confirmed in 1.3), so per
the task's own explicit fallback:

- `external_data_provider_credentials` stores `credential_type`
  (`api_key/bearer_token/oauth/username_password/custom_header/
  manual_login`), a `reference_key` (the environment variable name the
  real secret is expected in — never the secret itself),
  `configured` (derived at read time by checking
  `os.environ.get(reference_key)` is non-empty — never stored, always
  recomputed), `last_rotated_at`, `last_tested_at`, `status`.
- No API ever returns `reference_key`'s *value* — only whether it
  resolves to something non-empty (`configured: true/false`).
- Connection tests that require authentication read the referenced
  environment variable at test time only, never log it, never persist
  it, and pass it to the connector's transport call only in memory.
- **Documented limitation**: this is reference-based, not a real
  secrets vault (no rotation enforcement, no per-admin access control
  on who can set the env var, no audit of who read the env value at
  the OS level). Acceptable for Phase 9's scope (registry + bounded
  connection testing only, no data movement); a real secrets-manager
  integration is explicitly Phase 10+ territory if ever needed.

## 6. Admin Assistant integration plan

4 new read-only tools (`list_external_data_providers`,
`get_external_data_provider`, `get_provider_capabilities`,
`get_provider_connection_status`), each a thin wrapper around
`ExternalDataProviderService`, mode `data`, following the exact
`ToolDefinition`/`run_tool()` pattern from Phase 8. Up to 6 new
controlled actions (`register_external_data_provider` moderate,
`verify_external_data_provider` moderate, `test_external_data_provider_connection`
low, `enable_external_data_provider` moderate,
`disable_external_data_provider` low, `configure_provider_credential_reference`
high — touches auth) registered in `core_model.admin_assistant
.action_registry` and wired to real executors in
`admin_assistant_service.ACTION_EXECUTORS`, reusing the exact
propose -> preview -> stale-check -> confirm -> execute -> verify ->
audit pipeline built in Phase 8 — no new proposal mechanism.

## 7. Security risks and mitigations

- **Risk**: an admin could paste an arbitrary URL and expect it to be
  "trusted." **Mitigation**: every new custom provider defaults to
  `trust_status=unverified`, `lifecycle_status=draft`, `enabled=false`
  (Step 12) — nothing is trusted by registration alone; verification
  is a separate, evidence-producing action that never claims domain
  ownership from a page title alone (Step 7).
- **Risk**: a connection test becomes an SSRF/arbitrary-fetch vector.
  **Mitigation**: connection tests only ever hit the specific,
  already-registered domain(s) for that provider via the provider's
  own connector, never an admin-supplied arbitrary URL at test time;
  bounded timeout; read-only HTTP methods only; no redirect-following
  into arbitrary hosts (documented as an implementation requirement in
  the connector transport).
- **Risk**: credential leakage via logs/audit/API responses.
  **Mitigation**: no secret value is ever stored, logged, or returned
  (Section 5); `redact_secrets()` applied to any free-form JSON;
  dedicated tests assert no response body ever contains a configured
  reference's resolved value.
- **Risk**: provider approval silently implies dataset/training
  approval. **Mitigation**: this phase writes to no dataset,
  governance, or lineage table at all — structurally impossible for a
  provider mutation to affect any existing approval state.

## 8. Deferred to Phase 10+ (explicitly out of scope here)

Live dataset search/comparison, dataset-card harvesting, licence
snapshot capture, sample download, quarantine, RAG sandbox ingestion,
training approval/execution, automatic provider discovery, a web
crawler, automated login flows, browser credential automation, and any
real secrets-vault integration beyond the reference-only model in
Section 5.
