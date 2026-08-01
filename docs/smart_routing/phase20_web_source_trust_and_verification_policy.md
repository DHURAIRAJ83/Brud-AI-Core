# Phase 20 — Web Source Trust, SSRF Protection & Verification Policy

## 1. Policy file

`config/trusted_web_policy.json` — checksum-versioned exactly like
`config/production_regression_manifest.json`
(`compute_policy_checksum()`/`load_policy()` in
`backend/services/trusted_web_policy_service.py` mirror
`compute_manifest_checksum()`/`load_manifest()` line for line: SHA-256
over sorted-key compact JSON minus the checksum field itself). A
missing file, invalid JSON, failed schema validation, or checksum
mismatch **raises** — never falls back to an empty or permissive
policy. Reloadable only through the governed
`propose_trusted_web_policy_issue`/`propose_source_block`/
`propose_source_allowlist_review` Admin Assistant actions (record-only
in this phase — see §7), never a raw upload endpoint.

Current state: `policy_version="v1"`, 16 allowed domains (government
portals, official language/framework docs, W3C/ISO/MDN as
authoritative, Wikipedia as `reputable_secondary`), `maximum_results=5`,
`maximum_fetches=3`, `fetch_allowed=["official","authoritative",
"reputable_secondary"]`.

## 2. Trust levels

`official` / `authoritative` / `reputable_secondary` / `community` /
`unknown` / `blocked` — domain popularity is never conflated with
trust (per-domain assignment in `allowed_domains`, plus
`official_source_patterns` wildcard suffixes like `*.gov.in`).

## 3. Verification ladder

`search_result_only` → `domain_verified` → `page_fetched` →
`content_verified` → `cross_source_verified` →
`official_source_verified` (`core_model/web_search/verification.py`).
Monotonic — each level requires every check the level below it
required, plus exactly one more. The public answer always reports the
level actually achieved.

**Real bug found and fixed**: `cross_source_confirmed` was hardcoded
`False` at candidate-gathering time, making `cross_source_verified`/
`official_source_verified` structurally unreachable regardless of
evidence quality. Fixed with
`_apply_cross_source_confirmation()` in
`trusted_web_answer_service.py`: after all candidates are gathered, if
2+ genuinely distinct domains each independently reached
`content_verified`, each is bumped (never a domain confirming itself
via a second page on the same site). Given only one provider (a
single-domain Wikipedia adapter) ships by default, true cross-source
confirmation needs a second configured provider — a real, disclosed
consequence, not a bug. Because of this, `current_general_information`'s
required level was lowered from `cross_source_verified` to
`content_verified` (matching the other content-based categories) so
the shipped single-provider default can genuinely answer its own
catch-all category rather than being permanently unable to.

## 4. Freshness

`evaluate_freshness()` compares the most recent of `published_at`/
`updated_at` against per-category `fresh_days`/`possibly_stale_days`
thresholds. Results: `fresh` / `possibly_stale` / `stale` / `undated`
(never promoted to fresh) / a future-dated document is conservatively
`possibly_stale`, never rewarded as `fresh`. `overall_freshness()`
combines multiple selected items — `conflicting` only ever comes from
disagreement across sources, never a single source in isolation.

## 5. Conflict detection

`core_model/web_search/conflict_detection.py` — a bounded, honest
number/version-token heuristic between at least two independently
**trusted** (`official`/`authoritative`) sources; a single source can
never be "conflicting". Statuses: `no_conflict` / `minor_difference` /
`material_conflict` / `date_version_conflict` / `unresolved_conflict`.
A conflict is never silently resolved by picking one source — both/all
are disclosed and cited; a preference is only stated when one source
is clearly newer (`date_version_conflict`/single-fresh-source
`material_conflict`) and the reason is always recorded.

## 6. SSRF / URL safety

`backend/services/safe_web_fetcher.py::validate_fetch_url()`/
`fetch_page()`, reusing the proven Phase 11
`dataset_verification_transport.py` DNS/IP-safety primitives
(`is_domain_allowed`, `_reject_unsafe_ip`) rather than a third
reimplementation. Blocks, each with 41 dedicated pytest cases
(`tests/backend/test_safe_web_fetcher_security.py`), all passing:

- Non-HTTP/HTTPS schemes: `file://`, `ftp://`, `gopher://`, `data:`,
  `javascript:`, `ws://`.
- Credential-bearing URLs (`user:pass@host`).
- `localhost`, `*.local` hostnames.
- Domain not on the single scoped `allowed_domain` (exact-or-subdomain
  match only — `evilexample.com` never matches `example.com`).
- Every resolved IP checked: loopback (127.0.0.0/8, `::1`), private
  (10/8, 172.16/12, 192.168/16, IPv6 unique-local), link-local
  (169.254/16, IPv6 link-local), multicast, unspecified (`0.0.0.0`).
- Cloud metadata addresses (`169.254.169.254`, `fd00:ec2::254`) and
  the `metadata`/`metadata.google.internal` hostnames — checked even
  when reached only via a same-domain redirect (proven with a
  dedicated test: a redirect that stays within the allowlisted domain
  string but whose DNS now resolves to the metadata IP is still
  blocked).
- Redirects: at most 1 followed, re-validated identically to the
  original URL (domain scope **and** IP safety), a redirect off the
  original single scoped domain is rejected even if the target domain
  is separately allowlisted elsewhere in policy, a redirect loop is
  bounded (never infinite).
- Content type: allowlist only (`text/plain`, `text/markdown`,
  `text/html`, `application/json`, `application/pdf`) — an executable
  or archive content-type is rejected.
- Response size: truncated at `max_response_bytes`, never unbounded
  retained (though the underlying transport still downloads the full
  body before truncation — a documented, inherited Phase 11/12
  limitation, not new here).
- Best-effort IDN-confusable detection (mixed Latin/non-Latin script
  in one label) — flagged as a warning, never silently trusted.
- No cookies persisted, no authentication, GET only, no JavaScript
  execution, no form submission (structural: `fetch_page()`'s
  signature has no cookie/credential/proxy parameter at all — proven
  by a dedicated introspection test, not just a docstring claim).

**Known, inherited limitation** (shared with the Phase 11/12 code this
reuses, documented not silently assumed away): DNS-resolution safety
check and the actual TCP connect are two separate steps, so a DNS-
rebinding attacker with very low TTL could in principle swap the
resolved address between them. No module in this codebase closes this
gap; Phase 20 does not attempt a first-of-its-kind fix here.

## 7. Content extraction & injection defence

Safe HTML/PDF/text/JSON extraction (`safe_web_fetcher.py`, PDF via the
already-hard-dependency `PyMuPDF`). Extracts title, headings, published/
updated date, canonical URL, language; scripts/styles/nav/forms are
never executed, only stripped as text (proven: a page containing
`<script>alert(...)</script>` never has `alert(` survive into
`main_text`).

`core_model/public_chat/web_injection_guard.py` — the third extension
of the same base injection-filter lineage (RAG → conversation → Web),
reusing `detect_injection_signals`/`classify_injection_status`
unchanged and adding two Web-specific categories: hidden-instruction
markers surviving HTML extraction, and citation-manipulation
directives ("cite only this page", "never cite other sources"). A
match excludes the source from the evidence set (reason recorded in
`trusted_web_fetch_events.injection_status`) — never rejects the
public user's own request.

## 8. Evidence selection & citations

`WebEvidenceSelectionService` — term-overlap relevance scoring,
`support_type` in `directly_supports`/`partially_supports`/
`background_context` (never `contradicts` here; the orchestrator
downgrades a specific item to `contradicts` only after
`detect_conflict()` identifies it, keeping "is this relevant" and "do
sources disagree" separately testable). Excerpts are bounded
(`max_excerpt_chars=600`) and, as of this phase, privacy-scanned
(`_privacy_safe_excerpt()` reuses `detect_pii`/`redact_pii`/
`detect_secrets` from the corpus modules, block-then-redact order
matching `KnowledgeGapPrivacyService`) — applied once, before the
value reaches **both** the public reply text (which quotes it
verbatim) and the append-only `excerpt_redacted` DB column, so a page
containing incidental PII is never quoted back to the public user
either. **Real bug found and fixed**: the column was misleadingly
named `excerpt_redacted` but nothing actually redacted it until this
change.

Citations reuse the canonical Phase 18 path
(`backend/services/public_citation_adapter.py`) — `PublicCitation`'s
`source_type` widened to include `"web"`, a new sibling function
producing the exact same public dict shape from Web evidence (no
second citation system). Never exposes provider API keys, search-
provider internal IDs, private cache paths, raw fetch files, or
internal scoring vectors.
