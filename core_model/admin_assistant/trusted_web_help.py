"""Phase 20 Step 33: deterministic (never LLM-generated) answers to
the Trusted Web / deterministic-tool questions the Admin Assistant
must answer consistently in Tamil/English/Tanglish/Auto. Tanglish is
always *derived* from each entry's own "ta" value via
`core_model.admin_assistant.localization.message_catalog.localize()`
-- never hand-written a third time, mirroring
`knowledge_gap_help.py`/`rag_sandbox_help.py` exactly.
"""

from __future__ import annotations

TRUSTED_WEB_FAQ: dict[str, dict[str, object]] = {
    "what_is_trusted_web_search": {
        "keywords": (
            "what is trusted web search",
            "what is trusted web",
            "trusted web search meaning",
        ),
        "en": (
            "Trusted Web Search is Phase 20's bounded, source-verified live Web pipeline for "
            "public chat: search -> source-trust policy -> optional safe fetch -> injection "
            "filtering -> freshness evaluation -> evidence selection -> conflict detection -> "
            "grounded answer -> citation. A raw search result is never treated as trusted "
            "evidence by itself -- it must clear domain trust evaluation and, for most "
            "categories, an actual page fetch before it can be used."
        ),
        "ta": (
            "Trusted Web Search என்பது public chat-க்கான Phase 20-இன் bounded, "
            "source-verified நேரடி Web pipeline: search -> source-trust policy -> optional "
            "safe fetch -> injection filtering -> freshness evaluation -> evidence selection -> "
            "conflict detection -> grounded answer -> citation. ஒரு raw search result தானாகவே "
            "trusted evidence ஆக ஒருபோதும் கருதப்படாது -- பெரும்பாலான categories-க்கு அது "
            "domain trust evaluation-ஐயும் ஒரு உண்மையான page fetch-ஐயும் கடக்க வேண்டும்."
        ),
    },
    "how_is_a_source_verified": {
        "keywords": (
            "how is a source verified",
            "source verification",
            "how do you verify a source",
        ),
        "en": (
            "Verification is a monotonic ladder: search_result_only -> domain_verified -> "
            "page_fetched -> content_verified -> cross_source_verified -> "
            "official_source_verified. Each level requires every check the level below it "
            "required, plus one more (domain trust, then a successful fetch, then relevant/"
            "safe/dated content, then a second independent domain confirming the same claim, "
            "then an official-domain trust level). The public answer always reports the level "
            "actually achieved, never a higher one."
        ),
        "ta": (
            "Verification ஒரு monotonic ladder: search_result_only -> domain_verified -> "
            "page_fetched -> content_verified -> cross_source_verified -> "
            "official_source_verified. ஒவ்வொரு level-உம் அதற்கு கீழே உள்ள level தேவைப்படுத்தும் "
            "எல்லா checks-ஐயும், மேலும் ஒன்றை தேவைப்படுத்தும். Public answer எப்போதும் "
            "உண்மையில் அடையப்பட்ட level-ஐயே தெரிவிக்கும், ஒருபோதும் அதிகமானதை அல்ல."
        ),
    },
    "why_are_some_search_results_rejected": {
        "keywords": (
            "why are some search results rejected",
            "why was a result rejected",
            "search result rejected",
        ),
        "en": (
            "A result is dropped or downgraded for a specific, honest reason: the domain is "
            "on the blocked list, the domain's trust level is `unknown` and the category "
            "requires a fetch, the fetch itself was blocked (SSRF/private-IP/scheme/content-"
            "type check), the fetched content matched an injection pattern, or the content "
            "couldn't reach the category's required verification level. None of this is ever "
            "silently hidden -- the reason is recorded in the fetch/evidence event trail."
        ),
        "ta": (
            "ஒரு result ஒரு குறிப்பிட்ட, நேர்மையான காரணத்திற்காக drop அல்லது downgrade "
            "செய்யப்படும்: domain blocked list-இல் உள்ளது, domain-இன் trust level `unknown` "
            "மற்றும் category-க்கு fetch தேவை, fetch-ஏ block செய்யப்பட்டது (SSRF/private-IP/"
            "scheme/content-type check), fetch செய்யப்பட்ட content ஒரு injection pattern-உடன் "
            "பொருந்தியது, அல்லது content category-இன் தேவையான verification level-ஐ அடையவில்லை. "
            "இது ஒருபோதும் மறைக்கப்படாது -- காரணம் fetch/evidence event trail-இல் பதிவாகும்."
        ),
    },
    "what_is_freshness": {
        "keywords": ("what is freshness", "freshness meaning", "what does freshness mean"),
        "en": (
            "Freshness is how current a source's own published/updated date is, relative to "
            "the query's category (e.g. software documentation gets a tighter threshold than "
            "a stable general fact). Results: fresh, possibly_stale, stale, undated, or "
            "conflicting (when selected sources disagree). Content with no date is never "
            "promoted to 'fresh' just because a query needs current information."
        ),
        "ta": (
            "Freshness என்பது ஒரு source-இன் own published/updated date query-இன் category-உடன் "
            "ஒப்பிடும்போது எவ்வளவு தற்போதையது என்பது (எ.கா. software documentation-க்கு ஒரு "
            "stable general fact-ஐ விட கடுமையான threshold). முடிவுகள்: fresh, possibly_stale, "
            "stale, undated, அல்லது conflicting (தேர்ந்தெடுக்கப்பட்ட sources வேறுபட்டால்). "
            "தேதி இல்லாத content ஒரு query-க்கு தற்போதைய தகவல் தேவை என்பதற்காக மட்டும் "
            "'fresh' ஆக ஒருபோதும் உயர்த்தப்படாது."
        ),
    },
    "what_happens_when_sources_conflict": {
        "keywords": (
            "what happens when sources conflict",
            "sources conflict",
            "conflicting sources",
        ),
        "en": (
            "A conflict between two or more trusted sources is never silently resolved by "
            "picking one -- it is disclosed, both/all sources are cited, and confidence is "
            "lowered. Only when one source is clearly newer or legally controlling is a "
            "preference stated, and the reason for preferring it is always documented in the "
            "answer's limitations."
        ),
        "ta": (
            "இரண்டு அல்லது அதற்கு மேற்பட்ட trusted sources இடையேயான ஒரு conflict ஒருபோதும் "
            "ஒன்றை தேர்ந்தெடுத்து அமைதியாக தீர்க்கப்படாது -- அது வெளிப்படுத்தப்படும், அனைத்து "
            "sources-உம் cite செய்யப்படும், confidence குறைக்கப்படும். ஒரு source தெளிவாக "
            "புதியதாக அல்லது legally controlling ஆக இருந்தால் மட்டுமே ஒரு preference "
            "கூறப்படும், அதற்கான காரணம் எப்போதும் answer-இன் limitations-இல் documented."
        ),
    },
    "why_no_current_facts_from_model_memory": {
        "keywords": (
            "why does brud ai not answer current facts from model memory",
            "why not use model memory for current facts",
            "stale model knowledge",
        ),
        "en": (
            "A core invariant: search failure never grants permission to use stale model "
            "knowledge. If Trusted Web is recommended but the provider is unavailable, quota "
            "is exhausted, or the evidence found doesn't meet the required verification level, "
            "the honest response is `insufficient` with the specific reason -- never a silent "
            "fallback to whatever the base model happens to remember."
        ),
        "ta": (
            "ஒரு முக்கிய invariant: search failure ஒருபோதும் stale model knowledge-ஐ "
            "பயன்படுத்த அனுமதி தராது. Trusted Web recommend செய்யப்பட்டு provider "
            "unavailable ஆக இருந்தால், quota தீர்ந்துவிட்டால், அல்லது கிடைத்த evidence "
            "தேவையான verification level-ஐ அடையவில்லை என்றால், நேர்மையான பதில் குறிப்பிட்ட "
            "காரணத்துடன் `insufficient` -- base model எதை நினைவில் வைத்திருந்தாலும் அதற்கு "
            "அமைதியான fallback ஒருபோதும் இல்லை."
        ),
    },
    "what_is_a_deterministic_tool": {
        "keywords": ("what is a deterministic tool", "deterministic tool meaning"),
        "en": (
            "A deterministic tool is a schema-validated, sandboxed function -- calculator, "
            "unit conversion, or date/time arithmetic -- that always produces the exact same "
            "output for the same input, computed by real arithmetic code, never by the "
            "language model guessing. Every execution is validated, normalized, and audited."
        ),
        "ta": (
            "ஒரு deterministic tool என்பது ஒரு schema-validated, sandboxed function -- "
            "calculator, unit conversion, அல்லது date/time arithmetic -- இது ஒரே input-க்கு "
            "எப்போதும் ஒரே output-ஐ தரும், உண்மையான arithmetic code மூலம் கணக்கிடப்படும், "
            "language model யூகிப்பதன் மூலம் ஒருபோதும் இல்லை. ஒவ்வொரு execution-உம் "
            "validate, normalize, audit செய்யப்படும்."
        ),
    },
    "why_is_calculator_output_authoritative": {
        "keywords": (
            "why is calculator output different from model reasoning",
            "why is calculator output authoritative",
            "calculator vs model",
        ),
        "en": (
            "The calculator uses an AST-allowlist parser over exact decimal arithmetic -- "
            "never `eval`, never the language model. The model may format a short sentence "
            "around the result, but it can never alter the number itself; the structured "
            "result from the tool is always authoritative, unlike a model's own arithmetic "
            "reasoning, which is not guaranteed to be exact for large numbers."
        ),
        "ta": (
            "Calculator ஒரு AST-allowlist parser-ஐ exact decimal arithmetic-இன் மேல் "
            "பயன்படுத்துகிறது -- `eval` இல்லை, language model இல்லை. Model result-ஐ சுற்றி "
            "ஒரு சிறிய வாக்கியத்தை format செய்யலாம், ஆனால் எண்ணையே ஒருபோதும் மாற்ற முடியாது; "
            "tool-இன் structured result எப்போதும் authoritative, model-இன் own arithmetic "
            "reasoning பெரிய எண்களுக்கு exact ஆக இருக்கும் என்பதற்கு உத்தரவாதம் இல்லை."
        ),
    },
    "what_is_mcp": {
        "keywords": ("what is mcp", "mcp meaning"),
        "en": (
            "MCP (Model Context Protocol) is a standard shape for describing and invoking "
            "tools. Phase 20 defines an internal MCP-compatible contract (ToolDescriptor, "
            "ToolInvocationRequest/Result, ToolPermissionContext) so future internal services "
            "and approved external MCP servers can plug into the same tool gateway -- but no "
            "external MCP server is configured or executable in this phase."
        ),
        "ta": (
            "MCP (Model Context Protocol) என்பது tools-ஐ describe செய்யவும் invoke "
            "செய்யவும் ஒரு standard shape. Phase 20 ஒரு internal MCP-compatible contract-ஐ "
            "(ToolDescriptor, ToolInvocationRequest/Result, ToolPermissionContext) "
            "வரையறுக்கிறது, இதனால் எதிர்கால internal services மற்றும் approved external MCP "
            "servers அதே tool gateway-க்குள் இணையலாம் -- ஆனால் இந்த phase-இல் எந்த external "
            "MCP server-உம் configure அல்லது executable இல்லை."
        ),
    },
    "why_is_external_mcp_disabled": {
        "keywords": ("why is external mcp disabled", "external mcp disabled"),
        "en": (
            "`external_mcp_enabled` defaults to `false`, and any `external_mcp`-sourced tool "
            "descriptor is refused unconditionally regardless of that flag -- no external MCP "
            "server configuration is even accepted through any Phase 20 API. This is a "
            "deliberate, conservative default: full tool-permission governance for external "
            "MCP is explicitly deferred to a later phase, not built here."
        ),
        "ta": (
            "`external_mcp_enabled` இயல்பாகவே `false`, எந்த `external_mcp`-sourced tool "
            "descriptor-உம் அந்த flag-ஐப் பொருட்படுத்தாமல் unconditionally மறுக்கப்படும் -- "
            "எந்த Phase 20 API வழியாகவும் எந்த external MCP server configuration-உம் "
            "ஏற்கப்படாது. இது ஒரு வேண்டுமென்றே எடுக்கப்பட்ட, conservative default -- external "
            "MCP-க்கான full tool-permission governance வேண்டுமென்றே ஒரு பிற்கால phase-க்கு "
            "ஒத்திவைக்கப்பட்டுள்ளது, இங்கே கட்டப்படவில்லை."
        ),
    },
    "why_only_three_public_tools": {
        "keywords": (
            "why are only three public tools enabled",
            "only three tools",
            "three public tools",
        ),
        "en": (
            "Calculator, unit conversion, and date/time arithmetic are the Step 2 minimum "
            "scope -- each is fully deterministic, sandboxed, and needs no external "
            "credential or account action. File-write, shell, browser-automation, email, "
            "calendar, and payment tools are explicitly out of scope for this phase; adding "
            "them would need the full tool-permission governance Phase 22 is reserved for."
        ),
        "ta": (
            "Calculator, unit conversion, date/time arithmetic ஆகியவை Step 2-இன் minimum "
            "scope -- ஒவ்வொன்றும் முழுமையாக deterministic, sandboxed, எந்த external "
            "credential அல்லது account action-உம் தேவையில்லை. File-write, shell, "
            "browser-automation, email, calendar, payment tools இந்த phase-க்கு வெளிப்படையாக "
            "out of scope; இவற்றைச் சேர்க்க Phase 22-க்காக ஒதுக்கப்பட்ட full "
            "tool-permission governance தேவைப்படும்."
        ),
    },
}


def match_trusted_web_question(message: str) -> str | None:
    """Returns the matching FAQ key for a message, or `None`. Matches
    the longest keyword found so a more specific phrase always wins
    over an accidental shorter substring match."""

    message_lower = message.lower()
    best_key: str | None = None
    best_length = 0
    for key, entry in TRUSTED_WEB_FAQ.items():
        for keyword in entry["keywords"]:
            if keyword in message_lower and len(keyword) > best_length:
                best_key = key
                best_length = len(keyword)
    return best_key


__all__ = ["TRUSTED_WEB_FAQ", "match_trusted_web_question"]
