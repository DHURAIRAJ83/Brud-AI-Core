"""Versioned Brud instruction template definition and validation.

The template is a fixed single-exchange shape:
``<bos> <system> {system} <user> [<lang>] {prompt} [{input}] <assistant>``
as the prompt segment, followed by ``{response} <eos>`` as the response
segment. BOS appears exactly once (start of prompt), EOS exactly once (end
of response) — this is what guarantees no duplicate insertion.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field

from backend.core.json_utils import dumps_json

LANGUAGE_MARKERS = {"ta": "<ta>", "en": "<en>", "tgl": "<tgl>", "mixed": "<mixed>"}

REQUIRED_SPECIAL_TOKENS = (
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


@dataclass(frozen=True)
class InstructionTemplate:
    name: str
    version: str
    bos_token: str = "<bos>"
    eos_token: str = "<eos>"
    system_prefix: str = "<system>"
    user_prefix: str = "<user>"
    assistant_prefix: str = "<assistant>"
    insert_language_marker: bool = True
    language_markers: dict[str, str] = field(default_factory=lambda: dict(LANGUAGE_MARKERS))
    required_special_tokens: tuple[str, ...] = REQUIRED_SPECIAL_TOKENS


def _json_safe(value):
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    return value


def template_to_dict(template: InstructionTemplate) -> dict:
    return {key: _json_safe(value) for key, value in asdict(template).items()}


def template_from_dict(data: dict) -> InstructionTemplate:
    return InstructionTemplate(
        name=data["name"],
        version=data["version"],
        bos_token=data.get("bos_token", "<bos>"),
        eos_token=data.get("eos_token", "<eos>"),
        system_prefix=data.get("system_prefix", "<system>"),
        user_prefix=data.get("user_prefix", "<user>"),
        assistant_prefix=data.get("assistant_prefix", "<assistant>"),
        insert_language_marker=data.get("insert_language_marker", True),
        language_markers=data.get("language_markers", dict(LANGUAGE_MARKERS)),
        required_special_tokens=tuple(data.get("required_special_tokens", REQUIRED_SPECIAL_TOKENS)),
    )


def template_checksum(template: InstructionTemplate) -> str:
    return hashlib.sha256(dumps_json(template_to_dict(template)).encode("utf-8")).hexdigest()


def validate_template_against_tokenizer(
    template: InstructionTemplate, special_tokens: list[str]
) -> list[str]:
    """Check the template's required tokens against a tokenizer's *actual*
    persisted ``special_tokens_json`` — never the default Python constant,
    since a trained tokenizer's real token set may differ from it."""

    available = set(special_tokens)
    return [token for token in template.required_special_tokens if token not in available]
