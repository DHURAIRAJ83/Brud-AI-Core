"""Phase 19 Step 29: deterministic (never LLM-generated) answers to
the knowledge-gap-registry questions the Admin Assistant must answer
consistently in Tamil/English/Tanglish/Auto. Tanglish is always
*derived* from each entry's own "ta" value via
`core_model.admin_assistant.localization.message_catalog.localize()`
-- never hand-written a third time, mirroring
`rag_sandbox_help.py`/`sample_import_help.py` exactly.
"""

from __future__ import annotations

KNOWLEDGE_GAP_FAQ: dict[str, dict[str, object]] = {
    "what_is_a_knowledge_gap": {
        "keywords": ("what is a knowledge gap", "knowledge gap meaning", "what is knowledge gap"),
        "en": (
            "A knowledge gap is a *factual* case -- the model didn't know the answer, "
            "approved RAG had no or insufficient evidence, or the answer quality was "
            "confirmed poor by feedback. It is one of ten independent event types Phase 19 "
            "tracks; safety refusals, ambiguity, capability gaps, and operational failures "
            "are always recorded as their own separate type, never folded into this one."
        ),
        "ta": (
            "ஒரு knowledge gap என்பது ஒரு *உண்மை* தொடர்பான case -- model-க்கு பதில் "
            "தெரியவில்லை, approved RAG-க்கு evidence இல்லை அல்லது போதவில்லை, அல்லது "
            "feedback மூலம் answer quality மோசமானது என்று உறுதிசெய்யப்பட்டது. Phase 19 "
            "கண்காணிக்கும் பத்து தனித்தனி event types-இல் இதுவும் ஒன்று; safety refusals, "
            "ambiguity, capability gaps, மற்றும் operational failures எப்போதும் தங்கள் "
            "சொந்த தனி வகையாகவே பதிவு செய்யப்படும், இதனுள் ஒருபோதும் சேர்க்கப்படாது."
        ),
    },
    "why_is_a_safety_refusal_not_a_knowledge_gap": {
        "keywords": (
            "safety refusal not a knowledge gap",
            "why isn't a refusal a knowledge gap",
            "refusal knowledge gap",
        ),
        "en": (
            "A safety refusal is a deliberate policy decision, not missing knowledge -- the "
            "model may know the answer perfectly well and still correctly decline to give it. "
            "Recording it as a knowledge gap would be misleading (it might look like a future "
            "training/RAG candidate), so it is always recorded as its own `safety_event` type "
            "and never enters the knowledge-gap registry at all."
        ),
        "ta": (
            "ஒரு safety refusal என்பது ஒரு வேண்டுமென்றே எடுக்கப்பட்ட policy முடிவு, "
            "காணாமல் போன அறிவு அல்ல -- model-க்கு பதில் நன்றாகவே தெரிந்திருக்கலாம், ஆனாலும் "
            "அதைக் கொடுக்க சரியாக மறுக்கலாம். இதை knowledge gap ஆக பதிவு செய்வது தவறாக "
            "வழிநடத்தும் (எதிர்கால training/RAG candidate போல தோன்றலாம்), எனவே இது எப்போதும் "
            "தனது சொந்த `safety_event` வகையாகவே பதிவு செய்யப்படும், knowledge-gap "
            "registry-க்குள் ஒருபோதும் நுழையாது."
        ),
    },
    "what_is_a_capability_gap": {
        "keywords": ("what is a capability gap", "capability gap meaning"),
        "en": (
            "A capability gap (`web_capability_gap`/`tool_capability_gap`) means Phase 17 "
            "recommended Trusted Web search or a deterministic tool, but neither exists yet "
            "in this system -- it is demand for a *missing capability*, not a fact the model "
            "should have known. It never implies the model should guess or that training data "
            "is needed."
        ),
        "ta": (
            "ஒரு capability gap (`web_capability_gap`/`tool_capability_gap`) என்றால், Phase "
            "17 Trusted Web search அல்லது ஒரு deterministic tool-ஐ பரிந்துரைத்தது, ஆனால் "
            "இரண்டுமே இந்த system-இல் இன்னும் இல்லை -- இது ஒரு *இல்லாத capability*-க்கான "
            "தேவை, model தெரிந்திருக்க வேண்டிய ஒரு உண்மை அல்ல. இது model யூகிக்க வேண்டும் "
            "அல்லது training data தேவை என்று ஒருபோதும் குறிக்காது."
        ),
    },
    "why_are_web_and_tool_demand_stored_separately": {
        "keywords": (
            "web and tool demand stored separately",
            "why separate web tool demand",
            "web tool demand separate",
        ),
        "en": (
            "Web demand and Tool demand answer different future questions -- which Trusted-"
            "Web connector to build first (Phase 20) versus which deterministic tool to build "
            "first. Merging them into one count would hide which specific capability is "
            "actually most requested, and Phase 20 explicitly reads these two counts "
            "separately to prioritize its own connector/tool work."
        ),
        "ta": (
            "Web demand மற்றும் Tool demand வெவ்வேறு எதிர்கால கேள்விகளுக்கு பதிலளிக்கின்றன "
            "-- எந்த Trusted-Web connector-ஐ முதலில் build செய்வது (Phase 20) என்பதற்கும், "
            "எந்த deterministic tool-ஐ முதலில் build செய்வது என்பதற்கும். இவற்றை ஒரே "
            "எண்ணிக்கையாக இணைப்பது, உண்மையில் எது அதிகம் கோரப்படுகிறது என்பதை மறைக்கும், "
            "மேலும் Phase 20 தனது சொந்த connector/tool வேலையை முன்னுரிமைப்படுத்த இந்த "
            "இரண்டு எண்ணிக்கைகளையும் தனித்தனியாகப் படிக்கிறது."
        ),
    },
    "what_is_a_canonical_question": {
        "keywords": ("what is a canonical question", "canonical question meaning"),
        "en": (
            "A canonical question is a privacy-redacted, deterministically normalized (Unicode "
            "NFC, whitespace/punctuation cleanup, language-aware casing) version of a user's "
            "question -- never translated, never merged with another question just because "
            "they share keywords. It exists so a case is reviewable without the raw text ever "
            "being stored."
        ),
        "ta": (
            "ஒரு canonical question என்பது ஒரு பயனரின் கேள்வியின் privacy-redacted, "
            "deterministic-ஆக normalize செய்யப்பட்ட (Unicode NFC, whitespace/punctuation "
            "cleanup, language-aware casing) பதிப்பு -- ஒருபோதும் translate செய்யப்படாது, "
            "keywords பகிர்ந்துகொள்வதால் மட்டும் மற்றொரு கேள்வியுடன் இணைக்கப்படாது. raw "
            "text ஒருபோதும் சேமிக்கப்படாமல் ஒரு case review செய்யக்கூடியதாக இருக்க இது "
            "உள்ளது."
        ),
    },
    "why_is_raw_user_text_not_stored": {
        "keywords": (
            "why is raw user text not stored",
            "raw user text not stored",
            "raw text privacy",
        ),
        "en": (
            "Privacy by default -- only a SHA-256 input hash and a redacted/canonicalized "
            "form (with names, emails, phones, addresses, identifiers, and secrets replaced "
            "by placeholders) are stored. If a genuine credential/secret is detected, even the "
            "redacted form is withheld and only the hash is retained."
        ),
        "ta": (
            "Default-ஆக privacy -- ஒரு SHA-256 input hash மற்றும் ஒரு redacted/"
            "canonicalized வடிவம் மட்டுமே (பெயர்கள், emails, phones, addresses, "
            "identifiers, மற்றும் secrets ஆகியவை placeholders மூலம் மாற்றப்பட்டு) "
            "சேமிக்கப்படுகிறது. ஒரு உண்மையான credential/secret கண்டறியப்பட்டால், redacted "
            "வடிவம் கூட தடுக்கப்பட்டு hash மட்டுமே தக்கவைக்கப்படும்."
        ),
    },
    "how_are_duplicates_clustered": {
        "keywords": (
            "how are duplicates clustered",
            "how does clustering work",
            "duplicate clustering",
        ),
        "en": (
            "Conservatively, in three layers -- exact canonical match and normalized match "
            "auto-merge; a weaker Jaccard word-shingle near-duplicate match always requires "
            "explicit Admin review before merging. Candidates are only ever compared within "
            "the same domain/intent/freshness bucket, which is what keeps a current-version "
            "question and a stable-definition question separate."
        ),
        "ta": (
            "Conservative-ஆக, மூன்று layers-இல் -- exact canonical match மற்றும் "
            "normalized match தானாக merge ஆகும்; பலவீனமான Jaccard word-shingle "
            "near-duplicate match எப்போதும் merge செய்வதற்கு முன் தெளிவான Admin review-ஐ "
            "கோரும். Candidates எப்போதும் ஒரே domain/intent/freshness bucket-க்குள் "
            "மட்டுமே ஒப்பிடப்படும், இதுவே ஒரு current-version கேள்வியையும் ஒரு "
            "stable-definition கேள்வியையும் தனியாக வைத்திருக்கிறது."
        ),
    },
    "how_is_priority_calculated": {
        "keywords": (
            "how is priority calculated",
            "priority calculation",
            "how does priority work",
        ),
        "en": (
            "A deterministic weighted sum of frequency, recency, feedback severity, route-"
            "failure severity, and (for genuine language-capability reason codes only) a "
            "Tamil-first boost -- minus penalties for duplicate uncertainty, privacy risk, and "
            "low reproducibility. Every point is attached to a `priority_reason_codes` entry, "
            "so the score is always explainable, never a black box."
        ),
        "ta": (
            "frequency, recency, feedback severity, route-failure severity ஆகியவற்றின் "
            "deterministic weighted sum, மேலும் (உண்மையான language-capability reason "
            "codes-க்கு மட்டும்) ஒரு Tamil-first boost -- duplicate uncertainty, privacy "
            "risk, மற்றும் low reproducibility-க்கான penalties கழிக்கப்பட்டு. ஒவ்வொரு "
            "point-உம் ஒரு `priority_reason_codes` entry-உடன் இணைக்கப்பட்டுள்ளது, எனவே "
            "score எப்போதும் விளக்கக்கூடியதாக இருக்கும், ஒரு black box அல்ல."
        ),
    },
    "why_does_a_resolved_gap_not_enter_training_automatically": {
        "keywords": (
            "resolved gap not enter training",
            "why doesn't resolved gap enter training",
            "resolved gap training automatic",
        ),
        "en": (
            "'Resolved' only means an Admin recorded a decision about what should happen next "
            "-- it never means the case was approved for RAG or training. RAG approval, "
            "training-dataset creation, and training itself all remain separate, human-"
            "controlled workflows with their own governance; this registry only produces "
            "advisory eligibility flags, never an approval."
        ),
        "ta": (
            "'Resolved' என்றால், அடுத்து என்ன நடக்க வேண்டும் என்பது பற்றி ஒரு Admin ஒரு "
            "முடிவைப் பதிவு செய்தார் என்பது மட்டுமே அர்த்தம் -- இது case RAG அல்லது "
            "training-க்கு approve செய்யப்பட்டது என்று ஒருபோதும் அர்த்தமல்ல. RAG approval, "
            "training-dataset உருவாக்கம், மற்றும் training ஆகியவை அனைத்தும் தங்கள் சொந்த "
            "governance-உடன் தனியான, human-controlled workflows-ஆகவே உள்ளன; இந்த registry "
            "advisory eligibility flags-ஐ மட்டுமே உருவாக்குகிறது, ஒரு approval-ஐ அல்ல."
        ),
    },
    "what_is_rag_handoff_eligibility": {
        "keywords": ("what is rag handoff eligibility", "rag handoff eligibility meaning"),
        "en": (
            "An advisory flag (`eligible_for_rag_research`/`eligible_for_rag_trial_proposal`) "
            "marking a case as worth a source-rights review and potential RAG Sandbox trial -- "
            "only for static/timeless knowledge gaps, never volatile web facts (which would "
            "become stale in a permanent index). It never creates a RAG source or index by "
            "itself; Phase 24 will implement the actual bridge to the existing RAG Sandbox."
        ),
        "ta": (
            "ஒரு advisory flag (`eligible_for_rag_research`/`eligible_for_rag_trial_proposal`) "
            "ஒரு case ஒரு source-rights review மற்றும் சாத்தியமான RAG Sandbox trial-க்கு "
            "தகுதியானது என்று குறிக்கிறது -- static/timeless knowledge gaps-க்கு மட்டும், "
            "volatile web facts-க்கு ஒருபோதும் அல்ல (அவை ஒரு நிரந்தர index-இல் "
            "காலாவதியாகிவிடும்). இது தானாக ஒரு RAG source அல்லது index-ஐ உருவாக்காது; "
            "Phase 24 existing RAG Sandbox-க்கான உண்மையான bridge-ஐ செயல்படுத்தும்."
        ),
    },
    "what_is_training_assessment_eligibility": {
        "keywords": (
            "what is training assessment eligibility",
            "training assessment eligibility meaning",
            "training-assessment eligibility",
        ),
        "en": (
            "An advisory flag (`eligible_for_training_assessment`) for repeatable Tamil "
            "grammar/Tanglish-comprehension/instruction-following/reasoning capability "
            "failures only -- never current news, prices, weather, software versions, private "
            "facts, unsafe requests, or one-off/temporary failures. It never creates a "
            "training dataset or starts a training run by itself."
        ),
        "ta": (
            "மீண்டும் நிகழக்கூடிய Tamil grammar/Tanglish-comprehension/instruction-following/"
            "reasoning capability failures-க்கு மட்டும் ஒரு advisory flag "
            "(`eligible_for_training_assessment`) -- நடப்பு செய்திகள், விலைகள், வானிலை, "
            "software versions, தனிப்பட்ட உண்மைகள், unsafe requests, அல்லது ஒரு-முறை/"
            "தற்காலிக failures-க்கு ஒருபோதும் அல்ல. இது தானாக ஒரு training dataset-ஐ "
            "உருவாக்காது அல்லது ஒரு training run-ஐ தொடங்காது."
        ),
    },
}


def match_knowledge_gap_question(message: str) -> str | None:
    """Returns the matching FAQ key for a message, or `None`. Matches
    the longest keyword found so a more specific phrase always wins
    over an accidental shorter substring match."""

    message_lower = message.lower()
    best_key: str | None = None
    best_length = 0
    for key, entry in KNOWLEDGE_GAP_FAQ.items():
        for keyword in entry["keywords"]:
            if keyword in message_lower and len(keyword) > best_length:
                best_key = key
                best_length = len(keyword)
    return best_key


__all__ = ["KNOWLEDGE_GAP_FAQ", "match_knowledge_gap_question"]
