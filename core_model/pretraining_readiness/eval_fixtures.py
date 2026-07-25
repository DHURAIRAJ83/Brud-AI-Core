"""Fixed, hand-authored, project-authored tokenizer evaluation
fixtures -- never model-generated, never copied from any protected
benchmark or validation/test fixture set. Covers Tamil grammatical
categories (vowels, consonants, uyirmei letters, agglutinated forms,
plurals, case markers, verb forms, long compounds, domain
terminology) plus Tanglish and mixed Tamil-English samples."""

from __future__ import annotations

TAMIL_GRAMMAR_SAMPLES: dict[str, list[str]] = {
    "uyir_ezhuthukkal_vowels": ["அ", "ஆ", "இ", "ஈ", "உ", "ஊ", "எ", "ஏ", "ஐ", "ஒ", "ஓ", "ஔ"],
    "mei_ezhuthukkal_consonants": ["க்", "ங்", "ச்", "ஞ்", "ட்", "ண்", "த்", "ந்", "ப்", "ம்"],
    "uyirmei_ezhuthukkal": ["க", "கா", "கி", "கீ", "கு", "கூ", "கெ", "கே", "கை", "கொ", "கோ"],
    "agglutinated_forms": ["மரம்", "மரங்கள்", "மரத்தில்", "மரத்திலிருந்து"],
    "compound_terms": ["தமிழ்மொழி", "விவசாயத்தொழில்நுட்பம்", "மழைநீர்சேகரிப்பு"],
    "plurals_panmai": ["பையன்", "பையன்கள்", "மரம்", "மரங்கள்", "புத்தகம்", "புத்தகங்கள்"],
    "case_markers_vetrumai": ["மரத்தை", "மரத்தால்", "மரத்திற்கு", "மரத்தின்", "மரத்தில்", "மரத்தோடு"],
    "verb_forms_vinaimutru": ["படித்தான்", "படிக்கிறாள்", "படிப்பேன்", "படித்திருந்தார்கள்"],
    "long_words": ["ஆசிரியர்களுக்காகவும்", "பள்ளிக்கூடத்திற்குச்சென்றார்கள்"],
    "science_terms": ["ஒளிச்சேர்க்கை", "புவியீர்ப்பு விசை", "மூலக்கூறு"],
    "agriculture_terms": ["விவசாயம்", "பயிர் சுழற்சி", "நீர்ப்பாசனம்"],
    "technology_terms": ["செயற்கை நுண்ணறிவு", "தரவுத்தளம்", "நிரலாக்கம்"],
}

TANGLISH_SAMPLES: list[str] = [
    "epdi",
    "eppadi",
    "enna",
    "ennaku",
    "training epdi start panrathu",
    "Tamil model-ku data ready pannunga",
    "naan office ku poren",
    "indha vaaram semma busy ah irundhuchu",
]

MIXED_SAMPLES: list[str] = [
    "இன்று meeting ரொம்ப நல்லா போயிடுச்சு",
    "Tamil Nadu-வில் agriculture technology semma வளர்ந்திருக்கு",
    "School students தமிழ் மொழியை கற்கின்றனர்",
]

ENGLISH_SAMPLES: list[str] = [
    "The quick brown fox jumps over the lazy dog.",
    "Agriculture technology is improving crop yields.",
    "Photosynthesis converts sunlight into chemical energy.",
]


def all_fixtures() -> dict[str, list[str]]:
    fixtures = dict(TAMIL_GRAMMAR_SAMPLES)
    fixtures["tanglish"] = TANGLISH_SAMPLES
    fixtures["mixed"] = MIXED_SAMPLES
    fixtures["english"] = ENGLISH_SAMPLES
    return fixtures
