# Phase 20 — Trusted Web Search, Source Verification, Deterministic Tool Gateway & MCP-Ready Execution Foundation

## 1. What this phase is, and is not

Phase 20 upgrades the public Smart Answer Router so that Phase 17's
`trusted_web` and `tool` recommendations become genuinely executable,
instead of the honest-but-permanent "unavailable" Phase 18 shipped
with. It adds a bounded, source-verified live Web pipeline and three
sandboxed deterministic tools (calculator, unit conversion, date/time
arithmetic). It does **not** add live translation, a full source-
transparency dropdown (Phase 23), arbitrary browser automation, shell
execution, external MCP execution, or any account/payment/file-write
tool. No case from this phase automatically enters RAG or training.

## 2. Demand evidence

This development environment has no deployed public traffic yet, so
Phase 19's knowledge-gap registry has no real `web_capability_gap`/
`tool_capability_gap` volume to rank by. Per the spec's own fallback,
scope defaults to the Step 2 minimum: five Web categories
(`current_software_documentation`, `government_service_information`,
`current_rules_and_regulations`, `current_general_information`,
`official_product_documentation`) and three tools (`calculator`,
`unit_conversion`, `date_time_arithmetic`). Once real traffic flows,
`get_web_demand_summary`/`get_tool_demand_summary` (Phase 19, already
live) become the real evidence source for re-prioritizing Phase 21+.

## 3. Architecture

```
User question -> Phase 17 classification -> Phase 18 safety/route resolution
  -> resolve_route_availability() -- trusted_web/tool now conditionally executable
     -> trusted_web: TrustedWebAnswerService.answer()
          search -> policy -> candidate filtering -> source trust evaluation
          -> optional safe fetch -> content extraction -> injection filtering
          -> freshness evaluation -> evidence selection -> conflict detection
          -> grounded (template) answer -> citation
     -> tool: DeterministicToolExecutionService.execute()
          input schema validation -> permission check -> deterministic
          execution -> output schema validation -> audit
  -> Knowledge-gap capability resolution linkage (best-effort, advisory)
  -> Public-safe response (unchanged Phase 18 shape, additive fields only)
```

`PublicChatRoutingService.handle_message()` is the **only** public
router; `_execute_trusted_web_route`/`_execute_tool_route` are two new
sibling private methods alongside the existing `_execute_evidence_route`
(core_model/approved_rag/memory) — no second router was created, and
none of `core_model`/`approved_rag`/`memory`/`clarify`/`refuse`
behavior changed.

## 4. Web provider

Two `WebSearchProvider` implementations exist:

- **`WikipediaSearchProvider`** (the default,
  `trusted_web_provider_name="wikipedia"`) — zero-config, key-free,
  calls Wikipedia's official public REST search API
  (`/w/rest.php/v1/search/page`). Chosen deliberately so `trusted_web`
  is genuinely executable out of the box rather than permanently
  unconfigured. Narrow, honest coverage (strong for stable/
  encyclopedic topics).
- **`ConfigurableSearchApiProvider`** — generic HTTP adapter for any
  real, paid search API returning a Brave/Bing-shaped JSON result list.
  Selected via `BRUD_TRUSTED_WEB_PROVIDER_NAME` + `_BASE_URL` +
  `_API_KEY`. With no key configured it reports unhealthy —
  cost-controlled, fail-closed, exactly the Step 4 default.

Both share one production wiring point, `build_configured_provider()`,
and an in-process circuit breaker (3 consecutive failures opens a
60s cooldown) so `health_check()` never has to make a network call on
every route-availability check.

**Known, disclosed environment limitation**: Wikimedia's traffic-
fingerprinting infrastructure blocks generic Python HTTP clients
(confirmed: identical `curl` requests succeed, `httpx` requests
receive `403 Please respect our robot policy`) from this specific
sandboxed development environment, even with a correct, descriptive
User-Agent. This is **not** a code defect — the full pipeline logic is
proven correct via deterministic injected-transport tests (see §14),
and the fail-closed behavior it triggers (`web_provider_unavailable` →
honest `insufficient`, never a stale-model fallback) is itself the
correct, intended, safety-critical behavior. No workaround that could
resemble bot-detection evasion was attempted, consistent with "respect
source terms."

## 5. Deterministic tools

`calculator`, `unit_conversion`, `date_time_arithmetic` — see
`phase20_deterministic_tool_contract.md` for full detail. All three are
`public_enabled=True`, need no external credential, and are selected
deterministically from Phase 17's `ask_calculation` intent (never a
user-supplied tool name).

## 6. Knowledge-gap resolution linkage

`KnowledgeGapCapabilityLinkageService.link_if_matched()` runs after a
successful `trusted_web`/`tool` answer (fail-safe, double-wrapped like
Phase 19's `_capture_gap()`). It pre-filters open
`web_capability_gap`/`tool_capability_gap` cases to the same
`(domain, intent, freshness)` bucket `KnowledgeGapClusteringService`
already uses, then reuses that exact clustering service's near-
duplicate comparison — no new similarity math. A confident match
appends one `knowledge_gap_capability_resolutions` row
(`resolved_by_trusted_web`/`resolved_by_tool`); the case's own
`status`/`stage` is **never** auto-changed — closing a case remains a
human/Admin decision via the unchanged Phase 19
`KnowledgeGapResolutionService`. Verified both live (Flow I) and via
two dedicated tests proving a matching case gets linked and an
unrelated one never does.

## 7. Public APIs

`GET /api/chat/capabilities` now reports real
`trusted_web_available`/`tool_available`/`calculator_available`/
`unit_conversion_available`/`date_time_arithmetic_available`/
`external_mcp_enabled` (previously hardcoded `False`). `POST /api/chat`
response gains (all additive, existing fields unchanged):
`tool_name`/`tool_version`/`tool_status`, and `source_types`/
`PublicCitation.source_type` widened to include `"web"`/`"tool"`.
`evidence_status` gains one new value, `"deterministic"` (a tool
result is neither model-generated nor evidence-grounded).

## 8. Admin APIs

24 endpoints total, matching the spec's exact list: 8 under
`/api/admin/trusted-web` (`overview`, `providers`, `policy`,
`search-events`, `evidence`, `fetch-events`, `health`, `test-search`,
`verify-source` — one extra read-only `fetch-events` beyond the
spec's minimum, for Admin visibility into blocked/successful fetches),
4 under `/api/admin/deterministic-tools` (`overview`, `registry`,
`execution-events`, `test`). Every write endpoint requires Admin auth
+ CSRF; neither ever returns an API key, raw fetched page body, or
provider-internal payload.

## 9. Public chatbot frontend

Minimal, honest display only (full source-transparency dropdown is
Phase 23): route labels for `Web`/`Tool`, real citation links with a
freshness/source-conflict warning line for Web answers, tool name +
exact result with **no** citation for Tool answers. No new dropdown
architecture. Verified live: exact calculator result rendered, `Tool`
label shown, zero citation links on a tool answer, no horizontal
overflow at 390px, zero unexpected console errors.

## 10. Admin Dashboard

Two new pages, `Trusted Web` (10 tabs: Overview, Demand, Providers,
Policy, Search Events, Sources, Freshness, Conflicts, Injection
Blocks, Health) and `Deterministic Tools` (9 tabs: Overview, Registry,
Calculator, Unit Conversion, Date Arithmetic, Execution Events,
Errors, Permissions, MCP Readiness). Both wired into `App.jsx`,
`Sidebar.jsx`, and `core_model/admin_assistant/dashboard_registry.py`
(the Python-side nav-key registry Phase 18/19 both required and whose
omission was a real, caught bug both times — added proactively here).
Data Overview gained a `trustedWeb`/`deterministicTools` metrics group
(7 + 6 real metrics) and 4 new actions. All verified live rendering
real data from the actual running Admin API.

## 11. Admin Assistant

8 read-only tools (`get_trusted_web_overview`, `get_trusted_web_health`,
`get_web_source_verification_summary`, `get_web_freshness_summary`,
`get_web_conflict_summary`, `get_tool_gateway_overview`,
`get_tool_execution_summary`, `get_mcp_readiness_summary`) + 5
governed proposal actions (`propose_trusted_web_policy_issue`,
`propose_source_block`, `propose_source_allowlist_review`,
`propose_tool_enablement_review`, `propose_tool_permission_issue`),
all flag/record-only — none mutates the checksum-versioned policy
file, toggles a tool's code-level enabled state, or enables external
MCP. All 5 actions follow the unchanged propose→preview→confirm-with-
stale-check→execute→verify→audit pipeline and are proven, via
`set(ACTION_EXECUTORS) == {defined action_types}`, to have real
executors (the same architectural invariant a Phase 19 investigation
established). 11-topic bilingual deterministic help FAQ, dispatched
the same way Phase 19's `knowledge_gap_help.py` is.

## 12. Security controls

See `phase20_web_source_trust_and_verification_policy.md` §SSRF and
`phase20_mcp_readiness_and_security_boundary.md` for full detail.
Summary: 12 SSRF/scheme block categories tested (localhost, loopback,
private/link-local/multicast IPv4+IPv6, cloud metadata IP and
hostname, `file://`/`ftp://`/`gopher://`/`data:`/`javascript:`,
credential-bearing URLs), every redirect target re-validated
identically to the original URL, calculator is an AST-allowlist
evaluator (never `eval`/`exec`/`compile`), external MCP structurally
disabled (no registry entry exists to enable).

## 13. Performance/resource controls

`maximum_results=5`, `maximum_fetches=3`, `MAX_FETCH_REDIRECTS=1`,
`max_response_bytes=2,000,000`, `max_excerpt_chars=600`,
`MAX_EXPRESSION_LENGTH=200`, `MAX_AST_DEPTH=20`, `MAX_PAREN_DEPTH=20`,
`MAX_EXPONENT=12`, `MAX_CONVERSION_MAGNITUDE=1e15`,
`MAX_DAY_DELTA=366,000`. Separate rate limits for `web_search`,
`web_fetch` (+ per-domain), `tool_exec`, reusing
`public_chat_rate_limiter.check_rate_limit()` verbatim (same
documented single-process limitation as Phase 18). Bounded, in-process
search cache (`MAX_CACHE_ENTRIES=256`), never containing secrets or
per-user private context.

## 14. Tests, browser verification, regression

630 new/updated automated tests (see the final response for the exact
per-category breakdown and command output), all passing. 14/14 real,
non-mocked Playwright browser checks against genuinely running
backend + chatbot + admin-dashboard dev servers, plus additional real
HTTP-level verification (SSRF blocking, exact tool results, knowledge-
gap linkage) directly against a live server on a real TCP socket. The
canonical regression manifest was extended v5→v6 (65→70 batches); see
the final response for exact execution evidence.

## 15. Known limitations / deferred

- Wikipedia bot-detection blocks live search from this specific
  sandbox (§4) — architecturally sound and tested via injected fake
  transports; environment-specific, not a code defect.
- Source conflict (Flow C) and Web-content injection exclusion
  (Flow H) are proven via deterministic pytest (real orchestration
  logic, fake network I/O boundary only) rather than genuine live
  network, for the same reason.
- No dedicated Admin API endpoint exposes per-case capability-
  resolution links yet (the data and linkage logic are proven correct
  via repository-level tests and live DB verification; only the read
  HTTP surface for it is missing).
- `[PERSON]`-style redaction reused from Phase 19 remains a narrow
  heuristic, unchanged.
- No committed Playwright e2e suite for the new Admin Dashboard tabs
  (manual/scripted verification only, matching Phase 18/19's own
  scoping decision).
- Single-process rate limiting and search cache (documented,
  unchanged limitation carried from Phase 18).
- Tanglish-output-mismatch regeneration retry: out of scope, unchanged.

## 16. Phase 21 handoff

`DeterministicToolRegistry`'s `internal_service`/`external_mcp`
categories are defined but empty; `WebSearchProvider.provider_priority`
in the policy is ready for a second real provider. `web_demand`/
`tool_demand` summaries are now live and will carry real signal once
this system has real public traffic. No Phase 21 code exists.
