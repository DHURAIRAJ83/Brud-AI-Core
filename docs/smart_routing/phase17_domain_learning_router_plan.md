# Phase 17 — Knowledge Domain, Freshness, Evidence & Learning-Target Router: Plan

Written before any Phase 17 code, per the task's own requirement. This
phase builds a deterministic, explainable, CPU-first classification and
routing-*policy* layer only — it recommends, it never executes Model,
RAG, Web, Tool, or Memory actions, and it never touches `/api/chat` or
`ChatOrchestrationService`.

## 0. Existing modules reused (confirmed by direct inspection, not assumed)

- `core_model/rag/language_routing.py::classify_language()` /
  `routing_decision()` — the language layer. Reused verbatim as the
  first pipeline stage; not reimplemented.
- `core_model/conversation/language_continuity.py::decide_language()` —
  referenced as the precedent for "explicit request > confirmed
  preference > detection" precedence style, applied to the new
  route/target recommenders' own precedence design (not called
  directly — it is conversation-turn-specific, and Phase 17 has no
  conversation-turn context yet).
- `core_model/model_evaluation/__init__.py::SAFETY_CATEGORIES` (11
  categories) — reused verbatim as the safety-risk taxonomy's category
  vocabulary.
- `core_model/model_evaluation/refusal_checks.py` — reused as a
  **structural template** (bounded, explicit marker tuples, conservative
  default) for the new *input-side* safety-risk signal; its own marker
  lists detect refusal in **model output**, a different direction, so
  they are not called directly — new input-classification marker lists
  are added following the identical pattern.
- `core_model/admin_assistant/intent.py` — reused as the **structural
  template** for every new deterministic classifier in this phase
  (small bilingual keyword tuples, `_hits()`-style matching, a
  frozen-dataclass result, `INTENTS`/lexicon constants as the single
  source of truth). Not imported directly (it is Admin-Assistant-page-
  navigation-specific), but its pattern is followed exactly.
- `backend/services/text_normalization.py::normalize_text()` — reused
  verbatim as the pipeline's normalization stage.
- `core_model/instruction_tuning/language_checks.py::script_ratios()` —
  transitively reused via `language_routing.py`.
- `core_model/feedback/__init__.py` — reused as the **structural
  template** for taxonomy modules (`core_model/<package>/__init__.py`
  exporting plain tuples as the single source of truth, documented as
  mirroring the schema's own `CHECK` constraints).
- `core_model/admin_assistant/action_registry.py` /
  `dashboard_registry.py` — reused verbatim as the registration
  mechanism for the new Admin Assistant tools/actions and the new
  Admin Dashboard page entry (Phase 15A already added a `production_
  readiness` `PageEntry` this same way; Phase 17 adds one more).
- `config/production_regression_manifest.json` +
  `ProductionRegressionService::compute_manifest_checksum()`/`validate_
  manifest_schema()` — reused as the **structural template** for the
  new policy file's self-checksum/validation mechanism (same pattern:
  JSON payload, checksum field excluded from its own hash input,
  recomputed and compared on load).
- `backend/database/repositories/base.py::BaseRepository` — reused
  verbatim as the base class for the new repository.
- `backend/api/routes/production_readiness.py` — reused as the
  structural template for the new Admin-only route file (`Admin
  Dependency`/`CsrfDependency`/`SettingsDependency`, router-wide
  `require_admin`).
- `AuditLogRepository` — reused verbatim for audit coverage.

Nothing above is modified. Phase 17 only adds new modules that call
into or sit beside these.

## 1. Classifier architecture

A layered, pure-function pipeline
(`core_model/knowledge_routing/pipeline.py::classify()`), each layer a
small deterministic module under `core_model/knowledge_routing/`,
mirroring `intent.py`'s style exactly:

```
raw text
  -> normalize (text_normalization.normalize_text)
  -> language (language_routing.classify_language)
  -> intent (knowledge_routing.intent_classifier)
  -> domain/subdomain (knowledge_routing.domain_classifier)
  -> freshness/volatility (knowledge_routing.freshness_classifier)
  -> ambiguity/clarification (knowledge_routing.ambiguity_classifier)
  -> safety-risk signal (knowledge_routing.safety_signal)
  -> evidence requirement (knowledge_routing.evidence_classifier)
       [depends on domain + freshness + intent + safety]
  -> execution-route recommendation (knowledge_routing.route_recommender)
       [depends on all of the above, in a fixed precedence order]
  -> learning-target recommendation (knowledge_routing.learning_target_recommender)
       [depends on execution route + domain + freshness + safety]
  -> Tamil-first policy check (knowledge_routing.tamil_first_policy)
       [a cross-cutting validator over the recommended route, not a new layer]
  -> ClassificationResult (explainable, versioned)
```

Every layer returns a small frozen dataclass with exactly the fields
Step 2 requires: `value`, `confidence_band` (`high|medium|low|unknown`
— never fabricated numeric precision), `reason_codes` (tuple of stable
strings from the registry), `matched_rules` (tuple of the specific
keyword/rule hits, for explainability), `policy_version`.

## 2. Policy data vs. policy engine (the JSON-vs-Python decision)

Per the task's own offered alternative ("`config/knowledge_routing_
policy.json` or a Python policy registry if that is more consistent"),
Phase 17 uses **both, split by responsibility**, mirroring the exact
precedent the canonical regression manifest already established:

- **`config/knowledge_routing_policy.json`** holds only *data*: bilingual
  keyword lexicons per domain/subdomain/intent/freshness-signal, the
  reason-code registry (code → human description), and the declared
  `policy_version`/`taxonomy_version`. Pure data, no executable content,
  safe to be schema-validated and self-checksummed exactly like the
  regression manifest (`compute_manifest_checksum`-style: SHA-256 over
  canonical JSON with the checksum field excluded from its own input).
- **The Python modules under `core_model/knowledge_routing/`** hold the
  *engine*: the deterministic matching logic, the route/learning-target
  precedence order, and the Tamil-first validator. This is reviewed,
  tested, versioned code — not admin-editable content — matching how
  `production_regression_service.py` is the trusted engine that resolves
  the (separately trusted, checksummed) manifest.

This split satisfies every Step 15 requirement simultaneously:
deterministic (both parts are), schema-validated (the JSON), checksummed
(the JSON), no arbitrary code execution (the JSON has none; the engine
is ordinary reviewed code, not loaded from the policy file), safe
defaults (unknown/low-confidence everywhere the policy has no match),
invalid policy blocks classification clearly (checksum/schema mismatch
raises `ValidationError` the same way `ProductionRegressionService.
load_manifest()` already does for the regression manifest).

## 3. Taxonomy sizing decision

Per Step 3's own instruction ("do not create an excessively large
taxonomy without evidence"), Phase 17 implements **all** required
top-level domains (17) and intents (18) and freshness values (6) and
evidence-requirement values (7) and execution routes (8) and
learning-targets (8) in full, plus a **deliberately bounded subset** of
the "recommended optional" subdomains — the ones needed to satisfy every
worked example in Step 22 and Step 23, plus a small number of clearly
analogous siblings for each required domain (roughly 2-4 subdomains per
top-level domain that has meaningful sub-structure, not all ~30 listed).
This is stated explicitly, not hidden: the full list actually
implemented is in `phase17_policy_reference.md`. Extending the subdomain
list later is a pure data change to the checked-in JSON (bump
`taxonomy_version`), never a code change — this is a deliberate design
property, not a limitation.

## 4. Freshness detection design

A bilingual keyword-signal classifier (`freshness_classifier.py`)
following the exact required signal list (today/now/current/latest/
recent/this week/price/weather/news/score/schedule/law/rule/government
scheme/software version/API version/office holder/availability/
deadline/exchange rate, plus Tamil equivalents), returning one of
`timeless|slow_changing|time_sensitive|real_time|historical|unknown`.
Historical is detected via an explicit past-year/past-event marker set
(e.g. a 4-digit year token more than ~2 years old relative to a fixed
reference, or explicit "in 2020"/historical-marker phrasing) —
deliberately conservative: unmatched text defaults to `unknown`, never
guessed as `timeless` (a stale-answer risk) or `real_time` (an
over-triggering risk).

## 5. Clarification/ambiguity design

`ambiguity_classifier.py` looks for the required signal categories
(missing subject/object, unclear pronoun with no antecedent, unknown
acronym, incomplete action verb with no target, conflicting instruction
markers) using small bounded rule checks — never "every short sentence
is ambiguous" (Step 23's explicit false-positive control; a short but
complete question like "987654 × 12345" or "18748 English words" must
never be flagged). Unsafe requests are checked *before* ambiguity in the
route-precedence order (Step 9's own precedence list), so an unsafe
request is never reclassified as merely needing clarification.

## 6. Execution-route and learning-target engines

Both implement exactly the precedence orders given in Steps 9 and 10 as
literal, tested, ordered if/elif chains (not a data-driven precedence
list in JSON — precedence logic is exactly the kind of "engine" logic
§2 keeps in Python). Each recommendation carries `route_blockers`/
`training_risk`/`requires_human_review` and a `fallback_route_order`
that is explicitly documented as advisory-only in this phase (never
consumed by any execution code, since no execution exists yet).

## 7. Persistence decision (Step 14)

**A migration is required.** Data Overview integration (Step 20) needs
real, non-fabricated aggregate metrics ("classification tests run",
"low-confidence classifications", etc.) that must be queryable across
calls, which is impossible without persisting *something*. Per Step 14's
explicit guidance, exactly one small additive table is added —
`routing_classification_decisions` — storing only the fields Step 14
lists (never raw question text; only a SHA-256 `input_hash` plus the
structured classification outputs). This becomes **migration 039**,
schema version 38 → 39. No existing table, trigger, or migration is
touched. Full schema detail in §"Migration" of the implementation
doc.

## 8. API design

`backend/api/routes/knowledge_routing.py`, `prefix="/admin/knowledge-
routing"`, router-wide `Depends(require_admin)` (exact `production_
readiness.py` pattern). Every endpoint in Step 16's list, `CsrfDependency`
on the 3 POST endpoints, `SettingsDependency`-only on the 5 GET
endpoints (matching the established convention that reads don't need
CSRF). Bounded input (`max_length` on every text field, mirroring
`ChatRequest`'s own `max_length=4000`). No endpoint calls the model, RAG,
web, memory, or any tool — every endpoint calls only the pure
classification pipeline (+ the persistence/audit wrapper).

## 9. Admin Dashboard design

One new page, `Knowledge Routing`, registered in `Sidebar.jsx`'s
`navTree` (top-level, matching `Production Readiness`'s placement
style — a governance/inspection page, not a data-track page, so it is
**not** added under the `Data` group, mirroring the Phase 15A reasoning
that kept Production Readiness out of Data Overview's scope). Tabs
exactly as Step 17 lists. Every classifier result view carries a fixed,
literal banner: **"Recommendation only — no route was executed."**

## 10. Admin Assistant role

5 read-only inspection tools (Step 18's first list) registered the
identical way Phase 15A's 76 actions already are —
`ActionDefinition`/`ACTION_EXECUTORS`/`STALE_CHECK_FINGERPRINTS`/
`PREVIEW_GENERATORS`, plus (only if genuinely useful, minimal) up to 2
low-risk proposal-only actions from Step 18's second list. None call the
model/RAG/web/tool; all risk levels `low`; audited identically to every
existing action. The `BLOCKED_ACTION_SUBSTRINGS` guard remains untouched
and still applies.

## 11. Phase 18 handoff

Phase 17 hands Phase 18 exactly: a pure, importable `classify()` function
returning a fully-explained `ClassificationResult` with a `recommended_
execution_route` and `recommended_learning_target`; a versioned,
checksummed policy `knowledge_routing_policy.json` that Phase 18 can
extend (new keyword hits, same schema) without touching engine code;
zero coupling to `/api/chat` or `ChatOrchestrationService` (deliberately
— Phase 18 decides how/whether to wire this pipeline in front of the
real orchestration engine, per the Phase 16 audit's own headline
finding). Phase 17 does not decide that wiring; it only makes the
decision layer exist, correctly, testably, and explainably.

## 12. Pass/fail criteria for this plan

Phase 17 code begins once this document is committed to disk, matching
the Phase 15A/16 precedent.
