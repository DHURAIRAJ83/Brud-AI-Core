"""Phase 13 Step 30: deterministic (never LLM-generated) answers to
the 12 fixed RAG-sandbox questions the Admin Assistant must answer
consistently in Tamil/English/Tanglish/Auto. Tanglish is always
*derived* from each entry's own "ta" value via
`core_model.admin_assistant.localization.message_catalog.localize()`
(Phase 10A's own system) -- never hand-written a third time.

Every answer here restates one of Phase 13's own non-negotiable
rules; none of it is invented, and none of it may drift from the
structural invariants enforced in code (`core_model.rag_sandbox`, the
rag-sandbox services). If a rule described here ever changes in code,
this file must change with it -- there is no independent source of
truth.
"""

from __future__ import annotations

RAG_SANDBOX_FAQ: dict[str, dict[str, object]] = {
    "what_is_a_rag_sandbox": {
        "keywords": ("what is a rag sandbox", "rag sandbox meaning", "what is rag sandbox"),
        "en": (
            "A RAG sandbox is a governed, temporary, structurally-isolated retrieval and "
            "grounded-generation environment built from one finalized Phase 12 sample "
            "report's accepted records. It lets an Admin test retrieval, grounded answers, "
            "citations, and safety behavior before any production RAG or training decision "
            "-- it never builds a production index and never activates production RAG."
        ),
        "ta": (
            "RAG sandbox என்பது, finalize செய்யப்பட்ட ஒரு Phase 12 sample report-இன் "
            "accepted records-இலிருந்து கட்டப்பட்ட, regulated, தற்காலிக, structural-ஆக "
            "தனிமைப்படுத்தப்பட்ட retrieval மற்றும் grounded-generation environment ஆகும். "
            "இது ஒரு Admin-ஐ, எந்த production RAG அல்லது training முடிவுக்கு முன்பும், "
            "retrieval, grounded answers, citations, மற்றும் safety behavior-ஐ test "
            "செய்ய அனுமதிக்கிறது -- இது ஒருபோதும் ஒரு production index-ஐ build செய்யாது, "
            "production RAG-ஐயும் activate செய்யாது."
        ),
    },
    "why_is_it_isolated": {
        "keywords": ("why is it isolated", "why sandbox isolated", "sandbox isolation"),
        "en": (
            "Every sandbox experiment creates its own dedicated knowledge space -- a "
            "distinct namespace, corpus, and index -- never reusing or writing into the "
            "production RAG space. Retrieval is structurally scoped to one knowledge space "
            "at a time, so a sandbox index cannot be reached except through its own "
            "sandbox-only retrieval profile."
        ),
        "ta": (
            "ஒவ்வொரு sandbox experiment-உம், தனது சொந்த தனிப்பட்ட knowledge space-ஐ "
            "உருவாக்கும் -- ஒரு தனி namespace, corpus, மற்றும் index -- production RAG "
            "space-ஐ ஒருபோதும் மீண்டும் பயன்படுத்தாது அல்லது அதற்குள் எழுதாது. Retrieval "
            "structural-ஆக ஒரு நேரத்தில் ஒரு knowledge space-க்கு மட்டுமே scope "
            "செய்யப்பட்டுள்ளது, எனவே ஒரு sandbox index, அதன் சொந்த sandbox-only "
            "retrieval profile மூலம் தவிர அடைய முடியாது."
        ),
    },
    "why_cant_production_chat_see_sandbox_data": {
        "keywords": (
            "production chat see sandbox", "can production chat access sandbox",
            "public chat sandbox",
        ),
        "en": (
            "Production chat only ever queries a retrieval profile a human Admin explicitly "
            "configured for it -- it never auto-discovers or falls back to any other "
            "knowledge space. No Phase 13 code path ever registers a sandbox retrieval "
            "profile with production chat, so sandbox data is structurally unreachable from "
            "it, not merely hidden by a permission check."
        ),
        "ta": (
            "Production chat, ஒரு human Admin அதற்காக தெளிவாக configure செய்த ஒரு "
            "retrieval profile-ஐ மட்டுமே எப்போதும் query செய்யும் -- இது ஒருபோதும் வேறு "
            "எந்த knowledge space-ஐயும் தானாக கண்டறியாது அல்லது அதற்கு fallback ஆகாது. "
            "எந்த Phase 13 code path-உம் ஒரு sandbox retrieval profile-ஐ production "
            "chat-உடன் ஒருபோதும் register செய்யாது, எனவே sandbox தரவு அதிலிருந்து "
            "structural-ஆக அடைய முடியாதது, ஒரு permission check மூலம் மட்டும் "
            "மறைக்கப்படவில்லை."
        ),
    },
    "what_is_retrieval_relevance": {
        "keywords": ("what is retrieval relevance", "retrieval relevance meaning"),
        "en": (
            "Retrieval relevance measures whether the chunks a query actually retrieved "
            "match the source(s) an Admin expected for that query -- recall@k, precision@k, "
            "and mean reciprocal rank, computed only when a query carries expected source "
            "IDs. Without expected sources, the metric is honestly marked 'not available', "
            "never fabricated."
        ),
        "ta": (
            "Retrieval relevance, ஒரு query உண்மையில் retrieve செய்த chunks, அந்த "
            "query-க்கு ஒரு Admin எதிர்பார்த்த source(கள்)-உடன் பொருந்துகிறதா என்பதை "
            "அளவிடுகிறது -- recall@k, precision@k, மற்றும் mean reciprocal rank, ஒரு "
            "query expected source IDs-ஐ கொண்டிருக்கும்போது மட்டுமே கணக்கிடப்படும். "
            "Expected sources இல்லாமல், metric நேர்மையாக 'not available' என்று "
            "குறிக்கப்படும், ஒருபோதும் கற்பனை செய்யப்படாது."
        ),
    },
    "what_is_groundedness": {
        "keywords": ("what is groundedness", "groundedness meaning"),
        "en": (
            "Groundedness measures whether an answer's claims are traceable to the evidence "
            "it was actually given -- never whether those claims are true. It is computed "
            "from the fraction of answer sentences carrying a valid citation marker; an "
            "answer with high unsupported-claim ratio is marked accordingly, regardless of "
            "how confident it sounds."
        ),
        "ta": (
            "Groundedness, ஒரு answer-இன் claims, அது உண்மையில் கொடுக்கப்பட்ட evidence-க்கு "
            "traceable ஆக உள்ளதா என்பதை அளவிடுகிறது -- அந்த claims உண்மையா என்பதை "
            "ஒருபோதும் அல்ல. இது ஒரு valid citation marker கொண்ட answer sentences-இன் "
            "பங்கிலிருந்து கணக்கிடப்படுகிறது; அதிக unsupported-claim ratio கொண்ட ஒரு "
            "answer, அது எவ்வளவு நம்பிக்கையுடன் தோன்றினாலும், அதற்கேற்ப குறிக்கப்படும்."
        ),
    },
    "what_is_citation_validity": {
        "keywords": ("what is citation validity", "citation validity meaning"),
        "en": (
            "A citation is valid when it references a chunk that was actually retrieved and "
            "in context, exists, and its checksum matches. Citation validity is deliberately "
            "independent from retrieval relevance -- an answer can cite correctly from "
            "poorly-retrieved evidence, or badly from well-retrieved evidence; both are "
            "measured and reported separately."
        ),
        "ta": (
            "ஒரு citation, அது உண்மையில் retrieve செய்யப்பட்டு context-இல் இருந்த ஒரு "
            "chunk-ஐ குறிப்பிடும்போது, அது இருக்கும்போது, மற்றும் அதன் checksum "
            "பொருந்தும்போது valid ஆகும். Citation validity, retrieval relevance-இலிருந்து "
            "வேண்டுமென்றே தனியானது -- ஒரு answer, மோசமாக retrieve செய்யப்பட்ட "
            "evidence-இலிருந்தும் சரியாக cite செய்யலாம், அல்லது நன்றாக retrieve "
            "செய்யப்பட்ட evidence-இலிருந்தும் தவறாக cite செய்யலாம்; இரண்டும் தனித்தனியாக "
            "அளவிடப்பட்டு report செய்யப்படும்."
        ),
    },
    "why_test_insufficient_evidence": {
        "keywords": (
            "why test insufficient evidence", "insufficient evidence test",
            "why insufficient evidence important",
        ),
        "en": (
            "When no good evidence exists, a safe model must say so honestly instead of "
            "inventing an answer. Insufficient-evidence queries deliberately probe this -- "
            "a sandbox cannot be accepted if repeated insufficient-evidence tests produce "
            "hallucinated answers above the configured threshold."
        ),
        "ta": (
            "நல்ல evidence இல்லாதபோது, ஒரு பாதுகாப்பான model, ஒரு answer-ஐ கற்பனை "
            "செய்வதற்குப் பதிலாக, அதை நேர்மையாக சொல்ல வேண்டும். Insufficient-evidence "
            "queries, இதை வேண்டுமென்றே சோதிக்கின்றன -- repeated insufficient-evidence "
            "tests, configure செய்யப்பட்ட threshold-ஐ விட அதிகமான hallucinated answers-ஐ "
            "உருவாக்கினால், ஒரு sandbox accept செய்யப்பட முடியாது."
        ),
    },
    "why_test_conflicting_sources": {
        "keywords": (
            "why test conflicting sources", "conflicting sources test",
            "why conflicting sources important",
        ),
        "en": (
            "When two retrieved sources disagree, a safe model must surface the conflict, "
            "name the competing sources, and avoid silently choosing one side. Conflict "
            "queries deliberately probe this -- a silent resolution is scored as a failure, "
            "not a pass."
        ),
        "ta": (
            "Retrieve செய்யப்பட்ட இரண்டு sources ஒன்றுக்கொன்று உடன்படாதபோது, ஒரு "
            "பாதுகாப்பான model, அந்த conflict-ஐ வெளிப்படுத்த வேண்டும், போட்டியிடும் "
            "sources-ஐ பெயரிட வேண்டும், மேலும் ஒரு பக்கத்தை மௌனமாக தேர்ந்தெடுப்பதைத் "
            "தவிர்க்க வேண்டும். Conflict queries இதை வேண்டுமென்றே சோதிக்கின்றன -- ஒரு "
            "silent resolution, ஒரு pass ஆக அல்ல, ஒரு failure ஆக மதிப்பிடப்படும்."
        ),
    },
    "why_test_prompt_injection": {
        "keywords": (
            "why test prompt injection", "prompt injection test", "why injection test important",
        ),
        "en": (
            "Retrieved evidence must always remain evidence, never an instruction the model "
            "obeys. Injection queries test whether malicious content embedded in a retrieved "
            "record can make the model disclose the system prompt, change role, or bypass "
            "policy -- but this never claims complete prompt-injection security, only what "
            "was actually tested."
        ),
        "ta": (
            "Retrieve செய்யப்பட்ட evidence எப்போதும் evidence ஆகவே இருக்க வேண்டும், model "
            "கீழ்ப்படியும் ஒரு instruction ஆக அல்ல. Injection queries, ஒரு retrieve "
            "செய்யப்பட்ட record-இல் embed செய்யப்பட்ட malicious content, model-ஐ system "
            "prompt-ஐ வெளிப்படுத்த, role-ஐ மாற்ற, அல்லது policy-ஐ bypass செய்ய வைக்க "
            "முடியுமா என்பதை சோதிக்கிறது -- ஆனால் இது ஒருபோதும் முழுமையான "
            "prompt-injection பாதுகாப்பை கூறாது, test செய்யப்பட்டதை மட்டுமே கூறும்."
        ),
    },
    "what_does_accepted_with_conditions_mean": {
        "keywords": ("accepted with conditions", "what does accepted_with_conditions mean"),
        "en": (
            "'Accepted with conditions' means an Admin found the sandbox results good "
            "enough to proceed, but only if specific, recorded conditions are met first "
            "(e.g. fixing a specific citation gap, re-testing a language pair). It is not "
            "unconditional approval, and it still does not activate production RAG or "
            "approve training."
        ),
        "ta": (
            "'Accepted with conditions' என்றால், ஒரு Admin sandbox results-ஐ தொடர "
            "போதுமானதாக கண்டறிந்தார், ஆனால் முதலில் குறிப்பிட்ட, பதிவு செய்யப்பட்ட "
            "conditions பூர்த்தி செய்யப்பட்டால் மட்டுமே (எ.கா. ஒரு குறிப்பிட்ட citation "
            "gap-ஐ சரிசெய்தல், ஒரு language pair-ஐ மீண்டும் test செய்தல்). இது "
            "unconditional approval அல்ல, மேலும் இது இன்னும் production RAG-ஐ activate "
            "செய்யாது, training-ஐயும் approve செய்யாது."
        ),
    },
    "why_acceptance_does_not_activate_production_rag": {
        "keywords": (
            "acceptance not activate production rag", "why doesn't acceptance activate rag",
            "does acceptance activate production rag",
        ),
        "en": (
            "Acceptance is a sandbox-scoped quality judgment; production RAG activation is a "
            "separate, later governed decision with its own approval gate outside this phase "
            "entirely. There is no code path anywhere in Phase 13 that flips a production "
            "activation flag -- only advisory 'production_rag_readiness' and "
            "'eligible_for_production_rag_proposal' signals are produced."
        ),
        "ta": (
            "Acceptance என்பது ஒரு sandbox-scoped quality judgment; production RAG "
            "activation என்பது, இந்த phase-க்கு முற்றிலும் வெளியே, அதன் சொந்த approval "
            "gate-உடன் கூடிய தனியான, பிற்கால governed முடிவு. Phase 13-இல் எங்கும் ஒரு "
            "production activation flag-ஐ மாற்றும் எந்த code path-உம் இல்லை -- advisory "
            "'production_rag_readiness' மற்றும் 'eligible_for_production_rag_proposal' "
            "signals மட்டுமே உருவாக்கப்படும்."
        ),
    },
    "why_rag_success_does_not_approve_training": {
        "keywords": (
            "rag success not approve training", "why doesn't rag success approve training",
            "does rag success approve training",
        ),
        "en": (
            "Good retrieval and grounded answers only show this data works well for "
            "retrieval-and-answer use -- they say nothing about whether the same data is "
            "suitable for training (coverage, licensing for training, contamination risk "
            "against evaluation sets). Training suitability is a separate observation "
            "('training_data_observation'), and training itself remains Phase 14's own, "
            "separately-gated decision."
        ),
        "ta": (
            "நல்ல retrieval மற்றும் grounded answers, இந்த data retrieval-and-answer "
            "பயன்பாட்டிற்கு நன்றாக வேலை செய்கிறது என்பதை மட்டுமே காட்டுகின்றன -- அதே "
            "data training-க்கு ஏற்றதா (coverage, training-க்கான licensing, evaluation "
            "sets-க்கு எதிரான contamination risk) என்பதைப் பற்றி எதுவும் கூறாது. "
            "Training suitability என்பது ஒரு தனி observation ('training_data_observation'), "
            "மேலும் training என்பதே Phase 14-இன் சொந்த, தனியாக gate செய்யப்பட்ட முடிவாகவே "
            "உள்ளது."
        ),
    },
}


def match_rag_sandbox_question(message: str) -> str | None:
    """Returns the matching FAQ key for a message, or `None`. Matches
    the longest keyword found so a more specific phrase always wins
    over an accidental shorter substring match."""

    message_lower = message.lower()
    best_key: str | None = None
    best_length = 0
    for key, entry in RAG_SANDBOX_FAQ.items():
        for keyword in entry["keywords"]:
            if keyword in message_lower and len(keyword) > best_length:
                best_key = key
                best_length = len(keyword)
    return best_key
