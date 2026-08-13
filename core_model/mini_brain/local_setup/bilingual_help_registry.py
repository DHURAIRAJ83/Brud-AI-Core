"""MB-29: Bilingual Help Registry -- pure. Static Tamil+English help
text for every Local Setup dashboard sub-tab, keyed `local_setup.<tab>`.
"""

from __future__ import annotations

from typing import Any

HELP_REGISTRY: dict[str, dict[str, str]] = {
    "local_setup.hardware": {
        "title_en": "Hardware", "title_ta": "வன்பொருள்",
        "body_en": "Shows your machine's RAM, CPU, and disk space, and a health badge for the local model runtime.",
        "body_ta": "உங்கள் கணினியின் RAM, CPU மற்றும் வட்டு இடத்தையும், உள்ளூர் மாடல் இயக்கத்திற்கான ஆரோக்கிய பதக்கத்தையும் காட்டுகிறது.",
    },
    "local_setup.local_models": {
        "title_en": "Local Models", "title_ta": "உள்ளூர் மாடல்கள்",
        "body_en": "Scans the allowed model directory (and any admin-configured additional directories) for .gguf files already on disk.",
        "body_ta": "அனுமதிக்கப்பட்ட மாடல் அடைவில் (மற்றும் நிர்வாகி அமைத்த கூடுதல் அடைவுகளில்) ஏற்கனவே உள்ள .gguf கோப்புகளை ஸ்கேன் செய்கிறது.",
    },
    "local_setup.recommendations": {
        "title_en": "Recommendations", "title_ta": "பரிந்துரைகள்",
        "body_en": "Suggests the best local model for your detected RAM tier -- nothing is downloaded automatically.",
        "body_ta": "உங்கள் கண்டறியப்பட்ட RAM அடுக்குக்கு சிறந்த உள்ளூர் மாடலை பரிந்துரைக்கிறது -- எதுவும் தானாக பதிவிறக்கப்படாது.",
    },
    "local_setup.local_configuration": {
        "title_en": "Local Configuration", "title_ta": "உள்ளூர் அமைப்பு",
        "body_en": "Set the model path and runtime parameters (context length, max tokens, temperature, threads), then save.",
        "body_ta": "மாடல் பாதை மற்றும் இயக்க அளவுருக்களை (context length, max tokens, temperature, threads) அமைத்து சேமிக்கவும்.",
    },
    "local_setup.external_providers": {
        "title_en": "External Providers", "title_ta": "வெளிப்புற வழங்குநர்கள்",
        "body_en": "Optionally configure OpenAI, Anthropic, Gemini, or OpenRouter as a fallback when the local model is unavailable.",
        "body_ta": "உள்ளூர் மாடல் கிடைக்காதபோது OpenAI, Anthropic, Gemini அல்லது OpenRouter-ஐ மாற்றாக விருப்பப்படி அமைக்கலாம்.",
    },
    "local_setup.diagnostics": {
        "title_en": "Diagnostics", "title_ta": "நோயறிதல்",
        "body_en": "Raw status snapshot -- hardware, scan counts, and the currently configured model, with paths always masked.",
        "body_ta": "மூல நிலைப் பதிவு -- வன்பொருள், ஸ்கேன் எண்ணிக்கைகள், தற்போது அமைக்கப்பட்ட மாடல், பாதைகள் எப்போதும் மறைக்கப்படும்.",
    },
    "local_setup.setup_guide": {
        "title_en": "Setup Guide", "title_ta": "அமைப்பு வழிகாட்டி",
        "body_en": "A step-by-step walkthrough from checking hardware to saving a working local model configuration.",
        "body_ta": "வன்பொருளை சரிபார்ப்பதில் இருந்து உள்ளூர் மாடல் அமைப்பைச் சேமிப்பது வரை படிப்படியான வழிகாட்டி.",
    },
    "local_setup.help": {
        "title_en": "Help", "title_ta": "உதவி",
        "body_en": "This tab. Every Local Setup sub-tab has bilingual help available here.",
        "body_ta": "இந்த தாவல். ஒவ்வொரு Local Setup துணை-தாவலுக்கும் இருமொழி உதவி இங்கே கிடைக்கும்.",
    },
}


def help_for(key: str) -> dict[str, Any] | None:
    return HELP_REGISTRY.get(key)


def all_help() -> dict[str, dict[str, str]]:
    return dict(HELP_REGISTRY)
