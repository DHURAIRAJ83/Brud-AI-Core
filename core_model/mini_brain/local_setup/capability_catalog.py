"""MB-29: Capability Catalog -- pure. Canonical, bilingual vocabulary
for speed/support/quality levels, shared by `model_recommender.py` and
`provider_model_catalog.py` so both never independently invent their
own Tamil/English label text for the same concept.
"""

from __future__ import annotations

SPEED_LEVELS: dict[str, dict[str, str]] = {
    "excellent": {"en": "Excellent", "ta": "மிகச் சிறந்தது"},
    "good": {"en": "Good", "ta": "நல்லது"},
    "fair": {"en": "Fair", "ta": "மிதமானது"},
    "slow": {"en": "Slow", "ta": "மெதுவானது"},
}

SUPPORT_LEVELS: dict[str, dict[str, str]] = {
    "excellent": {"en": "Excellent", "ta": "மிகச் சிறந்தது"},
    "good": {"en": "Good", "ta": "நல்லது"},
    "fair": {"en": "Fair", "ta": "மிதமானது"},
    "limited": {"en": "Limited", "ta": "குறைவானது"},
}

YES_NO: dict[bool, dict[str, str]] = {
    True: {"en": "Yes", "ta": "ஆம்"},
    False: {"en": "No", "ta": "இல்லை"},
}

REASONING_LEVELS: dict[str, dict[str, str]] = {
    "high": {"en": "High", "ta": "அதிகம்"},
    "medium": {"en": "Medium", "ta": "நடுத்தரம்"},
    "low": {"en": "Low", "ta": "குறைவு"},
}

COST_HINTS: dict[str, dict[str, str]] = {
    "free": {"en": "Free", "ta": "இலவசம்"},
    "low": {"en": "Low cost", "ta": "குறைந்த செலவு"},
    "medium": {"en": "Medium cost", "ta": "நடுத்தர செலவு"},
    "high": {"en": "High cost", "ta": "அதிக செலவு"},
}


def label(catalog: dict[str, dict[str, str]], key: str) -> dict[str, str]:
    return catalog.get(key, {"en": key, "ta": key})


def bilingual(en: str, ta: str) -> dict[str, str]:
    return {"en": en, "ta": ta}


def yes_no(value: bool) -> dict[str, str]:
    return YES_NO[bool(value)]
