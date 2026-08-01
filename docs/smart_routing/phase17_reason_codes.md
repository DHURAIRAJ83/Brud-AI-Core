# Phase 17 — Reason-Code Registry

The single source of truth is
`core_model/knowledge_routing/reason_codes.py::REASON_CODE_REGISTRY`
(126 codes), served live by `GET /api/admin/knowledge-routing/reason-codes`
and the Admin Assistant's `list_knowledge_routing_reason_codes` tool.
Every code any classifier layer emits is asserted, at classification
time, to exist in this registry (`pipeline.classify()` asserts this on
every call -- see `tests/core_model/test_knowledge_routing_taxonomy.py`).

## Two-tier construction (why a few concepts have two codes)

25 codes are hand-written, verbatim, to match the exact spelling the
task's own Step 21 example list required (e.g. `INTENT_CURRENT_STATUS`,
`EVIDENCE_INTERNAL_REQUIRED`). Every remaining taxonomy value gets a
second, mechanically-generated code (`f"{PREFIX}_{value.upper()}"`) so
the registry has full coverage even where the task gave no explicit
example. Where a mechanical code would have collided with a required
one under a different spelling (e.g. intent value `ask_current_status`
mechanically generates `INTENT_ASK_CURRENT_STATUS`, but the required
form is `INTENT_CURRENT_STATUS`), **both exist in the registry**, but
only the required form is ever actually emitted by a classifier --
`INTENT_REASON_CODE_BY_VALUE`, `DOMAIN_REASON_CODE_BY_VALUE`,
`FRESHNESS_REASON_CODE_BY_VALUE`, `EVIDENCE_REASON_CODE_BY_VALUE`,
`SAFETY_REASON_CODE_BY_VALUE`, `TARGET_REASON_CODE_BY_VALUE` are the
value-to-code lookup tables every classifier actually calls, and each
one resolves to the required spelling wherever one was specified. The
mechanical duplicate stays in the registry only so
`is_known_reason_code()` and the API/tool listing remain a complete,
self-documenting reference -- it is dead code from the classifiers'
perspective, never a code a caller will actually see in
`all_reason_codes`.

## Full registry (126 codes)

| Code | Description |
|---|---|
| AMBIGUOUS_CONFLICTING_INSTRUCTION | The request contains mutually conflicting instructions. |
| AMBIGUOUS_INCOMPLETE_ACTION | An action verb has no stated target. |
| AMBIGUOUS_MISSING_CONTEXT | The request depends on context that is not available. |
| AMBIGUOUS_MISSING_OBJECT | The request appears to be missing a clear object/target. |
| AMBIGUOUS_MISSING_SUBJECT | The request appears to be missing a clear subject. |
| AMBIGUOUS_UNCLEAR_PRONOUN | A pronoun has no resolvable antecedent. |
| AMBIGUOUS_UNKNOWN_ACRONYM | An unrecognized acronym was used without expansion. |
| DOMAIN_ADMINISTRATIVE_ACTION | Knowledge domain classified as 'administrative_action' |
| DOMAIN_ADVANCED_CALCULATION | Knowledge subdomain classified as 'advanced_calculation' |
| DOMAIN_APPLICATION_GUIDANCE | Knowledge subdomain classified as 'application_guidance' |
| DOMAIN_BASIC_ARITHMETIC | Knowledge subdomain classified as 'basic_arithmetic' |
| DOMAIN_BIOLOGY | Knowledge subdomain classified as 'biology' |
| DOMAIN_BUSINESS_PROCESS | Knowledge subdomain classified as 'business_process' |
| DOMAIN_CHEMISTRY | Knowledge subdomain classified as 'chemistry' |
| DOMAIN_CIVICS | Knowledge subdomain classified as 'civics' |
| DOMAIN_COMPUTER_AND_CODING | Knowledge domain classified as 'computer_and_coding' |
| DOMAIN_CREATIVE_WRITING | Knowledge domain classified as 'creative_writing' |
| DOMAIN_CURRENT_AFFAIRS | Knowledge domain classified as 'current_affairs' |
| DOMAIN_CYBERSECURITY | Knowledge subdomain classified as 'cybersecurity' |
| DOMAIN_ENGLISH_LANGUAGE | Knowledge domain classified as 'english_language' |
| DOMAIN_GENERAL_KNOWLEDGE | Knowledge domain classified as 'general_knowledge' |
| DOMAIN_GEOGRAPHY | Knowledge subdomain classified as 'geography' |
| DOMAIN_GOVERNMENT_SCHEME | Knowledge subdomain classified as 'government_scheme' |
| DOMAIN_GOVERNMENT_SERVICES | Knowledge domain classified as 'government_services' |
| DOMAIN_HISTORY | Knowledge subdomain classified as 'history' |
| DOMAIN_INDUSTRY_KNOWLEDGE | Knowledge domain classified as 'industry_knowledge' |
| DOMAIN_LEGAL_OR_REGULATORY_CURRENT | Knowledge subdomain classified as 'legal_or_regulatory_current' |
| DOMAIN_MATHEMATICS | Knowledge domain classified as 'mathematics' |
| DOMAIN_NEWS | Knowledge subdomain classified as 'news' |
| DOMAIN_PERSONAL_CONTEXT | Knowledge domain classified as 'personal_context' |
| DOMAIN_PHYSICS | Knowledge subdomain classified as 'physics' |
| DOMAIN_PRICES | Knowledge subdomain classified as 'prices' |
| DOMAIN_PROGRAMMING | Knowledge subdomain classified as 'programming' |
| DOMAIN_SAFETY_SENSITIVE | Knowledge domain classified as 'safety_sensitive' |
| DOMAIN_SCIENCE | Knowledge domain classified as 'science' |
| DOMAIN_SOCIAL_SCIENCE | Knowledge domain classified as 'social_science' |
| DOMAIN_SOFTWARE_DOCUMENTATION | Knowledge subdomain classified as 'software_documentation'. |
| DOMAIN_SOFTWARE_USAGE | Knowledge subdomain classified as 'software_usage' |
| DOMAIN_SPORTS | Knowledge subdomain classified as 'sports' |
| DOMAIN_STABLE_GENERAL_FACT | Knowledge subdomain classified as 'stable_general_fact' |
| DOMAIN_TAMIL_GRAMMAR | Knowledge subdomain classified as 'tamil_grammar'. |
| DOMAIN_TAMIL_LANGUAGE | Knowledge domain classified as 'tamil_language' |
| DOMAIN_TAMIL_MEANING | Knowledge subdomain classified as 'tamil_meaning' |
| DOMAIN_TAMIL_ORTHOGRAPHY | Knowledge subdomain classified as 'tamil_orthography' |
| DOMAIN_TAMIL_TRANSLATION | Knowledge subdomain classified as 'tamil_translation' |
| DOMAIN_TANGLISH_INPUT | Knowledge domain classified as 'tanglish_input' |
| DOMAIN_TECHNICAL_INDUSTRY | Knowledge subdomain classified as 'technical_industry' |
| DOMAIN_TRANSLATION | Knowledge domain classified as 'translation' |
| DOMAIN_UNKNOWN | Knowledge domain classified as 'unknown' |
| DOMAIN_WEATHER | Knowledge subdomain classified as 'weather' |
| EVIDENCE_BLOCKED | Evidence requirement classified as 'blocked' |
| EVIDENCE_CLARIFICATION_REQUIRED | Evidence requirement classified as 'clarification_required' |
| EVIDENCE_DETERMINISTIC_TOOL_REQUIRED | Evidence requirement classified as 'deterministic_tool_required' (mechanical duplicate; never emitted -- see `EVIDENCE_TOOL_REQUIRED`) |
| EVIDENCE_EXTERNAL_REQUIRED | Evidence requirement classified as 'external_verified_evidence_required'. |
| EVIDENCE_EXTERNAL_VERIFIED_EVIDENCE_REQUIRED | mechanical duplicate; never emitted -- see `EVIDENCE_EXTERNAL_REQUIRED` |
| EVIDENCE_INTERNAL_EVIDENCE_REQUIRED | mechanical duplicate; never emitted -- see `EVIDENCE_INTERNAL_REQUIRED` |
| EVIDENCE_INTERNAL_REQUIRED | Evidence requirement classified as 'internal_evidence_required'. |
| EVIDENCE_MODEL_KNOWLEDGE_OK | Evidence requirement classified as 'model_knowledge_ok' |
| EVIDENCE_NONE | Evidence requirement classified as 'none' |
| EVIDENCE_TOOL_REQUIRED | Evidence requirement classified as 'deterministic_tool_required'. |
| FRESHNESS_HISTORICAL | Freshness/volatility classified as 'historical' |
| FRESHNESS_REAL_TIME | Freshness classified as 'real_time'. |
| FRESHNESS_SLOW_CHANGING | Freshness/volatility classified as 'slow_changing' |
| FRESHNESS_TIMELESS | Freshness/volatility classified as 'timeless' |
| FRESHNESS_TIME_SENSITIVE | Freshness classified as 'time_sensitive'. |
| FRESHNESS_UNKNOWN | Freshness/volatility classified as 'unknown' |
| INTENT_ASK_ACTION | Primary intent classified as 'ask_action' |
| INTENT_ASK_CALCULATION | Primary intent classified as 'ask_calculation' |
| INTENT_ASK_CLARIFICATION | Primary intent classified as 'ask_clarification' |
| INTENT_ASK_CODE | Primary intent classified as 'ask_code' |
| INTENT_ASK_COMPARISON | Primary intent classified as 'ask_comparison' |
| INTENT_ASK_CREATIVE_GENERATION | Primary intent classified as 'ask_creative_generation' |
| INTENT_ASK_CURRENT_STATUS | mechanical duplicate; never emitted -- see `INTENT_CURRENT_STATUS` |
| INTENT_ASK_DEFINITION | Primary intent classified as 'ask_definition' |
| INTENT_ASK_EXPLANATION | Primary intent classified as 'ask_explanation' |
| INTENT_ASK_FACT | Primary intent classified as 'ask_fact' |
| INTENT_ASK_HOW_TO | Primary intent classified as 'ask_how_to' |
| INTENT_ASK_NAVIGATION | Primary intent classified as 'ask_navigation' |
| INTENT_ASK_PERSONAL_MEMORY | Primary intent classified as 'ask_personal_memory' |
| INTENT_ASK_RECOMMENDATION | Primary intent classified as 'ask_recommendation' |
| INTENT_ASK_SUMMARIZATION | Primary intent classified as 'ask_summarization' |
| INTENT_ASK_TRANSLATION | Primary intent classified as 'ask_translation' |
| INTENT_CURRENT_STATUS | Primary intent classified as 'ask_current_status'. |
| INTENT_UNKNOWN | Primary intent classified as 'unknown' |
| INTENT_UNSAFE_OPERATIONAL | Primary intent classified as 'unsafe_operational' |
| LANG_ENGLISH_DETECTED | Latin script present with no Tanglish lexicon hits. |
| LANG_MIXED_DETECTED | Both Tamil and Latin script present above the detection threshold. |
| LANG_TAMIL_DETECTED | Tamil script present above the detection threshold. |
| LANG_TANGLISH_DETECTED | Latin script present with Tanglish lexicon hits. |
| LANG_UNKNOWN | Neither Tamil nor Latin script detected above the threshold. |
| NOT_AMBIGUOUS_DETERMINISTIC_ROUTE | A deterministic route is available without clarification. |
| ROUTE_CLARIFY_AMBIGUOUS | Request is ambiguous; a route cannot be safely chosen yet. |
| ROUTE_CORE_STABLE_LANGUAGE | Timeless language/explanation/creative request answerable from the model's own knowledge. |
| ROUTE_INSUFFICIENT_NO_EVIDENCE_PATH | No viable evidence path exists for this request. |
| ROUTE_MEMORY_PERSONAL_CONTEXT | Request concerns the user's own prior context/preference. |
| ROUTE_RAG_APPROVED_INTERNAL | Request concerns an approved internal document/evidence set. |
| ROUTE_REFUSE_UNSAFE | Request matched a likely-disallowed safety category. |
| ROUTE_TOOL_DETERMINISTIC | Request is a deterministic calculation/conversion the model should not attempt via free-text reasoning. |
| ROUTE_WEB_CURRENT_INFORMATION | Request concerns real-time or time-sensitive information the model cannot know reliably. |
| SAFETY_BENIGN_CYBERSECURITY | Safety-relevant category matched: benign_cybersecurity. |
| SAFETY_DANGEROUS_SUBSTANCE | Safety-relevant category matched: dangerous_substance. |
| SAFETY_DELIBERATE_DISINFORMATION | Safety-relevant category matched: deliberate_disinformation. |
| SAFETY_FRAUD_OR_FORGERY | Safety-relevant category matched: fraud_or_forgery. |
| SAFETY_GOVERNMENT_CRITICISM | Safety-relevant category matched: government_criticism. |
| SAFETY_LEGAL_INFORMATION | Safety-relevant category matched: legal_information. |
| SAFETY_LIKELY_DISALLOWED | A high-risk safety category matched; recommend refusal. |
| SAFETY_MALWARE_OR_CREDENTIAL_THEFT | Safety-relevant category matched: malware_or_credential_theft. |
| SAFETY_PERSONAL_DATA_EXTRACTION | Safety-relevant category matched: personal_data_extraction. |
| SAFETY_POLITICAL_DISCUSSION | Safety-relevant category matched: political_discussion. |
| SAFETY_REQUIRES_POLICY_REVIEW | A category matched that a human safety policy should review. |
| SAFETY_SAFE | No safety-risk signal matched. |
| SAFETY_SELF_HARM_INSTRUCTION | Safety-relevant category matched: self_harm_instruction. |
| SAFETY_SENSITIVE_BUT_ALLOWED | A sensitive but explicitly-allowed category matched (e.g. benign cybersecurity education, political criticism, legal information). |
| SAFETY_UNKNOWN | No safety signal could be determined. |
| SAFETY_VIOLENT_OPERATIONAL | Safety-relevant category matched: violent_operational. |
| SAFETY_WEAPON_INSTRUCTION | Safety-relevant category matched: weapon_instruction. |
| TAMIL_FIRST_POLICY_VIOLATION | A Tamil-language request was routed to core_model purely because of its language, despite requiring current/external evidence. |
| TAMIL_FIRST_PRIORITY_APPLIED | Tamil-first policy correctly prioritized core-model language handling for a timeless Tamil-language request. |
| TARGET_BLOCKED_UNSAFE | Unsafe request; must never become any kind of learning signal. |
| TARGET_CORE_LANGUAGE_SKILL | Timeless linguistic/reasoning skill worth generalizing into the base model. |
| TARGET_DO_NOT_LEARN_PERSONAL | Personal/user-specific content must never become a training signal. |
| TARGET_EVALUATION_ONLY | Session-specific/operational; useful for evaluation only. |
| TARGET_FUTURE_TRAINING_CANDIDATE | Stable, generalizable content flagged for a future, separately-approved training cycle -- not an automatic training approval. |
| TARGET_RAG_STABLE_FACT | Stable fact suitable for an approved knowledge space, not model weights. |
| TARGET_TOOL_CALCULATION | Deterministic-tool result; no learning signal needed. |
| TARGET_WEB_VOLATILE_FACT | Volatile fact that should never be baked into model weights. |

## Testing

Every code's registration and every value-to-code lookup table's
resolution to a registered code is asserted in
`tests/core_model/test_knowledge_routing_taxonomy.py`. The 25 codes
named verbatim in the task's own Step 21 example list are individually
asserted present in `test_required_step21_example_codes_exist_verbatim`.
