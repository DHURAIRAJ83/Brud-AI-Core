"""Evaluation suite definition and checksum.

Once a suite is activated, its fixtures, thresholds, and generation
configuration must become immutable, and the suite checksum must remain
stable — this module's ``suite_checksum`` is what the service layer
persists and re-verifies for that guarantee.
"""

from __future__ import annotations

import hashlib

from backend.core.json_utils import dumps_json

REQUIRED_SUITE_FIELDS = (
    "name", "version", "description", "supported_languages",
    "generation_configuration", "automated_thresholds", "human_review_rubric",
    "readiness_gate_configuration",
)


def suite_checksum(suite: dict) -> str:
    canonical = {field: suite.get(field) for field in REQUIRED_SUITE_FIELDS}
    return hashlib.sha256(dumps_json(canonical).encode("utf-8")).hexdigest()


def generation_config_checksum(generation_configuration: dict) -> str:
    return hashlib.sha256(dumps_json(generation_configuration).encode("utf-8")).hexdigest()


def validate_generation_policy(generation_configuration: dict) -> list[str]:
    """Enforce the required bounded-generation policy — reject any suite
    that tries to enable sampling, streaming, or unbounded generation."""

    violations = []
    if generation_configuration.get("temperature", 0.0) not in (0.0, None):
        violations.append("temperature_must_be_disabled")
    if generation_configuration.get("sampling_enabled", False):
        violations.append("sampling_must_be_disabled")
    if generation_configuration.get("streaming", False):
        violations.append("streaming_not_allowed")
    if generation_configuration.get("max_new_tokens", 0) <= 0:
        violations.append("max_new_tokens_must_be_bounded_and_positive")
    if generation_configuration.get("max_new_tokens", 0) > 256:
        violations.append("max_new_tokens_exceeds_safety_ceiling")
    return violations
