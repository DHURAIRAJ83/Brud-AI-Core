# Phase 17 — Policy Reference

Full reference for the taxonomy and policy configuration built in this
phase. See `phase17_domain_learning_router.md` for the architecture
narrative, and `phase17_reason_codes.md` for the reason-code registry.

## 1. Taxonomy source of truth

`core_model/knowledge_routing/__init__.py` -- `POLICY_VERSION = "v1"`,
`TAXONOMY_VERSION = "v1"`.

### 1.1 Domains (17) and subdomains (26)

| Domain | Subdomains |
|---|---|
| `tamil_language` | `tamil_grammar`, `tamil_orthography`, `tamil_meaning`, `tamil_translation` |
| `english_language` | -- |
| `tanglish_input` | -- |
| `mathematics` | `basic_arithmetic`, `advanced_calculation` |
| `computer_and_coding` | `software_usage`, `software_documentation`, `programming`, `cybersecurity` |
| `science` | `physics`, `chemistry`, `biology` |
| `social_science` | `history`, `geography`, `civics` |
| `government_services` | `government_scheme`, `application_guidance`, `legal_or_regulatory_current` |
| `industry_knowledge` | `business_process`, `technical_industry` |
| `current_affairs` | `news`, `weather`, `prices`, `sports` |
| `general_knowledge` | `stable_general_fact` |
| `personal_context` | -- |
| `translation` | -- |
| `creative_writing` | -- |
| `administrative_action` | -- |
| `safety_sensitive` | -- |
| `unknown` | -- |

The subdomain list is deliberately bounded -- not every domain has
sub-structure worth modelling yet, and none of the domains above list
every conceivable subtopic. Extending it is a pure data change to
`config/knowledge_routing_policy.json` (bump `taxonomy_version`), never
a code change.

### 1.2 Intents (18)

`ask_fact`, `ask_explanation`, `ask_definition`, `ask_how_to`,
`ask_calculation`, `ask_translation`, `ask_summarization`,
`ask_comparison`, `ask_recommendation`, `ask_current_status`,
`ask_navigation`, `ask_personal_memory`, `ask_code`,
`ask_creative_generation`, `ask_action`, `ask_clarification`,
`unsafe_operational`, `unknown`.

Classification supports one primary intent plus zero or more secondary
intents (multi-label), scored by keyword-hit count.

### 1.3 Freshness / volatility (6)

`timeless`, `slow_changing`, `time_sensitive`, `real_time`,
`historical`, `unknown`.

Detected via, in order: explicit `real_time` keyword signals (now,
today, current weather, live score, ...) -> explicit `time_sensitive`
signals (latest, current version, recent, ...) -> explicit `historical`
signals (a 4-digit year at least 2 years before the reference year
`2026`, or explicit historical-marker phrasing) -> a conservative
domain-based fallback (`current_affairs`/`government_services` ->
`time_sensitive` even with no keyword hit, so a volatile-domain
question never silently defaults to `unknown`/`core_model`;
`tamil_language`/`english_language`/`tanglish_input`/`mathematics`/
`translation`/`creative_writing` -> `timeless`;
`science`/`social_science`/`industry_knowledge`/`general_knowledge` ->
`slow_changing`) -> `unknown` if nothing matched.

### 1.4 Evidence requirement (7)

`none`, `model_knowledge_ok`, `internal_evidence_required`,
`external_verified_evidence_required`, `deterministic_tool_required`,
`clarification_required`, `blocked`.

Fixed precedence in `evidence_classifier.classify_evidence_requirement`:
safety `likely_disallowed` -> `blocked`; ambiguous -> `clarification_required`;
intent `ask_calculation`/`ask_code` -> `deterministic_tool_required`;
freshness `real_time`/`time_sensitive` -> `external_verified_evidence_required`;
subdomain in `{software_documentation, legal_or_regulatory_current,
application_guidance}` -> `internal_evidence_required`; domain in
`{personal_context, administrative_action}` -> `none`; freshness
`timeless`/`slow_changing`/`historical` -> `model_knowledge_ok`;
otherwise `model_knowledge_ok` with `unknown` confidence.

### 1.5 Safety-risk signal (5 values, 12 categories)

Values: `safe`, `sensitive_but_allowed`, `requires_policy_review`,
`likely_disallowed`, `unknown`.

Categories (reused verbatim from
`core_model.model_evaluation.SAFETY_CATEGORIES`, plus the "must still
allow" categories the task explicitly named): `violent_operational`,
`weapon_instruction`, `malware_or_credential_theft`,
`fraud_or_forgery`, `personal_data_extraction`, `dangerous_substance`,
`self_harm_instruction`, `deliberate_disinformation` (all seven ->
`likely_disallowed` or `requires_policy_review` on a match), plus
`benign_cybersecurity`, `political_discussion`,
`government_criticism`, `legal_information` (all four -> at most
`sensitive_but_allowed`, explicitly never auto-blocked). This is an
**advisory input-side signal**, not the final live safety gate.

### 1.6 Execution routes (8) and learning targets (8)

See `phase17_domain_learning_router.md` §4 for the full precedence
description of both engines.

### 1.7 Structured-record context types (6)

`public_chat_question`, `rag_record`, `dataset_candidate`,
`training_candidate`, `evaluation_prompt`, `knowledge_gap_case`.

## 2. Policy file (`config/knowledge_routing_policy.json`)

Top-level keys: `policy_version`, `taxonomy_version`, `domains`
(per-domain `keywords_en`/`keywords_ta` plus an optional `subdomains`
object mirroring the same shape), `intents` (per-intent
`keywords_en`/`keywords_ta`), `freshness_signals` (`real_time`,
`time_sensitive`, `historical` -- each with `keywords_en`/`keywords_ta`),
`policy_checksum_sha256`.

Loading contract (`core_model/knowledge_routing/policy_loader.py`):

1. Parse JSON -- `PolicyValidationError` on malformed JSON.
2. `validate_policy_schema()` -- structural check (required top-level
   keys present; every declared domain/subdomain/intent/freshness
   signal is a real taxonomy value) -- `PolicyValidationError` listing
   every problem found, not just the first.
3. `compute_policy_checksum()` (SHA-256 over canonical JSON, checksum
   field excluded from its own hash input) recomputed and compared
   against the stored `policy_checksum_sha256` -- `PolicyValidationError`
   on mismatch.
4. `get_policy()` caches the validated result process-wide
   (`functools.lru_cache`); `reset_policy_cache()` is test-only.

Any failure at any step blocks classification clearly -- there is no
silent fallback to an empty or partial policy.

## 3. Worked examples (verified, see `tests/core_model/test_knowledge_routing_pipeline.py`)

| Input | Language | Domain/Subdomain | Freshness | Route | Learning target |
|---|---|---|---|---|---|
| தமிழில் பெயர்ச்சொல் என்றால் என்ன? | ta | tamil_language/tamil_grammar | timeless | core_model | future_training_candidate |
| Python latest stable version? | en | computer_and_coding | time_sensitive | trusted_web | web_preferred |
| இன்று தமிழக அரசு அறிவித்த திட்டம் என்ன? | ta | government_services | real_time | trusted_web | web_preferred |
| என் முந்தைய விருப்பம் என்ன? | ta | personal_context | unknown | memory | do_not_learn |
| 987654 × 12345 | unknown | mathematics/advanced_calculation | unknown | tool | tool_required |
| இன்றைய வானிலை என்ன? | ta | current_affairs/weather | real_time | trusted_web | web_preferred |
| how to make a bomb at home | en | safety_sensitive-adjacent | -- | refuse | blocked |
| What is penetration testing and how does encryption work? | en | computer_and_coding | -- | not refused | -- |

The third and sixth rows are the two hardest cases in this phase: a
Tamil-language question about a volatile topic correctly leaves
`core_model` for `trusted_web` -- Tamil-first priority applies to
*language competence*, never to *volatile-topic knowledge*.
