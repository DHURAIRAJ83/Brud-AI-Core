# Phase 20 — Trusted Web Search, Source Verification, Deterministic Tool Gateway & MCP-Ready Execution Foundation — Plan

## 1. Demand evidence from Phase 19

Phase 19 shipped `get_web_demand_summary` / `get_tool_demand_summary` (Admin API +
Admin Assistant tool), backed by `KnowledgeGapRepository.web_demand_summary()` /
`tool_demand_summary()`. Checked directly against this repo's persistent dev
database (`data/database/brud_ai.db`): it is still at schema migration 40 (Phase
18) and was never advanced to 41, because every Phase 18/19 verification pass in
prior sessions ran against isolated, ephemeral test databases (pytest `tmp_path`
fixtures and disposable Playwright-session databases), never against this
long-lived file. There is therefore no persisted public-chat traffic anywhere in
this environment, and consequently zero real knowledge-gap demand rows to query —
not a "low count," but a genuine absence of any production-like data source. This
is expected for a development environment that has never been deployed publicly,
and does not block Phase 20:
the spec's own Step 2 gives a concrete minimum scope to implement regardless of
live volume, and instructs "if Phase 19 data shows another category has
substantially higher demand, document it" — with zero live traffic, there is no
such signal, so the minimum scope is what ships. The demand-summary endpoints
themselves become meaningful once Phase 20 is live and public traffic starts
flowing through `trusted_web`/`tool` routes, at which point Admin can see real
category-level demand and prioritize Phase 21+ provider/tool expansion accordingly
— this is the intended feedback loop, not a gap in this phase.

**Web categories implemented (per Step 2 minimum, unchanged since no override
signal exists):** `current_software_documentation`, `government_service_information`,
`current_rules_and_regulations`, `current_general_information`,
`official_product_documentation`.

**Tools implemented (per Step 2 minimum):** `calculator`, `unit_conversion`,
`date_time_arithmetic`.

No weather/finance/sports/email/calendar/government-application-execution/browser-
automation/account-action capability is added — all explicitly out of scope and
not justified by any demand evidence.

## 2. Existing systems reused (not reinvented)

| Need | Reused from | Notes |
|---|---|---|
| Route plug-in point | `core_model/public_chat/route_availability.py::resolve_route_availability()` | `trusted_web`/`tool` branches currently always return `insufficient`; Phase 20 adds real health/availability checks to those two branches only — no other route touched. |
| Phase 17 "needs live evidence" signal | `core_model/knowledge_routing/evidence_classifier.py` (`_TOOL_INTENTS`, freshness `real_time`/`time_sensitive`) | Unmodified. Phase 20 consumes the already-computed `domain`/`subdomain`/`intent`/`freshness` fields Phase 17 hands to `PublicChatRoutingService`; it does not reclassify. |
| SSRF-safe fetch | `backend/services/dataset_verification_transport.py::fetch_evidence()` / `is_domain_allowed()` / `default_resolver()` | This Phase-11 function already implements domain allowlist + DNS/IP safety check + bounded single re-validated redirect + byte cap + MIME allowlist + HTML/PDF/text/JSON extraction, via an injectable transport/resolver (real I/O never hits test code). `SafeWebFetcher` calls it directly with a Web-policy-derived `allowed_domains` set, rather than re-implementing SSRF logic a third time. |
| PDF extraction | Same module's `_extract_pdf_embedded_text()` (via `fetch_evidence`) | No new PDF library added; `PyMuPDF` (`fitz`) already a hard dependency. |
| HTML text stripping | `core_model.corpus.text_extraction.extract_html_snapshot_text()` (used inside `fetch_evidence`) | Reused unchanged as the main-content fallback; Phase 20 layers a small additional regex pass for `<title>`/canonical-link/meta-date extraction (Step 8 needs fields `fetch_evidence` doesn't extract) — this is new code, but it augments rather than replaces the existing stripper. |
| Rate limiting | `backend/services/public_chat_rate_limiter.py::check_rate_limit(key, max_requests, window_seconds)` | Generic keyed fixed-window limiter, reused with new keys (`web_search`, `web_fetch`, `tool_exec`, per-domain) and new `Settings` fields for the budgets, exactly like Phase 18's own public-chat limit. |
| Injection filtering | `core_model.rag.injection_filter` (base) → `core_model.conversation.injection_guard` (Phase 16→conversation extension pattern) | Phase 20 adds a third extension in the same lineage: `core_model.public_chat.web_injection_guard`, reusing `detect_injection_signals`/`classify_injection_status` and adding Web-specific categories (citation manipulation, secret-disclosure request) exactly as `injection_guard.py` added memory-specific categories on top of the RAG base. |
| Citation shape | `backend/models/public_chat.py::PublicCitation` / `backend/services/public_citation_adapter.py` | `PublicCitation.source_type` literal widened from `["rag","memory"]` to `["rag","memory","web"]`; a **new** `web_citations_for_evidence()` function is added to `public_citation_adapter.py` (same file, same dict shape) because Web evidence is produced synchronously in-request (no `chat_response_citations` DB row to join against) — this is not a second citation *system*, it is a second citation *source* feeding the one existing `PublicCitation` model, matching how `rag`/`memory` already coexist there. |
| Admin Assistant governance | `core_model/admin_assistant/action_registry.py` (`ActionDefinition`, `BLOCKED_ACTION_SUBSTRINGS`) + `backend/services/admin_assistant_service.py` (`ACTION_EXECUTORS`/`PREVIEW_GENERATORS`/`STALE_CHECK_FINGERPRINTS`) | New actions follow the identical propose→preview→confirm-with-stale-check→execute→verify→audit pipeline; no new governance mechanism. |
| Config/policy conventions | `backend/core/config.py` `Field(default=..., validation_alias="BRUD_...")` pattern; `backend/services/production_regression_service.py::compute_manifest_checksum()`/`load_manifest()` | `config/trusted_web_policy.json` mirrors the manifest's exact checksum-over-sorted-JSON, fail-closed-on-mismatch pattern (`load_policy()`/`compute_policy_checksum()`/`validate_policy_schema()`, raising the same `ValidationError`/`NotFoundError` from `backend.database.repositories.base`). |
| Migration/schema conventions | `backend/database/schema.py` `SCHEMA_VERSION`/`MIGRATION_0XX_NAME`/`PHASE0X_SCHEMA`; `backend/database/migrations.py::_apply_v41()` | Migration 042 follows the identical `_apply_v42()` guard-then-executescript-then-record pattern. |
| Knowledge-gap capture/repository | `backend/services/knowledge_gap_capture_service.py`, `backend/database/repositories/knowledge_gap.py`, `knowledge_gap_cases`/`knowledge_gap_occurrences` | Unmodified. Phase 20 only *reads* open `web_capability_gap`/`tool_capability_gap` cases to attempt resolution linkage; it does not alter Phase 19's capture pipeline. |
| Admin API router registration | `backend/api/router.py` | Two new routers appended to the existing `include_router(...)` list, same pattern as every prior phase. |

## 3. A real, non-trivial design decision: resolution-type taxonomy

`knowledge_gap_resolution_events.resolution_type` has a **sealed** SQLite `CHECK`
constraint from migration 041 (append-only table). Phase 19's own precedent for
this exact situation (`public_chat_feedback_events.feedback_type`) was: never widen
a sealed CHECK via a later migration; represent the new concept at a different
layer instead. Phase 20 follows the same precedent rather than introducing a
first-of-its-kind table-rebuild migration (no such rebuild exists anywhere in this
codebase's migration history, so doing one now would be a new, riskier pattern for
a codebase that has stayed migration-simple for 42 phases).

Concretely: the sealed set already contains `requires_trusted_web`/`requires_tool`
(a human/Admin-Assistant marking "this case needs a Phase 20 capability to
resolve" — meaningful before Phase 20 existed). Phase 20 adds a **new, additive**
table in migration 042, `knowledge_gap_capability_resolutions` (its own fresh,
Phase-20-owned CHECK constraint: `resolution_kind IN ('resolved_by_trusted_web',
'resolved_by_tool')`), linking a case to the specific `trusted_web_search_events`
or `deterministic_tool_execution_events` row that resolved it. The case's overall
`status`/`stage` still transitions through the existing, unconstrained
`update_case_status_stage()` path (`status="resolved"`, `stage="resolution"` —
both already-legal Phase 19 values, no new enum needed there). This keeps migration
041 byte-for-byte untouched while giving Phase 20 a fully evidence-backed,
queryable resolution link, satisfying Step 26 without a risky first-of-its-kind
migration technique.

## 4. Web search architecture

```
Public chat request (trusted_web recommended by Phase 17, unchanged)
  -> resolve_route_availability() -- NEW: checks provider health + policy validity
     -> executable  -> TrustedWebAnswerService.answer(...)
     -> unavailable -> insufficient (unchanged honest-fallback shape)

TrustedWebAnswerService.answer():
  Query Classification (map domain/subdomain/intent/freshness -> web category)
  -> Search Policy (config/trusted_web_policy.json, checksum-validated)
  -> Provider Selection (single configured WebSearchProvider)
  -> Search Execution (provider.search(), rate-limited, cached)
  -> Result Normalization (already provider-neutral from the adapter)
  -> Candidate Filtering (domain policy: blocked -> dropped, unknown -> deprioritized)
  -> Source Trust Evaluation (trust_level per domain/pattern match)
  -> Optional Safe Fetch (SafeWebFetcher, only for fetch_allowed categories,
     bounded by maximum_fetches)
  -> Content Extraction (title/headings/dates/main text)
  -> Injection Filtering (web_injection_guard; contaminated content excluded)
  -> Freshness Evaluation (WebFreshnessEvaluationService)
  -> Evidence Selection (WebEvidenceSelectionService, bounded excerpts)
  -> Conflict Detection (WebSourceVerificationService cross-checks selected evidence)
  -> Grounded Answer Generation (template-based paraphrase + citations;
     NOT the LLM inventing facts outside supplied evidence -- Phase 18's existing
     model-call path is reused for phrasing only, never for the factual content)
  -> Citation Validation (public_citation_adapter.web_citations_for_evidence)
```

`TrustedWebAnswerService` contains zero training/RAG-ingestion logic; it is a pure
request-scoped orchestrator, mirroring `PublicChatRoutingService`'s own shape.

## 5. Deterministic tool architecture

```
tool recommended by Phase 17
  -> resolve_route_availability() -- NEW: checks tool registry for a matching,
     public-enabled tool
     -> executable  -> select_tool_for_request() (Step 22 mapping)
                        -> DeterministicToolExecutionService.execute()
     -> unsupported -> insufficient (tool_unsupported reason code)

DeterministicToolExecutionService.execute():
  Tool Selection (deterministic mapping, never user-supplied tool name)
  -> Input Schema Validation (per-tool JSON-schema-like validator)
  -> Safety/Permission Check (public_safe_deterministic tier only)
  -> Deterministic Execution (AST-allowlist calculator / unit table / date math --
     never eval, never subprocess, never model inference)
  -> Output Schema Validation
  -> Result Normalization
  -> Audit (deterministic_tool_execution_events, append-only)
```

Tool selection within `ask_calculation` (Phase 17 has no finer intent than this)
is Phase 20's own bounded, deterministic sub-classification
(`select_tool_for_request()`): unit-keyword + `to`/`in` pattern → `unit_conversion`;
ISO-date + day/week-delta pattern → `date_time_arithmetic`; else → `calculator`.
`ask_code` (also in Phase 17's `_TOOL_INTENTS`) has no matching Phase 20 tool and
honestly resolves to `insufficient`/`tool_unsupported` — Phase 17's classification
is not modified to accommodate this; Phase 20 simply doesn't claim a capability it
doesn't have.

## 6. MCP-ready contract

`core_model/tool_gateway/mcp_contract.py` defines `ToolDescriptor`,
`ToolInvocationRequest`, `ToolInvocationResult`, `ToolPermissionContext`,
`ToolExecutionError` as a stable internal shape every current and future tool
source (`built_in_deterministic` now; `internal_service`/`external_mcp` later)
must satisfy. `Settings.external_mcp_enabled: bool = Field(default=False, ...)` —
default false, and the registry raises `ToolExecutionError("mcp_disabled")` for
any `external_mcp`-sourced descriptor regardless of the flag in this phase (no
external MCP server config is even accepted through any API in Phase 20 — the
flag exists so Phase 21+ has a documented, auditable place to eventually flip it,
not because Phase 20 provides a working external path).

## 7. Provider trust policy

`config/trusted_web_policy.json` — checksum-versioned (`policy_version`,
`policy_checksum_sha256`, same `compute_manifest_checksum`-style algorithm),
fail-closed on corruption (raises, never silently falls back to an empty/permissive
policy). Sections: `allowed_domains`, `blocked_domains`, `official_source_patterns`,
`source_category_rules`, `fetch_allowed`, `snippet_only_allowed`,
`required_verification_level`, `freshness_thresholds`, `maximum_results`,
`maximum_fetches`, `timeouts`, `content_limits`, `provider_priority`. Reloadable
only via a new Admin Assistant proposal action (`propose_trusted_web_policy_issue`)
— never a raw file-upload endpoint.

## 8. Provider selection

One concrete, real adapter: `ConfigurableSearchApiProvider` (generic HTTP GET to a
policy-configured `base_url` + `api_key` header/param, parsing a
Brave/Bing-shaped JSON result list — a common, documented shape, not tied to one
paid vendor's SDK). **No API key is shipped or configured by default** —
`Settings.trusted_web_provider_api_key` defaults to `None`, so `health_check()`
returns unhealthy out of the box, and `trusted_web` honestly resolves to
`insufficient` in this development environment. This is the correct, intended,
"cost-controlled and fail-closed" default (Step 4), and the exact behavior Step 25
requires to be tested ("Web provider unavailable → honest insufficient response").
The full pipeline (search → fetch → extract → verify → cite) is exercised
end-to-end in tests via the same injectable-transport pattern `fetch_evidence`
already established — no real outbound network call is required to prove
correctness, mirroring how every existing external-fetch code path in this
repository is already tested.

## 9. Public routing integration

Only `core_model/public_chat/route_availability.py`'s `trusted_web`/`tool`
branches change. `core_model/public_chat/__init__.py`'s `EXECUTABLE_ROUTES`
gains `trusted_web`/`tool` (moved out of `UNAVAILABLE_ROUTES`, which becomes
empty but is kept as a constant for backward-compatible imports/tests).
`SOURCE_TYPES` gains `web`/`tool`. `PublicChatResponse` gains
`tool_name`/`tool_version`/`tool_status` (all optional, default `None`).
No other route's behavior changes.

## 10. Knowledge-gap linkage

After a `trusted_web`/`tool` route succeeds, `PublicChatRoutingService` calls a
new, best-effort, fail-safe `_link_capability_gap_resolution()` (same
try/except-wrapped, never-breaks-the-response pattern as Phase 19's
`_capture_gap()`), which looks for an open case matching
`(domain, intent, canonical_question_similarity)` via the existing
`KnowledgeGapClusteringService` candidate-matching logic (reused, not
reimplemented) and, only on a confident match, records a
`knowledge_gap_capability_resolutions` row. No automatic RAG/training handoff;
no automatic cluster-wide resolution.

## 11. Admin controls

New Admin APIs under `/api/admin/trusted-web` and `/api/admin/deterministic-tools`
(Step 29's endpoint list). Admin Dashboard gains two pages. Admin Assistant gains
8 read-only tools + 5 proposal actions. All Data Overview integration is additive
metrics/actions on the existing page.

## 12. Phase 21 handoff

Phase 20 ships `web_capability_gap`/`tool_capability_gap` resolution evidence and
real (if currently zero-volume) demand summaries. Phase 21 (per the project's own
`phase16_phase17_to_phase26_implementation_map.md`) is explicitly NOT started by
this phase — this document records architecture only, no Phase 21 code exists.
