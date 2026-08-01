"""Phase 18 Step 32 -- 10 bilingual, deterministic, template-based
Q&A entries explaining the public Smart Answer Router's own behavior
(why a route was chosen, why Web/Tool are unavailable, etc.).

This is a standalone, read-only reference surface -- exposed via
`GET /api/chat/help` -- and is deliberately NOT wired into the live
6-route classification pipeline (`core_model.public_chat.EXECUTABLE_ROUTES`).
Matching a user's free-form message to one of these entries and
answering with it instead of running real classification would risk
silently misrouting a genuine question that happens to share
keywords with a meta-question about the router itself, which the
Phase 18 invariants forbid (route recommendation must come from the
real classifier, never a keyword heuristic). No LLM call is involved,
matching the CPU-first, deterministic philosophy already used for
`clarification.py` and `fallback_text.py`.
"""

from __future__ import annotations

from typing import TypedDict


class HelpFaqEntry(TypedDict):
    id: str
    question_en: str
    question_ta: str
    answer_en: str
    answer_ta: str


HELP_FAQ_ENTRIES: tuple[HelpFaqEntry, ...] = (
    {
        "id": "route_selection",
        "question_en": "How does the chatbot decide how to answer my question?",
        "question_ta": "என் கேள்விக்கு பதிலளிக்க இந்த சாட்பாட் எப்படி முடிவெடுக்கிறது?",
        "answer_en": (
            "Every message is classified first, then answered using exactly one source: "
            "the language model, an approved document collection, your saved conversation "
            "memory, a clarifying question, a safety refusal, or an honest "
            "'not enough information' response. Sources are never combined or guessed."
        ),
        "answer_ta": (
            "ஒவ்வொரு செய்தியும் முதலில் வகைப்படுத்தப்படுகிறது, பின்னர் மொழி மாதிரி, "
            "அங்கீகரிக்கப்பட்ட ஆவணத் தொகுப்பு, உங்கள் சேமிக்கப்பட்ட உரையாடல் நினைவகம், "
            "தெளிவுபடுத்தும் கேள்வி, பாதுகாப்பு மறுப்பு, அல்லது 'போதிய தகவல் இல்லை' "
            "என்ற நேர்மையான பதில் ஆகியவற்றில் ஏதேனும் ஒன்று மட்டும் பயன்படுத்தப்படுகிறது."
        ),
    },
    {
        "id": "current_questions_not_from_model",
        "question_en": (
            "Why doesn't the chatbot answer questions about today's news or the "
            "latest version of something from memory?"
        ),
        "question_ta": (
            "இன்றைய செய்திகள் அல்லது ஏதேனும் ஒன்றின் சமீபத்திய பதிப்பு பற்றிய "
            "கேள்விகளுக்கு சாட்பாட் ஏன் நினைவிலிருந்து பதிலளிக்காது?"
        ),
        "answer_en": (
            "The language model only knows what it was trained on, which can go stale. "
            "For anything time-sensitive or current, guessing from old training data would "
            "risk giving you a wrong or outdated answer, so the chatbot avoids answering "
            "confidently from the model alone in those cases."
        ),
        "answer_ta": (
            "மொழி மாதிரிக்கு அது பயிற்சி பெற்ற தகவல் மட்டுமே தெரியும், அது காலப்போக்கில் "
            "பழையதாகிவிடலாம். காலத்திற்கு உட்பட்ட அல்லது சமீபத்திய தகவலுக்கு, பழைய தரவிலிருந்து "
            "யூகிப்பது தவறான அல்லது காலாவதியான பதிலைத் தரலாம், எனவே அத்தகைய சூழல்களில் "
            "மாதிரி மட்டும் கொண்டு உறுதியாக பதிலளிக்காது."
        ),
    },
    {
        "id": "why_web_unavailable",
        "question_en": "Why can't the chatbot search the web for me?",
        "question_ta": "எனக்காக சாட்பாட் ஏன் இணையத்தில் தேட முடியாது?",
        "answer_en": (
            "Live web search is not yet part of this system. When a question needs current "
            "web information, the chatbot honestly says so instead of answering with a "
            "possibly stale guess from the model."
        ),
        "answer_ta": (
            "நேரடி இணைய தேடல் இன்னும் இந்த அமைப்பின் பகுதியாக இல்லை. ஒரு கேள்விக்கு தற்போதைய "
            "இணைய தகவல் தேவைப்படும்போது, மாதிரியிலிருந்து பழையதாக இருக்கக்கூடிய ஒரு யூகத்துடன் "
            "பதிலளிப்பதற்குப் பதிலாக, சாட்பாட் அதை நேர்மையாகக் கூறுகிறது."
        ),
    },
    {
        "id": "why_tool_unavailable",
        "question_en": (
            "Why didn't the chatbot calculate that / tell me the current time or "
            "exchange rate?"
        ),
        "question_ta": (
            "அதை கணக்கிடவோ / தற்போதைய நேரம் அல்லது நாணய மாற்று விகிதத்தை கூறவோ "
            "சாட்பாட் ஏன் செய்யவில்லை?"
        ),
        "answer_en": (
            "This chatbot does not yet have calculator, clock, or live currency tools "
            "connected. Rather than approximate a large calculation or guess a live value "
            "from the model, it tells you the tool isn't available."
        ),
        "answer_ta": (
            "இந்த சாட்பாட்டில் இன்னும் கால்குலேட்டர், கடிகாரம், அல்லது நேரடி நாணய மாற்று "
            "கருவிகள் இணைக்கப்படவில்லை. ஒரு பெரிய கணக்கீட்டை தோராயமாக கணிப்பதற்கு அல்லது "
            "மாதிரியிலிருந்து ஒரு நேரடி மதிப்பை யூகிப்பதற்குப் பதிலாக, கருவி கிடைக்கவில்லை "
            "என்று அது உங்களுக்குத் தெரிவிக்கும்."
        ),
    },
    {
        "id": "what_is_approved_rag_answer",
        "question_en": "What does it mean when the answer is based on 'approved documents'?",
        "question_ta": "'அங்கீகரிக்கப்பட்ட ஆவணங்கள்' அடிப்படையில் பதில் வழங்கப்பட்டது என்றால் என்ன அர்த்தம்?",
        "answer_en": (
            "An approved-document answer is generated only from a curated, production-approved "
            "collection you're permitted to see -- never from sandbox, quarantined, or "
            "training-only data. Where possible, it comes with public-safe citations "
            "so you can see where the information came from."
        ),
        "answer_ta": (
            "அங்கீகரிக்கப்பட்ட ஆவணப் பதில் நீங்கள் பார்க்க அனுமதிக்கப்பட்ட, தேர்ந்தெடுக்கப்பட்ட, "
            "தயாரிப்புக்கு அங்கீகரிக்கப்பட்ட தொகுப்பிலிருந்து மட்டுமே உருவாக்கப்படுகிறது -- "
            "சாண்ட்பாக்ஸ், தனிமைப்படுத்தப்பட்ட, அல்லது பயிற்சிக்கு மட்டுமான தரவிலிருந்து அல்ல. "
            "தகவல் எங்கிருந்து வந்தது என்பதை நீங்கள் பார்க்க முடியும் வகையில், முடிந்தவரை "
            "பொது-பாதுகாப்பான மேற்கோள்களுடன் இது வழங்கப்படுகிறது."
        ),
    },
    {
        "id": "why_rag_insufficient",
        "question_en": (
            "Why did the chatbot say there wasn't enough evidence to answer from "
            "the documents?"
        ),
        "question_ta": (
            "ஆவணங்களிலிருந்து பதிலளிக்க போதிய ஆதாரம் இல்லை என்று சாட்பாட் ஏன் கூறியது?"
        ),
        "answer_en": (
            "When the approved document collection doesn't contain a well-supported answer "
            "to your question, the chatbot reports that honestly instead of inventing an "
            "answer or falling back to an unsupported guess."
        ),
        "answer_ta": (
            "அங்கீகரிக்கப்பட்ட ஆவணத் தொகுப்பில் உங்கள் கேள்விக்கு நன்கு ஆதரிக்கப்பட்ட பதில் "
            "இல்லாதபோது, ஒரு பதிலை கற்பனை செய்வதற்கு அல்லது ஆதரவற்ற ஒரு யூகத்திற்குத் "
            "திரும்புவதற்குப் பதிலாக, சாட்பாட் அதை நேர்மையாகத் தெரிவிக்கிறது."
        ),
    },
    {
        "id": "why_tanglish_input_gets_tamil_output",
        "question_en": (
            "I typed in Tanglish (Tamil written in English letters) -- why did I "
            "get a reply in Tamil script?"
        ),
        "question_ta": (
            "நான் தங்லிஷில் (ஆங்கில எழுத்துக்களில் தமிழ்) தட்டச்சு செய்தேன் -- "
            "தமிழ் எழுத்தில் ஏன் பதில் கிடைத்தது?"
        ),
        "answer_en": (
            "Public answers are always written in proper Tamil or English script -- Tanglish "
            "is never used as an output language, even though it's fully accepted as input. "
            "By default, Tanglish input is answered in Tamil script."
        ),
        "answer_ta": (
            "பொது பதில்கள் எப்போதும் சரியான தமிழ் அல்லது ஆங்கில எழுத்தில் எழுதப்படும் -- "
            "தங்லிஷ் ஒருபோதும் வெளியீட்டு மொழியாகப் பயன்படுத்தப்படாது, அது உள்ளீடாக முழுமையாக "
            "ஏற்றுக்கொள்ளப்பட்டாலும். இயல்பாக, தங்லிஷ் உள்ளீட்டிற்கு தமிழ் எழுத்தில் பதில் "
            "அளிக்கப்படும்."
        ),
    },
    {
        "id": "why_memory_not_shown_as_citation",
        "question_en": (
            "Why isn't something I told the chatbot earlier shown as a citation "
            "or source?"
        ),
        "question_ta": (
            "நான் முன்பு சாட்பாட்டிடம் கூறிய ஒன்று மேற்கோள் அல்லது ஆதாரமாக ஏன் "
            "காட்டப்படவில்லை?"
        ),
        "answer_en": (
            "Your conversation memory is personal context, not verified public evidence -- it "
            "is used only with your consent and is never presented as an external citation, "
            "and it is never used as the sole basis for a factual or current-events answer."
        ),
        "answer_ta": (
            "உங்கள் உரையாடல் நினைவகம் தனிப்பட்ட சூழல் மட்டுமே, சரிபார்க்கப்பட்ட பொது ஆதாரம் "
            "அல்ல -- இது உங்கள் சம்மதத்துடன் மட்டுமே பயன்படுத்தப்படுகிறது, ஒருபோதும் வெளிப்புற "
            "மேற்கோளாக வழங்கப்படாது, மேலும் ஒரு உண்மை அல்லது நடப்பு நிகழ்வு பதிலுக்கான ஒரே "
            "அடிப்படையாக ஒருபோதும் பயன்படுத்தப்படாது."
        ),
    },
    {
        "id": "why_clarification_was_asked",
        "question_en": "Why did the chatbot ask me a question instead of answering?",
        "question_ta": "பதிலளிப்பதற்குப் பதிலாக சாட்பாட் ஏன் என்னிடம் ஒரு கேள்வி கேட்டது?",
        "answer_en": (
            "Your message was ambiguous enough that answering directly could easily be wrong. "
            "The chatbot asks one focused clarifying question rather than guessing what you meant."
        ),
        "answer_ta": (
            "உங்கள் செய்தி நேரடியாக பதிலளிப்பது எளிதில் தவறாக இருக்கும் அளவிற்கு தெளிவற்றதாக "
            "இருந்தது. நீங்கள் என்ன சொல்ல வந்தீர்கள் என்று யூகிப்பதற்குப் பதிலாக, சாட்பாட் ஒரு "
            "குறிப்பிட்ட தெளிவுபடுத்தும் கேள்வியைக் கேட்கிறது."
        ),
    },
    {
        "id": "why_request_was_refused",
        "question_en": "Why did the chatbot refuse to answer my request?",
        "question_ta": "என் கோரிக்கைக்கு பதிலளிக்க சாட்பாட் ஏன் மறுத்தது?",
        "answer_en": (
            "Your message matched a category the safety check treats as unsafe to answer in "
            "detail. This is a safety refusal, not a knowledge gap -- the chatbot doesn't have "
            "an answer withheld, it's declining to provide the specific content requested."
        ),
        "answer_ta": (
            "உங்கள் செய்தி பாதுகாப்பு சரிபார்ப்பு விரிவாக பதிலளிக்க பாதுகாப்பற்றது என்று "
            "கருதும் ஒரு வகையுடன் பொருந்தியது. இது ஒரு பாதுகாப்பு மறுப்பு, அறிவு இடைவெளி "
            "அல்ல -- சாட்பாட் ஒரு பதிலை நிறுத்தி வைக்கவில்லை, கோரப்பட்ட குறிப்பிட்ட "
            "உள்ளடக்கத்தை வழங்க மறுக்கிறது."
        ),
    },
)

HELP_FAQ_BY_ID: dict[str, HelpFaqEntry] = {entry["id"]: entry for entry in HELP_FAQ_ENTRIES}

__all__ = ["HELP_FAQ_BY_ID", "HELP_FAQ_ENTRIES", "HelpFaqEntry"]
