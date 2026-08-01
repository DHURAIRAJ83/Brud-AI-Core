# Phase 10 Plan — Live Dataset Discovery, Normalization & Comparison

Written before implementation, per this phase's Step 1. See
[phase10_live_dataset_discovery.md](phase10_live_dataset_discovery.md)
for the final, as-built report (status, deviations, bugs found and
fixed, test counts, manual verification results).

## 1. Systems reused (confirmed by direct inspection)

- **Phase 9 External Data Provider Registry** (`external_data_providers`
  + 5 child tables, `ExternalDataProviderService`/`*CredentialService`/
  `*ConnectionService`/`*CapabilityService`,
  `backend/services/external_data_connectors/`). This phase never
  duplicates it -- discovery only ever *reads* provider rows (`enabled`,
  `lifecycle_status`, capabilities, credential status) and resolves a
  credential value through the existing
  `ExternalDataProviderCredentialService`/env-var-reference model. No
  new provider table, no new credential table.
- **Connector contract** (`backend/services/external_data_connectors/base.py`):
  `ExternalDataProviderConnector` Protocol, `BaseHttpConnector`,
  `ConnectorConfig`, `HttpResponse`, `default_http_transport`. Extended
  *additively* (Step 3) -- every existing method/field keeps its exact
  signature; `HttpResponse` gains one new trailing field with a default
  (`body: str = ""`, bounded at read time) so search connectors can
  parse a JSON body, which `test_connection`/`get_capabilities` never
  needed before. This is backward compatible: every existing call site
  constructs `HttpResponse` via keyword arguments.
- **Source & Rights Registry** (`data_sources`, Data Studio Phase 2):
  confirmed untouched by this phase -- discovery candidates are *not*
  `data_sources` rows. A future Phase 11+ that decides to actually
  import a candidate is expected to create one through the existing,
  unmodified `SourceRegistryService`, exactly as a manually found
  source would. `source_type='manual'` (mentioned in the task's Step 4
  for manual candidate entry) refers to a *new*, Phase-10-local
  candidate provenance concept, not `data_sources.source_type`'s
  existing CHECK-constrained enum (`human_created, admin_created, ...`)
  -- the two are never conflated; Phase 10 defines its own
  `candidate_entry_method` value on `external_dataset_candidates`
  instead of touching that constraint.
- **Admin Assistant foundation** (Phase 8): `core_model/admin_assistant/
  dashboard_registry.py`/`action_registry.py`,
  `backend/services/admin_assistant_tools.py` (`READ_ONLY_TOOLS`),
  `backend/services/admin_assistant_service.py` (`ACTION_EXECUTORS`,
  propose -> preview -> stale-check -> confirm -> execute -> verify ->
  audit). Reused verbatim -- no new proposal table, no new tool-registry
  shape.
- **Language routing** (`core_model/rag/language_routing.py`,
  Phase 16): `classify_language()` returns short codes (`ta, en, tgl,
  mixed, unknown`) used for *detecting the language of an admin's chat
  message*. Phase 10's requirement/candidate `languages` field uses the
  task's own full-word vocabulary (`tamil, english, tanglish, mixed,
  other, unknown`) -- a different vocabulary for a different purpose
  (a dataset's declared/inferred language content, potentially
  multiple, not a single detected reply language). A small, explicit
  mapping (`ta->tamil, en->english, tgl->tanglish, mixed->mixed,
  unknown->unknown`) lets the Assistant reuse `classify_language()`
  when inferring a requirement's language from a Tamil admin message,
  without merging the two enums into one.
- **Audit** (`AuditLogRepository.append`), **redaction**
  (`backend/core/json_utils.py::redact_secrets`), **pagination**
  (`BaseRepository.pagination`), **migration conventions**
  (`PHASE{N}_SCHEMA` + `_apply_v{N}` + `schema_migrations` insert +
  `PRAGMA user_version`) -- all reused exactly as in Phases 1-9.

## 2. Provider connector extension strategy

Two new Protocol methods, additive:

```python
def search_datasets(self, config: ConnectorConfig, transport: HttpTransport, request: DatasetSearchRequest) -> DatasetSearchResult: ...
def get_dataset_metadata(self, config: ConnectorConfig, transport: HttpTransport, provider_dataset_id: str) -> NormalizedDatasetMetadata | None: ...
```

`BaseHttpConnector` gains a default implementation of both that returns
`unsupported` (mirroring `ManualProviderConnector`'s existing honesty
pattern) -- only connectors that actually implement a real search path
override them. This means every one of the 7 existing connectors keeps
working unchanged for `test_connection`/`get_capabilities`; only
`HuggingFaceConnector`, `GitHubConnector`, and `WikimediaConnector`
gain a real `search_datasets` override (Step 4). `AI4BharatConnector`
and `BhashiniConnector` keep the inherited `unsupported` default,
honestly, since (confirmed by inspecting their actual public surfaces)
neither exposes a stable, unauthenticated, machine-readable dataset
*search* endpoint reachable in this environment -- their existing
`supports_manual_discovery=True` provider-level flag (Phase 9) is the
correct, already-modeled path for them, not a fabricated search
integration.

## 3. Schema design (migration 031)

8 new, all-additive tables (Step 2's exact list): search sessions,
requirements (1:1 with a session), provider runs (1:N), candidates
(1:N, deduplicated), candidate sources (1:N per candidate -- the raw
per-provider evidence), candidate scores (1:N per candidate, one row
per scoring dimension for full explainability), candidate comparisons
(a saved N-way comparison), and an append-only search-event log
(mirroring Phase 9's `external_data_provider_events` pattern exactly).

Field-provenance tracking (Step 2's `admin_explicit` /
`assistant_inferred` / `unknown` requirement) is stored as three JSON
object columns on the requirements row
(`inferred_fields_json`/`confirmed_fields_json`/`unknown_fields_json`,
mapping field name -> value/reason) rather than a per-field relational
table -- proportionate for a handful of requirement fields, consistent
with how Phase 6/9 already store small structured JSON blobs
(`warnings_json`, `blocking_reasons_json`, etc.) rather than
over-normalizing.

## 4. Normalized candidate model

One `DatasetSearchRequest`/`NormalizedDatasetMetadata` pair
(`core_model/data_discovery/`, pure dataclasses + enums) is the
contract every connector's `search_datasets`/`get_dataset_metadata`
must honor. Every field the task lists (Step 3) is present; any field
a connector cannot determine is `None`/empty, never invented --
`_UNKNOWN` sentinels are never silently coerced into a real-looking
value. `raw_metadata` is the connector's own untruncated-at-this-layer
dict; bounding/redaction/checksums happen once, centrally, in
`ExternalDatasetNormalizationService` (Step 6), not duplicated per
connector.

## 5. Search session lifecycle

`draft -> ready -> running -> (partial | completed | failed) |
cancelled | expired`, matching Step 2's recommended statuses exactly.
`ExternalDatasetSearchService` owns the transitions; every transition
is recorded as an `external_dataset_search_events` row (append-only)
in addition to updating the session row itself -- the same
derived-vs-stored-state discipline already used for Phase 8's proposal
lifecycle (nothing here invents a *second* state machine pattern).

## 6. Ranking model

A pure function per scoring dimension
(`core_model/data_discovery/scoring.py`), each returning
`{dimension, raw_value, weight, score, reason}` -- the exact shape
Step 8 requires for reproducibility. The final `suitability_score` is
a fixed weighted sum of dimension scores minus penalty dimensions,
computed the same way every time for the same inputs (no randomness,
no external call, no popularity signal). Explicitly *not* a
"popularity" or "download count" dimension, per the task's own rule.

## 7. Deduplication strategy

Conservative, signal-based, never title-similarity-based (Step 7): two
candidates are auto-merged only when they share an exact
`provider_dataset_id` re-seen from the same provider, or a normalized
`(organization, name)` pair, or an identical `repository_url`/
`homepage_url`/`dataset_card_url`, or an identical canonical
identifier/version+revision pair. Anything weaker (e.g. similar titles,
different organizations) becomes a `possible_duplicate_group` flag for
human review instead of an automatic merge -- every provider source row
is preserved either way, never discarded on merge.

## 8. Security boundaries

- **No arbitrary domain fetches**: `search_datasets`/
  `get_dataset_metadata` only ever call the provider's own
  already-registered `api`/`official` domain (via the same
  `ConnectorConfig.domains` mechanism `test_connection` already uses)
  -- never a domain found inside a dataset's metadata/description, and
  never an admin-supplied URL. `default_http_transport` keeps
  `follow_redirects=False`; a connector that receives a redirect
  response for a search call must fail closed (`unsupported`/`failed`),
  never silently follow it.
- **No file download**: connectors return metadata dicts only; nothing
  in this phase ever calls anything resembling a file-content GET
  beyond a single bounded metadata JSON response.
- **No shell/script execution from provider content**: dataset
  names/descriptions/tags/authors are treated as untrusted display
  strings everywhere (React's default text-escaping on the frontend;
  never interpolated into any backend command, path, or SQL string).
- **Bounded everything**: `MAX_PROVIDERS_PER_SEARCH`,
  `MAX_RESULTS_PER_PROVIDER`, `MAX_CANDIDATES_PER_SESSION`,
  `PER_PROVIDER_TIMEOUT_SECONDS`, `OVERALL_SEARCH_DEADLINE_SECONDS`,
  `MAX_RAW_METADATA_BYTES`, `MAX_RETRIES_PER_PROVIDER` -- explicit
  constants in `core_model/data_discovery/__init__.py`, conservative
  enough for this sandboxed test environment (Step 11).
- **Partial-failure isolation**: `ExternalDatasetProviderSearchService`
  wraps every single provider call in its own try/except -- one
  provider's exception, timeout, or malformed response becomes a
  `provider_runs` row with `status='failed'`/`'timeout'`/etc. and never
  aborts the other providers' runs or raises out of the overall search.

## 9. Deferred licence verification (explicitly, per the task's own rule)

`declared_licence` on a candidate is stored and displayed exactly as
the provider reported it, with `licence_status` defaulting to
`unknown`/`declared` (never `verified`) -- this phase adds no licence
*verification* logic (no fetching/parsing a LICENSE file, no legal
classification, no terms-of-service snapshot). Every recommendation
text ends by pointing at Phase 11 licence/evidence verification as the
required next gate before any training/RAG/commercial use.

## 10. Phase 11 handoff

A future phase should: consume `external_dataset_candidates` rows
marked `recommendation_status IN ('recommended_for_review',
'possible')` to perform real licence-evidence verification (fetching
and parsing an actual LICENSE/terms page, snapshotting it, and setting
`licence_status='verified'` or similar) -- entirely additive to this
phase's tables, never rewriting them; and, only after that gate, decide
whether a candidate becomes a real `data_sources` row through the
existing Source & Rights Registry.
