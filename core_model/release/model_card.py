"""Versioned model-card generation and validation.

A model card is generated from already-registered, already-verified data
only — this module never invents a capability claim, and a card describing
an evaluation-blocked model as capable or production-ready must fail
validation.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

MODEL_CARD_SECTIONS = (
    "model_name", "version", "release_family", "summary", "architecture",
    "parameter_count", "context_length", "tokenizer", "training_datasets",
    "dataset_limitations", "base_training", "instruction_tuning", "evaluation",
    "supported_languages", "intended_uses", "out_of_scope_uses", "known_limitations",
    "safety_limitations", "resource_requirements", "licence_and_provenance",
    "artifact_checksums", "release_status", "deployment_eligibility",
    "public_chat_assignment_status",
)

REQUIRED_HONESTY_STATEMENTS = (
    "This model has not been proven to provide production-grade factual accuracy.",
    "Evaluation results are bounded by the size and quality of the available "
    "datasets and fixtures.",
    "Release registration does not automatically make the model available to "
    "the public chatbot.",
)

_UNSUPPORTED_CAPABILITY_PHRASES = (
    "production-ready", "production ready", "fully accurate", "guaranteed safe",
    "guaranteed accurate", "always correct", "no limitations", "perfectly safe",
)

_ABSOLUTE_PATH_PATTERN = re.compile(r"(?:^|\s)(/home/|/etc/|/usr/|/var/|[A-Za-z]:\\)\S+")
_SECRET_LIKE_PATTERN = re.compile(
    r"\b(api[_-]?key|password|secret|token)\s*[:=]\s*\S+", re.IGNORECASE
)


def render_model_card(fields: dict[str, Any]) -> str:
    """Deterministic markdown renderer — fixed section order, always
    including the three required honesty statements verbatim."""

    lines = [f"# Model Card — {fields.get('model_name', 'Unnamed model')}", ""]
    for section in MODEL_CARD_SECTIONS:
        title = section.replace("_", " ").title()
        lines.append(f"## {title}")
        lines.append(str(fields.get(section, "")).strip() or "_Not provided._")
        lines.append("")
    lines.append("## Honesty Statements")
    for statement in REQUIRED_HONESTY_STATEMENTS:
        lines.append(f"- {statement}")
    lines.append("")
    return "\n".join(lines)


def model_card_checksum(markdown: str) -> str:
    return hashlib.sha256(markdown.encode("utf-8")).hexdigest()


def parse_model_card_sections(markdown: str) -> dict[str, str]:
    """Parse a card rendered by ``render_model_card`` back into a
    section-name -> content dict — the single source of truth validation
    reads from, so validation always reflects what the card actually says,
    never a separately-supplied (and potentially stale or empty) dict."""

    sections: dict[str, str] = {}
    current: str | None = None
    buffer: list[str] = []
    title_to_section = {
        section.replace("_", " ").title(): section for section in MODEL_CARD_SECTIONS
    }
    for line in markdown.splitlines():
        if line.startswith("## "):
            if current is not None:
                sections[current] = "\n".join(buffer).strip()
            title = line[3:].strip()
            current = title_to_section.get(title)
            buffer = []
        elif current is not None:
            buffer.append(line)
    if current is not None:
        sections[current] = "\n".join(buffer).strip()
    return sections


def validate_model_card(
    markdown: str,
    *,
    evaluation_status: str | None,
    not_public_chat_ready: bool,
    actual_parameter_count: int,
    registered_parameter_count: int,
    checkpoint_checksum: str,
    registered_checkpoint_checksum: str,
) -> dict[str, Any]:
    issues: list[str] = []

    fields = parse_model_card_sections(markdown)
    for section in MODEL_CARD_SECTIONS:
        content = fields.get(section, "")
        if not content or content == "_Not provided._":
            issues.append(f"missing_required_section:{section}")

    if _ABSOLUTE_PATH_PATTERN.search(markdown):
        issues.append("contains_absolute_path")
    if _SECRET_LIKE_PATTERN.search(markdown):
        issues.append("contains_secret_like_content")

    normalized = markdown.lower()
    for phrase in _UNSUPPORTED_CAPABILITY_PHRASES:
        if phrase in normalized and evaluation_status != "eligible":
            issues.append(f"unsupported_capability_claim:{phrase}")

    for statement in REQUIRED_HONESTY_STATEMENTS:
        if statement not in markdown:
            issues.append("missing_honesty_statement")
            break

    if evaluation_status == "evaluation_blocked" and any(
        phrase in normalized for phrase in ("capable", "ready for users", "production")
    ):
        issues.append("misleading_readiness_claim_for_blocked_model")

    if actual_parameter_count != registered_parameter_count:
        issues.append("parameter_count_mismatch")
    if checkpoint_checksum != registered_checkpoint_checksum:
        issues.append("checkpoint_checksum_mismatch")

    chat_status_text = str(fields.get("public_chat_assignment_status", "")).lower()
    chat_status_accurate = any(
        marker in chat_status_text for marker in ("none", "not assigned", "placeholder")
    )
    if not_public_chat_ready and not chat_status_accurate:
        issues.append("public_chat_assignment_status_inaccurate")

    return {"valid": not issues, "issues": issues}
