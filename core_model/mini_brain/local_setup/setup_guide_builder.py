"""MB-29: Setup Guide Builder -- pure. Assembles a bilingual,
step-by-step guide from already-computed hardware/scan/recommendation
data -- never fetches or computes any of that itself.
"""

from __future__ import annotations

from typing import Any


def build_guide(
    *,
    hardware: dict[str, Any],
    scanned_model_count: int,
    top_recommendation: dict[str, Any] | None,
    local_model_configured: bool,
) -> dict[str, Any]:
    steps: list[dict[str, Any]] = [
        {
            "step": 1,
            "title_en": "Check your hardware", "title_ta": "உங்கள் வன்பொருளை சரிபார்க்கவும்",
            "body_en": f"Detected {hardware.get('total_ram_gb', 0)}GB RAM ({hardware.get('recommended_ram_tier', '?')} tier), {hardware.get('cpu_cores', 0)} CPU cores.",
            "body_ta": f"கண்டறியப்பட்டது {hardware.get('total_ram_gb', 0)}GB RAM ({hardware.get('recommended_ram_tier', '?')} அடுக்கு), {hardware.get('cpu_cores', 0)} CPU கோர்கள்.",
        },
        {
            "step": 2,
            "title_en": "Scan for local models", "title_ta": "உள்ளூர் மாடல்களை ஸ்கேன் செய்யவும்",
            "body_en": (
                f"Found {scanned_model_count} GGUF model(s) already on disk." if scanned_model_count
                else "No GGUF models found yet in the allowed model directory."
            ),
            "body_ta": (
                f"{scanned_model_count} GGUF மாடல்(கள்) ஏற்கனவே கிடைத்தன." if scanned_model_count
                else "அனுமதிக்கப்பட்ட மாடல் அடைவில் இன்னும் GGUF மாடல்கள் இல்லை."
            ),
        },
    ]

    if top_recommendation:
        steps.append({
            "step": 3,
            "title_en": "Download the recommended model", "title_ta": "பரிந்துரைக்கப்பட்ட மாடலைப் பதிவிறக்கவும்",
            "body_en": (
                f"Recommended: {top_recommendation['model_name']} ({top_recommendation['quantization']}) -- "
                f"~{top_recommendation['expected_ram_usage_gb']}GB RAM expected. Download it manually and place it "
                "in the allowed model directory -- this dashboard never downloads a model automatically."
            ),
            "body_ta": (
                f"பரிந்துரை: {top_recommendation['model_name']} ({top_recommendation['quantization']}) -- "
                f"~{top_recommendation['expected_ram_usage_gb']}GB RAM எதிர்பார்க்கப்படுகிறது. அதை கைமுறையாக பதிவிறக்கி "
                "அனுமதிக்கப்பட்ட மாடல் அடைவில் வைக்கவும் -- இந்த டாஷ்போர்டு ஒருபோதும் தானாக மாடலைப் பதிவிறக்காது."
            ),
        })

    steps.append({
        "step": len(steps) + 1,
        "title_en": "Save the local model configuration", "title_ta": "உள்ளூர் மாடல் அமைப்பைச் சேமிக்கவும்",
        "body_en": (
            "Configuration already saved." if local_model_configured
            else "Open the Local Configuration tab, set the model path, and press Save."
        ),
        "body_ta": (
            "அமைப்பு ஏற்கனவே சேமிக்கப்பட்டது." if local_model_configured
            else "உள்ளூர் அமைப்பு தாவலைத் திறந்து, மாடல் பாதையை அமைத்து, சேமி என்பதை அழுத்தவும்."
        ),
    })

    steps.append({
        "step": len(steps) + 1,
        "title_en": "Optional: enable an external provider", "title_ta": "விருப்பம்: வெளிப்புற வழங்குநரை இயக்கவும்",
        "body_en": "For heavier questions, configure an external provider (OpenAI, Anthropic, Gemini, OpenRouter) as a fallback -- entirely optional.",
        "body_ta": "கனமான கேள்விகளுக்கு, ஒரு வெளிப்புற வழங்குநரை (OpenAI, Anthropic, Gemini, OpenRouter) மாற்றாக அமைக்கலாம் -- முற்றிலும் விருப்பமானது.",
    })

    return {"steps": steps}
