"""
Phase 60 WS07 E3: Admin Assistant Controlled Dataset Expansion & Translation Engine.
Provides deterministic, context-aware translation with polysemy/ambiguity detection,
phonetic Tamil -> Tanglish transliteration, and multi-level dataset candidate generation.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class GenerationType(str, Enum):
    WORD_LEVEL = "word_level"
    PHRASE_LEVEL = "phrase_level"
    SENTENCE_LEVEL = "sentence_level"
    TRANSLATION_DIRECTION = "translation_direction"
    MIXED_BILINGUAL = "mixed_bilingual"
    CONVERSATIONAL = "conversational"
    INSTRUCTION = "instruction"


class ProvenanceClass(str, Enum):
    HUMAN_AUTHORED = "HUMAN_AUTHORED"
    HUMAN_EDITED_AI_PROPOSAL = "HUMAN_EDITED_AI_PROPOSAL"
    AI_GENERATED_ADMIN_APPROVED = "AI_GENERATED_ADMIN_APPROVED"


@dataclass
class TranslationCandidate:
    tamil_concept: str
    english_translation: str
    tanglish_transliteration: str
    alternative_translations: list[str] = field(default_factory=list)
    is_ambiguous: bool = False
    ambiguity_reason: str = ""
    context_notes: str = ""
    confidence: float = 0.95


@dataclass
class ExpansionProposal:
    proposal_id: str
    source_concept: str
    generation_type: GenerationType
    language: str  # "ta", "en", "mixed", "tgl"
    capability_id: str
    task_type: str
    instruction: str
    response: str
    optional_context: str = ""
    confidence: float = 0.95
    provenance: dict[str, Any] = field(default_factory=dict)
    validation: dict[str, Any] = field(default_factory=dict)
    approval_status: str = "PENDING"  # PENDING, APPROVED, REJECTED, EDITED


# Deterministic lexicon with polysemy / context discrimination
TAMIL_ENGLISH_LEXICON: dict[str, dict[str, Any]] = {
    "அம்மா": {
        "primary": "mother",
        "alts": ["mom", "mama"],
        "tanglish": "amma",
        "tanglish_alts": ["ammaa", "ammah"],
        "is_ambiguous": False,
        "sample_phrase": ("என் அம்மா", "my mother", "en amma"),
        "sample_sentence": (
            "என் அம்மா வீட்டில் இருக்கிறார்.",
            "My mother is at home.",
            "En amma veetla irukkaar."
        ),
    },
    "அப்பா": {
        "primary": "father",
        "alts": ["dad", "papa"],
        "tanglish": "appa",
        "tanglish_alts": ["appaa", "appah"],
        "is_ambiguous": False,
        "sample_phrase": ("என் அப்பா", "my father", "en appa"),
        "sample_sentence": (
            "என் அப்பா அலுவலகம் செல்கிறார்.",
            "My father goes to the office.",
            "En appa office poraaru."
        ),
    },
    "வீடு": {
        "primary": "house",
        "alts": ["home", "residence"],
        "tanglish": "veedu",
        "tanglish_alts": ["veetu", "veeduu"],
        "is_ambiguous": False,
        "sample_phrase": ("பெரிய வீடு", "big house", "periya veedu"),
        "sample_sentence": (
            "எங்கள் வீடு அழகாக உள்ளது.",
            "Our house is beautiful.",
            "Enga veedu azhagaa irukku."
        ),
    },
    "தண்ணீர்": {
        "primary": "water",
        "alts": ["drinking water"],
        "tanglish": "thanneer",
        "tanglish_alts": ["thanni", "thaneer"],
        "is_ambiguous": False,
        "sample_phrase": ("குடி தண்ணீர்", "drinking water", "kudi thanneer"),
        "sample_sentence": (
            "சுத்தமான தண்ணீர் குடிப்பது நல்லது.",
            "Drinking clean water is good for health.",
            "Clean thanneer kudipathu nalladhu."
        ),
    },
    "சாப்பாடு": {
        "primary": "food",
        "alts": ["meal", "rice"],
        "tanglish": "saappadu",
        "tanglish_alts": ["sappadu", "saapaadu"],
        "is_ambiguous": False,
        "sample_phrase": ("மதிய சாப்பாடு", "lunch", "madhiya saappadu"),
        "sample_sentence": (
            "மதிய சாப்பாடு தயாராக உள்ளது.",
            "Lunch is ready.",
            "Lunch saappadu ready-ah irukku."
        ),
    },
    "புத்தகம்": {
        "primary": "book",
        "alts": ["volume", "tome"],
        "tanglish": "puthagam",
        "tanglish_alts": ["pusthakam", "puththagam"],
        "is_ambiguous": False,
        "sample_phrase": ("தமிழ் புத்தகம்", "Tamil book", "Tamil puthagam"),
        "sample_sentence": (
            "நான் ஒரு புத்தகம் படிக்கிறேன்.",
            "I am reading a book.",
            "Naan oru book padikiren."
        ),
    },
    "வணக்கம்": {
        "primary": "greetings",
        "alts": ["hello", "namaste"],
        "tanglish": "vanakkam",
        "tanglish_alts": ["vanakam"],
        "is_ambiguous": False,
        "sample_phrase": ("காலை வணக்கம்", "good morning", "kaalai vanakkam"),
        "sample_sentence": (
            "அனைவருக்கும் இனிய காலை வணக்கம்.",
            "Good morning greetings to everyone.",
            "Anaivarukkum good morning vanakkam."
        ),
    },
    "நன்றி": {
        "primary": "thank you",
        "alts": ["thanks", "gratitude"],
        "tanglish": "nandri",
        "tanglish_alts": ["nanri", "nandree"],
        "is_ambiguous": False,
        "sample_phrase": ("மிக்க நன்றி", "thank you very much", "mikka nandri"),
        "sample_sentence": (
            "உங்கள் உதவிக்கு மிக்க நன்றி.",
            "Thank you very much for your help.",
            "Unga help-ku mikka nandri."
        ),
    },
    # Polysemous concepts requiring context disambiguation
    "பால்": {
        "primary": "milk",
        "alts": ["gender / grammatical classification", "share / portion"],
        "tanglish": "paal",
        "tanglish_alts": ["pal"],
        "is_ambiguous": True,
        "ambiguity_reason": "Polysemous noun: means 'milk' (beverage) or 'grammatical gender/class' (ஆண்பால்/பெண்பால்) or 'portion' (பகுதி). Context is strictly required.",
        "sample_phrase": ("பசும்பால்", "cow's milk", "pasum paal"),
        "sample_sentence": (
            "குழந்தை பசும்பால் குடிக்கிறது.",
            "The baby is drinking cow's milk.",
            "Kuzhandhai cow's paal kudikkudhu."
        ),
    },
    "படி": {
        "primary": "read / study",
        "alts": ["step / stair", "measure", "manner / as"],
        "tanglish": "padi",
        "tanglish_alts": ["padii"],
        "is_ambiguous": True,
        "ambiguity_reason": "Polysemous verb/noun: means 'to read/study' (verb) or 'staircase step' (noun) or 'volumetric measure' (படி அரிசி). Context required.",
        "sample_phrase": ("நன்றாக படி", "study well", "nandraaga padi"),
        "sample_sentence": (
            "தேர்வுக்கு நன்றாக படி.",
            "Study well for the examination.",
            "Exam-ku nalla padi."
        ),
    },
    "திங்கள்": {
        "primary": "Monday",
        "alts": ["moon", "month"],
        "tanglish": "thingal",
        "tanglish_alts": ["tingal"],
        "is_ambiguous": True,
        "ambiguity_reason": "Polysemous noun: means 'Monday' (day of week), 'moon' (சந்திரன்), or archaic 'month'.",
        "sample_phrase": ("திங்கட்கிழமை", "Monday", "thingat kizhamai"),
        "sample_sentence": (
            "நாளை திங்கட்கிழமை பள்ளி திறக்கப்படுகிறது.",
            "School opens tomorrow on Monday.",
            "Naalai Monday school open aagudhu."
        ),
    },
}


class TanglishTransliterationEngine:
    """Phonetic Tamil to Tanglish transliteration and normalization."""

    VOWELS = {
        "அ": "a", "ஆ": "aa", "இ": "i", "ஈ": "ee", "உ": "u", "ஊ": "oo",
        "எ": "e", "ஏ": "ae", "ஐ": "ai", "ஒ": "o", "ஓ": "oo", "ஔ": "au"
    }

    VOWEL_SIGNS = {
        "ா": "aa", "ி": "i", "ீ": "ee", "ு": "u", "ூ": "oo",
        "ெ": "e", "ே": "ae", "ை": "ai", "ொ": "o", "ோ": "oo", "ௌ": "au"
    }

    CONSONANTS = {
        "க": "k", "ங": "ng", "ச": "ch", "ஞ": "nj", "ட": "t", "ண": "n",
        "த": "th", "ந": "n", "ப": "p", "ம": "m", "ய": "y", "ர": "r",
        "ல": "l", "வ": "v", "ழ": "zh", "ள": "l", "ற": "r", "ன": "n",
        "ஜ": "j", "ஷ": "sh", "ஸ": "s", "ஹ": "h"
    }

    VIRAMA = "்"
    AYTHAM = {"ஃ": "kh"}

    # Tanglish phonetic spelling normalization mapping
    NORMALIZATION_VARIANTS: dict[str, str] = {
        "ammaa": "amma",
        "ammah": "amma",
        "appaa": "appa",
        "appah": "appa",
        "veetu": "veedu",
        "veeduu": "veedu",
        "thanni": "thanneer",
        "thaneer": "thanneer",
        "sappadu": "saappadu",
        "saapaadu": "saappadu",
        "vanakam": "vanakkam",
        "nanri": "nandri",
        "nandree": "nandri",
        "tingal": "thingal",
        "chaappaatu": "saappadu",
    }

    @classmethod
    def transliterate(cls, tamil_text: str) -> str:
        """Deterministically transliterates Tamil Unicode to phonetic Tanglish."""
        if not tamil_text:
            return ""

        # Normalize Unicode NFC
        text = unicodedata.normalize("NFC", tamil_text)
        out = []
        i = 0
        n = len(text)

        while i < n:
            ch = text[i]

            # Vowels
            if ch in cls.VOWELS:
                out.append(cls.VOWELS[ch])
                i += 1
            # Aytham
            elif ch in cls.AYTHAM:
                out.append(cls.AYTHAM[ch])
                i += 1
            # Consonants
            elif ch in cls.CONSONANTS:
                base_c = cls.CONSONANTS[ch]
                # Check next character
                if i + 1 < n and text[i + 1] == cls.VIRAMA:
                    out.append(base_c)
                    i += 2
                elif i + 1 < n and text[i + 1] in cls.VOWEL_SIGNS:
                    sign = text[i + 1]
                    out.append(base_c + cls.VOWEL_SIGNS[sign])
                    i += 2
                else:
                    # Inherent 'a' vowel
                    out.append(base_c + "a")
                    i += 1
            else:
                # Spaces, punctuation, ASCII
                out.append(ch)
                i += 1

        res = "".join(out)
        return res

    @classmethod
    def normalize_tanglish_word(cls, word: str) -> str:
        """Normalizes variant Tanglish spellings to the canonical representation."""
        lowered = word.lower().strip()
        return cls.NORMALIZATION_VARIANTS.get(lowered, lowered)

    @classmethod
    def transliterate_to_canonical(cls, tamil_text: str) -> str:
        """Transliterates Tamil to phonetic Tanglish and applies canonical spelling normalization."""
        raw = cls.transliterate(tamil_text)
        words = raw.split()
        norm_words = [cls.normalize_tanglish_word(w) for w in words]
        return " ".join(norm_words)


class BilingualTranslationEngine:
    """Context-aware translation engine with explicit polysemy and ambiguity handling."""

    @classmethod
    def translate_concept(cls, tamil_concept: str, context: str = "") -> TranslationCandidate:
        concept = tamil_concept.strip()
        lex_entry = TAMIL_ENGLISH_LEXICON.get(concept)

        if not lex_entry:
            # Fallback phonetic transliteration
            tgl = TanglishTransliterationEngine.transliterate(concept)
            return TranslationCandidate(
                tamil_concept=concept,
                english_translation=concept,
                tanglish_transliteration=tgl,
                alternative_translations=[],
                is_ambiguous=True,
                ambiguity_reason="Out of dictionary concept. Phonetic fallback used.",
                confidence=0.50
            )

        primary_en = lex_entry["primary"]
        alts_en = lex_entry.get("alts", [])
        tgl = lex_entry.get("tanglish", TanglishTransliterationEngine.transliterate(concept))
        is_ambiguous = lex_entry.get("is_ambiguous", False)
        ambiguity_reason = lex_entry.get("ambiguity_reason", "")

        # Ambiguity resolution via context check
        confidence = 0.98
        if is_ambiguous:
            if not context:
                # Ambiguous without disambiguating context -> penalty
                confidence = 0.70
            else:
                # Context provided -> check for domain keywords
                context_lower = context.lower()
                if "பசு" in context or "குடி" in context or "milk" in context_lower:
                    primary_en = "milk"
                    confidence = 0.95
                elif "இலக்கணம்" in context or "ஆண்பால்" in context or "gender" in context_lower:
                    primary_en = "grammatical gender / classification"
                    confidence = 0.95
                else:
                    confidence = 0.75

        return TranslationCandidate(
            tamil_concept=concept,
            english_translation=primary_en,
            tanglish_transliteration=tgl,
            alternative_translations=alts_en,
            is_ambiguous=is_ambiguous,
            ambiguity_reason=ambiguity_reason,
            context_notes=context,
            confidence=confidence
        )


class DatasetExpansionEngine:
    """Proposes multi-level training records from approved Tamil concepts."""

    def __init__(self, generator_version: str = "v1.0.0", max_proposals_per_concept: int = 8):
        self.generator_version = generator_version
        self.max_proposals_per_concept = max_proposals_per_concept

    def generate_proposals_for_concept(
        self,
        concept: str,
        provenance_source: str = "admin_approved_vocabulary"
    ) -> list[ExpansionProposal]:
        candidate = BilingualTranslationEngine.translate_concept(concept)
        lex_data = TAMIL_ENGLISH_LEXICON.get(concept, {})
        proposals: list[ExpansionProposal] = []

        ta_c = candidate.tamil_concept
        en_c = candidate.english_translation
        tgl_c = candidate.tanglish_transliteration
        conf = candidate.confidence

        common_prov = {
            "generated_by": "admin_assistant_mini_brain",
            "generator_version": self.generator_version,
            "source_concept": ta_c,
            "provenance_class": ProvenanceClass.AI_GENERATED_ADMIN_APPROVED.value,
            "source_dataset": provenance_source,
            "is_ambiguous": candidate.is_ambiguous
        }

        # 1. Word-Level (CAP-17 Translation)
        p1 = ExpansionProposal(
            proposal_id=f"prop_{ta_c}_word",
            source_concept=ta_c,
            generation_type=GenerationType.WORD_LEVEL,
            language="mixed",
            capability_id="CAP-17",
            task_type="bilingual_vocabulary",
            instruction=f"'{ta_c}' என்ற தமிழ் சொல்லின் ஆங்கில அர்த்தம் மற்றும் Tanglish ஒலிபெயர்ப்பு என்ன?",
            response=f"English: {en_c} | Tanglish: {tgl_c}",
            confidence=conf,
            provenance=dict(common_prov, subtype="word_level")
        )
        proposals.append(p1)

        # 2. Phrase-Level (CAP-17 Translation)
        sample_phrase = lex_data.get("sample_phrase", (f"என் {ta_c}", f"my {en_c}", f"en {tgl_c}"))
        p2 = ExpansionProposal(
            proposal_id=f"prop_{ta_c}_phrase",
            source_concept=ta_c,
            generation_type=GenerationType.PHRASE_LEVEL,
            language="mixed",
            capability_id="CAP-17",
            task_type="phrase_alignment",
            instruction=f"Translate phrase to English and Tanglish: '{sample_phrase[0]}'",
            response=f"English: {sample_phrase[1]} | Tanglish: {sample_phrase[2]}",
            confidence=conf,
            provenance=dict(common_prov, subtype="phrase_level")
        )
        proposals.append(p2)

        # 3. Sentence-Level (CAP-17 Translation)
        sample_sent = lex_data.get("sample_sentence", (
            f"இது {ta_c}.", f"This is {en_c}.", f"Idhu {tgl_c}."
        ))
        p3 = ExpansionProposal(
            proposal_id=f"prop_{ta_c}_sent",
            source_concept=ta_c,
            generation_type=GenerationType.SENTENCE_LEVEL,
            language="ta",
            capability_id="CAP-17",
            task_type="sentence_translation",
            instruction=f"பின்வரும் தமிழ் வாக்கியத்தை ஆங்கிலத்தில் மொழிபெயர்க்கவும்: '{sample_sent[0]}'",
            response=sample_sent[1],
            confidence=conf,
            provenance=dict(common_prov, subtype="sentence_level")
        )
        proposals.append(p3)

        # 4. Translation-Direction: English -> Tamil (CAP-17)
        p4 = ExpansionProposal(
            proposal_id=f"prop_{ta_c}_en_to_ta",
            source_concept=ta_c,
            generation_type=GenerationType.TRANSLATION_DIRECTION,
            language="en",
            capability_id="CAP-17",
            task_type="reverse_translation",
            instruction=f"What is the Tamil word for '{en_c}'?",
            response=f"The Tamil word for '{en_c}' is '{ta_c}'.",
            confidence=conf,
            provenance=dict(common_prov, subtype="direction_en_to_ta")
        )
        proposals.append(p4)

        # 5. Translation-Direction: Tamil -> Tanglish (CAP-06 Tanglish)
        p5 = ExpansionProposal(
            proposal_id=f"prop_{ta_c}_ta_to_tgl",
            source_concept=ta_c,
            generation_type=GenerationType.TRANSLATION_DIRECTION,
            language="tgl",
            capability_id="CAP-06",
            task_type="transliteration",
            instruction=f"'{ta_c}' என்பதன் Tanglish வடிவம் என்ன?",
            response=f"'{ta_c}' என்பதன் Tanglish சொல் '{tgl_c}'.",
            confidence=conf,
            provenance=dict(common_prov, subtype="direction_ta_to_tgl")
        )
        proposals.append(p5)

        # 6. Mixed Bilingual Example (CAP-05 Language ID / Code-Switching)
        mixed_sent = f"My {ta_c} வீட்டில் இருக்கிறார்."
        p6 = ExpansionProposal(
            proposal_id=f"prop_{ta_c}_mixed",
            source_concept=ta_c,
            generation_type=GenerationType.MIXED_BILINGUAL,
            language="mixed",
            capability_id="CAP-05",
            task_type="mixed_bilingual_explanation",
            instruction=f"'{mixed_sent}' - இந்த வாக்கியத்தில் உள்ள மொழிகளைக் கண்டறிந்து திருத்தவும்.",
            response=f"இந்த வாக்கியத்தில் ஆங்கிலம் ('My') மற்றும் தமிழ் ('{ta_c} வீட்டில் இருக்கிறார்') கலந்துள்ளது. முழுமையான தமிழாக்கம்: '{sample_sent[0]}'.",
            confidence=conf,
            provenance=dict(common_prov, subtype="mixed_bilingual")
        )
        proposals.append(p6)

        # 7. Conversational QA (CAP-11 Dialogue)
        p7 = ExpansionProposal(
            proposal_id=f"prop_{ta_c}_dialogue",
            source_concept=ta_c,
            generation_type=GenerationType.CONVERSATIONAL,
            language="ta",
            capability_id="CAP-11",
            task_type="conversational_qa",
            instruction=f"வணக்கம்! '{ta_c}' பற்றி எனக்கு சொல்ல முடியுமா?",
            response=f"வணக்கம்! '{ta_c}' என்பது '{en_c}' என்ற பொருள் தரும் சொல். உதாரணமாக, '{sample_sent[0]}'.",
            confidence=conf,
            provenance=dict(common_prov, subtype="conversational_qa")
        )
        proposals.append(p7)

        # 8. Instruction Following (CAP-04 Instructions)
        p8 = ExpansionProposal(
            proposal_id=f"prop_{ta_c}_instruction",
            source_concept=ta_c,
            generation_type=GenerationType.INSTRUCTION,
            language="ta",
            capability_id="CAP-04",
            task_type="direct_instruction",
            instruction=f"'{ta_c}' என்ற சொல்லைப் பயன்படுத்தி ஒரு எளிய வாக்கியம் அமைக்கவும்.",
            response=sample_sent[0],
            confidence=conf,
            provenance=dict(common_prov, subtype="direct_instruction")
        )
        proposals.append(p8)

        # Apply synthetic volume limits
        return proposals[:self.max_proposals_per_concept]
