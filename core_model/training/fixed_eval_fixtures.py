"""Fixed, versioned held-out evaluation fixtures for Phase 11.

These sentences are hardcoded literals — they are never sourced from the
training dataset, so they cannot leak into training regardless of which
dataset version an experiment uses. They are ground truth only in the sense
that they are real, human-written sentences; no model-generated text is used
as ground truth anywhere in this module.
"""

from __future__ import annotations

FIXTURE_VERSION = "phase11-fixed-eval-v1"

TAMIL_SENTENCES: tuple[str, ...] = (
    "வணக்கம், எப்படி இருக்கிறீர்கள்?",
    "இன்று வானிலை மிகவும் நன்றாக இருக்கிறது.",
    "தமிழ் ஒரு பழமையான மொழி.",
    "நான் பள்ளிக்குச் செல்கிறேன்.",
    "இது ஒரு எளிய விளக்கம்.",
    "புத்தகங்கள் அறிவை வளர்க்கின்றன.",
    "அவர் நேற்று வீட்டிற்கு வந்தார்.",
    "இந்த ஊரில் மழை நிறைய பெய்தது.",
    "எண்கள்: ஒன்று, இரண்டு, மூன்று, நான்கு, ஐந்து.",
    "தமிழ் எழுத்துக்கள்: க், ங், ச், ஞ், ட், ண்.",
    "அம்மா சமையல் செய்கிறாள்.",
    "நண்பர்களுடன் விளையாடுவது மகிழ்ச்சி அளிக்கும்.",
)

ENGLISH_SENTENCES: tuple[str, ...] = (
    "Hello, how are you today?",
    "The weather is very pleasant this morning.",
    "English is spoken widely around the world.",
    "I am going to school now.",
    "This is a simple explanation of the topic.",
    "Books help people learn new things.",
    "She arrived home yesterday evening.",
    "It rained heavily in this town last week.",
    "Numbers: one, two, three, four, five.",
    "Friends enjoy playing games together.",
    "The train leaves the station at nine.",
    "Water boils at one hundred degrees Celsius.",
)

TANGLISH_SENTENCES: tuple[str, ...] = (
    "vanakkam epdi irukeenga?",
    "indha weather romba nalla irukku.",
    "naan school ku poren.",
    "idhu oru simple explanation.",
    "books padikardhu nalla habit.",
    "avaru nethu veetuku vandhaaru.",
    "இந்த ஊரு la rain nalla pochu.",
    "friends கூட்ட விளையாடுறது fun ஆ இருக்கும்.",
    "naan office la irukken இப்போ.",
    "atha konjam clear ஆ சொல்லுங்க.",
)

MIXED_SENTENCES: tuple[str, ...] = (
    "இந்த laptop-ஐ configure பண்ண வேண்டும்.",
    "நான் meeting-க்கு late ஆக வந்தேன்.",
    "This வாக்கியம் தமிழ் மற்றும் English கலந்தது.",
    "Please இந்த file-ஐ download பண்ணுங்க.",
    "அவள் project-ஐ successfully complete பண்ணினாள்.",
    "The server இப்போ maintenance mode-ல் இருக்கு.",
    "இந்த recipe-க்கு two cups rice தேவை.",
    "He தினமும் gym-க்கு போவான்.",
)


def all_fixtures() -> dict[str, tuple[str, ...]]:
    return {
        "ta": TAMIL_SENTENCES,
        "en": ENGLISH_SENTENCES,
        "tgl": TANGLISH_SENTENCES,
        "mixed": MIXED_SENTENCES,
    }
