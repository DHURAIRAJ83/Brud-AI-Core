"""Deterministic instruction-example rendering, split at the assistant boundary."""

from __future__ import annotations

from core_model.instruction_tuning.templates import InstructionTemplate

ALL_SPECIAL_TOKENS = (
    "<bos>",
    "<eos>",
    "<system>",
    "<user>",
    "<assistant>",
    "<ta>",
    "<en>",
    "<tgl>",
    "<mixed>",
)


def render_example(
    validated: dict, language: str, template: InstructionTemplate
) -> tuple[str, str]:
    """Render one validated record into (prompt_text, response_text).

    The assistant role marker is the last token of ``prompt_text`` — this
    boundary is what `label_masking` relies on (prompt tokens are masked,
    response tokens are trainable). BOS appears once at the very start of
    the prompt; EOS appears once at the very end of the response.
    """

    system_text = validated.get("system_text") or ""
    prompt_body = validated.get("prompt_text") or ""
    input_text = validated.get("input_text") or ""
    response_text = validated.get("response_text") or ""

    marker = template.language_markers.get(language, "") if template.insert_language_marker else ""

    parts = [template.bos_token, template.system_prefix]
    if system_text:
        parts.append(system_text)
    parts.append(template.user_prefix)
    if marker:
        parts.append(marker)
    parts.append(prompt_body)
    if input_text:
        parts.append(input_text)
    parts.append(template.assistant_prefix)
    prompt_rendered = " ".join(part for part in parts if part)
    response_rendered = f"{response_text} {template.eos_token}".strip()
    return prompt_rendered, response_rendered


def detect_special_token_collisions(text: str) -> list[str]:
    """Return which special tokens literally appear inside raw user/response text.

    This is reported (special_token_collision_count in the dataset profile),
    never silently stripped — records are not rewritten to hide the collision.
    """

    return [token for token in ALL_SPECIAL_TOKENS if token in text]
