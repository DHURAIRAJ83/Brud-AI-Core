# Phase 17 — Knowledge Domain, Freshness, Evidence & Learning-Target Router

Status: implementation complete. This document is the narrative record
of what was built, why, and how it was verified. It follows directly
from `docs/smart_routing/phase17_domain_learning_router_plan.md`
(written first, per the task's own requirement) and from Phase 16's
audit (`docs/smart_routing/phase16_*`).

## 0. What this phase is, and is not

Phase 17 builds a deterministic, explainable, CPU-first **classification
and routing-policy** layer. It never executes Model, RAG, Web, Tool, or
Memory actions. It never touches `/api/chat` or
`ChatOrchestrationService`. Every result returned by every API endpoint
and every Admin Dashboard view is labelled **"Recommendation only -- no
route was executed."**

It produces two independently-computed, independently-stored
recommendations that are never merged into one field:

- **Execution-route recommendation**: `core_model | approved_rag |
  trusted_web | tool | memory | clarify | refuse | insufficient`
- **Learning-target recommendation**: `core_model | rag_only |
  web_preferred | tool_required | evaluation_only |
  future_training_candidate | do_not_learn | blocked`

## 1. Architecture

```
raw text
  -> sanitize (bound length, strip control/bidi chars, NFC normalize)
  -> normalize (backend.services.text_normalization.normalize_text)
  -> language (core_model.rag.language_routing.classify_language)
  -> intent (knowledge_routing.intent_classifier)
  -> domain/subdomain (knowledge_routing.domain_classifier)
  -> freshness/volatility (knowledge_routing.freshness_classifier)
  -> safety-risk signal (knowledge_routing.safety_signal)
  -> ambiguity/clarification (knowledge_routing.ambiguity_classifier)
  -> evidence requirement (knowledge_routing.evidence_classifier)
       [depends on domain + subdomain + freshness + intent + safety + ambiguity]
  -> execution-route recommendation (knowledge_routing.route_recommender)
       [8-step fixed precedence: refuse -> clarify -> memory -> tool ->
        trusted_web -> approved_rag -> core_model -> insufficient]
  -> learning-target recommendation (knowledge_routing.learning_target_recommender)
       [8-step fixed precedence, informed by the execution route]
  -> Tamil-first policy check (knowledge_routing.tamil_first_policy)
       [a cross-cutting validator over the recommended route]
  -> ClassificationResult (explainable, versioned)
```

**Documented deviation from the plan doc's literal Step 2 layer order:**
the plan doc's step list names evidence before ambiguity before safety;
the implementation computes safety and ambiguity before evidence,
because the route-recommender's own required precedence (safety and
ambiguity are gate conditions, checked first) has a hard computational
dependency: the route can only be judged in the same order in which its
gate conditions are evaluated, so evidence-classification -- which
itself depends on safety and ambiguity -- has to run after them. This
is a reasoned resolution of an ordering conflict between two rules in
the same document, not a scope deviation.

Every layer returns a small frozen dataclass (`LayerResult` in
`core_model/knowledge_routing/result_types.py`, or a layer-specific
variant for domain/safety/route/target) with `value`,
`confidence_band` (`high|medium|low|unknown` -- never a fabricated
numeric score), `reason_codes` (stable strings from the registry),
`matched_rules` (the literal keyword/rule hits, for explainability),
and `policy_version`.

## 2. Policy data vs. policy engine

Per the plan's own design decision, split by responsibility:

- **`config/knowledge_routing_policy.json`** -- inert data only:
  bilingual keyword lexicons per domain/subdomain/intent/freshness
  signal, `policy_version`, `taxonomy_version`, and a self-checksum
  (`policy_checksum_sha256`, SHA-256 over the canonical JSON with the
  checksum field excluded from its own hash input -- the exact pattern
  `ProductionRegressionService.compute_manifest_checksum` already
  established for `config/production_regression_manifest.json`).
- **`core_model/knowledge_routing/policy_loader.py`** -- loads,
  schema-validates, and checksum-verifies the policy file, raising
  `PolicyValidationError` and refusing to classify on any mismatch
  (fail closed). `get_policy()` is a process-wide cached singleton;
  `reset_policy_cache()` exists for tests only.
- **The Python modules under `core_model/knowledge_routing/`** -- the
  reviewed, tested, versioned decision engine (route/learning-target
  precedence, Tamil-first validation). Never loaded from the policy
  file, so there is no arbitrary-code-execution surface in the policy
  data.

This satisfies every Step 15 requirement: deterministic, schema-
validated, checksummed, no arbitrary code execution, safe defaults
(`unknown`/low-confidence wherever the policy has no match), invalid
policy blocks classification clearly.

## 3. Taxonomy (summary -- full detail in `phase17_policy_reference.md`)

| Taxonomy | Count |
|---|---|
| Domains | 17 |
| Subdomains | 26 |
| Intents | 18 |
| Freshness values | 6 |
| Evidence-requirement values | 7 |
| Safety-risk values | 5 |
| Safety reason categories | 12 |
| Execution routes | 8 |
| Learning targets | 8 |
| Structured-record context types | 6 |
| Reason codes | 126 |

The subdomain list is a deliberately bounded subset (roughly 2-4 per
top-level domain with meaningful sub-structure), chosen to cover every
worked example and false-positive control, not an exhaustive listing of
every subdomain the task's own examples mentioned. Extending it later
is a pure data change to the checked-in JSON (bump `taxonomy_version`),
never a code change.

## 4. Execution-route and learning-target precedence

Both engines are literal, ordered `if/elif` chains in Python (never a
data-driven precedence list, since precedence logic is exactly the kind
of engine logic the JSON-vs-Python split keeps out of the policy file).

**Execution route** (`route_recommender.recommend_execution_route`):
`refuse` (safety `likely_disallowed`) -> `clarify` (ambiguous) ->
`memory` (domain `personal_context`) -> `tool` (evidence
`deterministic_tool_required`) -> `trusted_web` (evidence
`external_verified_evidence_required`) -> `approved_rag` (evidence
`internal_evidence_required`) -> `core_model` (evidence
`model_knowledge_ok`) -> `insufficient` (fallback).

**Learning target** (`learning_target_recommender.recommend_learning_target`):
`blocked` (safety `likely_disallowed`) -> `do_not_learn` (domain
`personal_context`) -> `tool_required` (route `tool`) -> `web_preferred`
(freshness `real_time`/`time_sensitive`) -> `rag_only` (evidence
`internal_evidence_required`) -> `evaluation_only` (route
`clarify`/`insufficient`/`refuse`/`memory`) -> `future_training_candidate`
(timeless language-skill domain with high/medium route confidence) ->
`core_model` (fallback). **No value this engine returns grants training
approval by itself** -- `grants_training_approval` is hardcoded `False`
everywhere in this phase; `future_training_candidate` only flags
content for a later, separately-approved training cycle.

## 5. Tamil-first policy

`tamil_first_policy.check_tamil_first_policy` is a cross-cutting
validator, not a new pipeline layer. It confirms that Tamil
grammar/meaning/orthography/translation questions correctly prioritize
`core_model` (`tamil_first_policy_applied=True`), and it flags the
specific failure mode named in the task -- a Tamil-language,
volatile-freshness question routed to `core_model` merely because of
its language, rather than because a web/RAG source was actually
irrelevant (`tamil_first_policy_violation=True`). Verified with a real
example: "இன்று தமிழக அரசு அறிவித்த திட்டம் என்ன?" (a Tamil, real-time,
`government_services` question) routes to `trusted_web`, not
`core_model`, and `tamil_first_policy_violation` is `False` -- Tamil
language never overrides freshness/evidence-driven routing.

## 6. Persistence (migration 039)

Schema version 38 -> **39**. One small additive table,
`routing_classification_decisions` (append-only, with
immutable-update/delete triggers matching the existing
`production_*` append-only table convention). Fields: `public_id`,
`input_hash` (SHA-256 hex, **never raw text**), `context_type`,
`language_category`, `intent`, `domain`, `subdomain`, `freshness`,
`ambiguity`, `safety_risk`, `evidence_requirement`, `execution_route`,
`learning_target`, `requires_human_review`, `input_truncated`,
`reason_codes_json`, `policy_version`, `taxonomy_version`,
`created_by_admin_public_id`, `created_at`. No historical migration was
touched; `_apply_v39` follows the exact idempotent-guard +
`executescript` + `schema_migrations` insert + `PRAGMA user_version`
pattern every prior migration uses.

Verified: fresh-database init reaches schema version 39;
`upgrade_database` on an existing (38) database upgrades cleanly;
`PRAGMA foreign_key_check` reports zero violations; the table's
append-only triggers correctly reject `UPDATE`/`DELETE`.

## 7. Service, repository, adapters

- `backend/database/repositories/knowledge_routing.py` ::
  `KnowledgeRoutingRepository` (subclasses `BaseRepository`) --
  create/get/list/aggregate over the new table only.
- `backend/services/knowledge_routing_classification_service.py` ::
  `KnowledgeRoutingClassificationService` -- wraps the pure
  `pipeline.classify()` with optional persistence and audit logging
  (mirrors the `ProductionRegressionService` wrapper pattern).
- `core_model/knowledge_routing/adapters.py` -- structured-record
  adapters for `rag_record`, `dataset_candidate`, `training_candidate`,
  `evaluation_prompt`, and `knowledge_gap_case` (the last one is a
  ready-made entry point for Phase 18+; no knowledge-gap registry
  exists yet, per this phase's explicit out-of-scope list). Each
  adapter flattens only its record's own bounded fields into text --
  never a full raw document body, never a fabricated field.

## 8. API (`/api/admin/knowledge-routing`)

Admin-only (`Depends(require_admin)` router-wide), CSRF-protected on
every POST, following the exact `production_readiness.py` template.
Endpoints: `GET /policy`, `GET /reason-codes`, `GET /context-types`,
`POST /classify`, `POST /classify-record`, `GET /decisions/{id}`,
`GET /decisions`, `GET /metrics`. No endpoint calls Model, RAG, Web,
Tool, or Memory. `ClassificationInputError` is mapped to HTTP 422
(`ValidationError`) at the API boundary, never a raw 500. Confirmed
`/api/chat` is byte-for-byte unchanged (same placeholder response as
Phase 16 documented) and unauthenticated requests to every new endpoint
return 401.

## 9. Admin Dashboard

New top-level Sidebar entry "Knowledge Routing" (kept out of the `Data`
group, mirroring the Phase 15A reasoning for Production Readiness).
`apps/admin-dashboard/src/pages/KnowledgeRoutingPage.jsx`, 6 tabs:
Overview, Try Classifier, Structured Record, Recent Decisions, Reason
Codes, Policy. Every classification result view carries the literal
banner "Recommendation only -- no route was executed."

## 10. Admin Assistant

5 new read-only tools in `backend/services/admin_assistant_tools.py`
(`get_knowledge_routing_policy`, `list_knowledge_routing_reason_codes`,
`get_knowledge_routing_metrics`, `list_knowledge_routing_decisions`,
`preview_knowledge_routing_classification` -- the last classifies
without persisting, so it stays strictly read-only). No new mutating
`ActionDefinition` was added: the classifier has nothing safe to mutate
beyond its own append-only diagnostic log, and the task's own guidance
was "only if genuinely useful, minimal." A new `PageEntry` in
`core_model/admin_assistant/dashboard_registry.py` gives the existing,
unmodified `classify_intent()` free help/navigation awareness of the
new page -- verified directly: "help me with knowledge routing" and
"take me to Knowledge Routing" both resolve `matched_page_id ==
"knowledge_routing"`.

## 11. Data Overview integration

`apps/admin-dashboard/src/pages/DataOverviewPage.jsx` gained one new
metrics group (`knowledgeRoutingMetrics`) showing "Knowledge-routing
classifications recorded" and "Knowledge-routing decisions needing
human review" -- both real, fetched counts, never fabricated -- plus an
"Open Knowledge Routing" quick action.

## 12. Reason-code registry

See `phase17_reason_codes.md` for the full table. 126 stable codes,
served by `GET /api/admin/knowledge-routing/reason-codes` and the
`list_knowledge_routing_reason_codes` tool. Every code any classifier
layer can emit is asserted, at classification time, to exist in the
registry (`pipeline.classify()` asserts this on every call).

## 13. Testing

76 new backend/core_model/database tests (all passing) plus 5 new
frontend tests (all passing, 161/161 frontend tests total). Coverage:
taxonomy/reason-code consistency, policy checksum/schema/tamper
handling, 9 worked-example scenarios (including the two hardest cases:
Tamil grammar staying on `core_model`, and Tamil government-scheme-
today correctly leaving `core_model` for `trusted_web`), 3 Step-23
false-positive controls, 11 Step-25 security/robustness cases (oversized
input, control/bidi/zero-width characters, empty/non-string input,
unknown context type, HTML/script, SQL-like text, prompt-injection-
style text, secret-like text never appearing in the stored hash),
determinism, service/repository persistence and append-only enforcement,
8 API tests (auth, CSRF, validation, persistence, 404, metrics), and 11
Admin Assistant/dashboard-registry tests.

## 14. Performance (Step 24, real measured numbers)

Pure `pipeline.classify()` (no persistence, no DB, no network, no model
load):

| Scale | Total | Per-question |
|---|---|---|
| n=1 | 1.41 ms | 1.41 ms |
| n=100 | 23.24 ms | 0.232 ms |
| n=1000 | 232.02 ms | 0.232 ms |

(measured on the dev machine; the n=1 figure includes the one-time
policy-file load/checksum-verify, cached for the process lifetime via
`functools.lru_cache` thereafter.) No model load, no network call, no
DB-heavy scan, no vector search -- confirmed by inspection: `pipeline.py`
imports only `core_model.*` and `backend.services.text_normalization`,
never a database or HTTP client module.

## 15. Security controls (Step 25)

Verified directly (see §13): oversized text is bounded and truncated,
never crashes; control characters and bidirectional-override characters
are stripped defensively before classification; zero-width characters
are handled (inherited from `text_normalization.normalize_text`);
prompt-injection-style and HTML/script/SQL-like text classify without
crashing and without being granted any special execution path (nothing
in this phase executes anything, so there is no injection target);
secret-like text is never present in the stored `input_hash`; policy-
file tampering (checksum mismatch) and invalid policy schema both fail
closed with `PolicyValidationError`; no `eval`/`exec`/`pickle`/
`subprocess`/`os.system` anywhere in the new code (grepped, zero
matches); every API endpoint requires admin auth and CSRF on writes; no
endpoint executes a route.

## 16. Known limitations / deferred to Phase 18+

- Bilingual deterministic help content (Step 19) is provided by the
  existing generic `get_page_help` tool + `DASHBOARD_PAGES.purpose`
  mechanism (the same mechanism every other Admin Dashboard page
  relies on), not a bespoke 10-question FAQ -- no bespoke FAQ exists
  for any other Phase 8-16 page either, so this keeps the same
  established pattern rather than introducing a new, inconsistent one.
- The classifier is not wired in front of `ChatOrchestrationService` or
  `/api/chat` -- by design; Phase 16's audit found the public chatbot is
  still a placeholder, and this phase deliberately does not decide that
  wiring (per its own non-negotiable rules).
- No knowledge-gap registry exists yet; `adapters.adapt_knowledge_gap_case`
  is a ready entry point for whichever future phase adds it.
- `fallback_route_order` on `RouteRecommendation` is advisory-only and
  consumed by nothing yet, exactly as documented in the plan.

## 17. Files created / modified

**Created:** `core_model/knowledge_routing/__init__.py`,
`reason_codes.py`, `result_types.py`, `policy_loader.py`,
`intent_classifier.py`, `domain_classifier.py`, `freshness_classifier.py`,
`ambiguity_classifier.py`, `safety_signal.py`, `evidence_classifier.py`,
`route_recommender.py`, `learning_target_recommender.py`,
`tamil_first_policy.py`, `pipeline.py`, `adapters.py`;
`config/knowledge_routing_policy.json`;
`backend/database/repositories/knowledge_routing.py`;
`backend/services/knowledge_routing_classification_service.py`;
`backend/api/routes/knowledge_routing.py`;
`apps/admin-dashboard/src/pages/KnowledgeRoutingPage.jsx` (+ `.test.jsx`);
7 new test files under `tests/core_model/`, `tests/backend/`,
`tests/database/`; this document plus `phase17_policy_reference.md` and
`phase17_reason_codes.md`.

**Modified:** `backend/database/schema.py` (SCHEMA_VERSION 38->39,
`PHASE39_SCHEMA`, `MIGRATION_039_NAME`); `backend/database/migrations.py`
(`_apply_v39`, dispatch chain); `backend/api/router.py` (router
registration); `apps/admin-dashboard/src/App.jsx`,
`Sidebar.jsx`, `services/api.js`, `DataOverviewPage.jsx` (+ `.test.jsx`);
`backend/services/admin_assistant_tools.py` (5 new tools);
`core_model/admin_assistant/dashboard_registry.py` (new `PageEntry`);
`config/production_regression_manifest.json` (5 new batches,
`manifest_version` 2->3, recomputed checksum).
