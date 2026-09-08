"""Phase 18: Public Runtime Policy — Pure Policy Bounds & Resource Verification.

Provides pure, deterministic, side-effect-free policy functions for validating
request message bounds, timeout thresholds, retry rules, response token limits,
and resource safety boundaries.

Authoritative constraints (verified against repository baseline):
  - MAX_MESSAGE_LENGTH = 4000 characters (matching backend.models.public_chat)
  - Max Provider Timeout = 60.0 seconds
  - Max Retry Attempts = 0 (stateless per request; zero autonomous retry fan-out)
  - Max Response Token Limit = 4096 tokens
  - Max Conversation Window Turns = 50 turns

Critical invariants:
  ✅ Pure, side-effect-free functions.
  ✅ Deterministic evaluations.
  ❌ No database connections or migrations.
  ❌ No network calls or HTTP requests.
  ❌ No subprocesses, eval, or exec.
  ❌ No background tasks or daemons.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Authoritative repository boundary constants
AUTHORITATIVE_MAX_MESSAGE_LENGTH: int = 4000
MAX_PERMITTED_PROVIDER_TIMEOUT_SECONDS: float = 60.0
MAX_PERMITTED_RETRY_COUNT: int = 0  # No autonomous retry fan-out in public chat
MAX_PERMITTED_RESPONSE_TOKENS: int = 4096
MAX_CONVERSATION_WINDOW_TURNS: int = 50


@dataclass(frozen=True)
class RequestBoundsResult:
    is_valid: bool
    reason_code: str | None
    character_count: int
    max_permitted: int


@dataclass(frozen=True)
class PolicyEvaluationResult:
    is_permitted: bool
    policy_name: str
    reason_code: str | None
    details: dict[str, Any]


def validate_request_bounds(
    text: str | None,
    *,
    max_length: int = AUTHORITATIVE_MAX_MESSAGE_LENGTH,
) -> RequestBoundsResult:
    """Validate raw message text against size and non-empty bounds.

    Args:
        text: Raw user message string.
        max_length: Maximum permitted length in characters (default 4000).

    Returns:
        RequestBoundsResult with validation verdict and character count.
    """
    if text is None:
        return RequestBoundsResult(
            is_valid=False,
            reason_code="null_input",
            character_count=0,
            max_permitted=max_length,
        )

    length = len(text)
    stripped = text.strip()

    if not stripped:
        return RequestBoundsResult(
            is_valid=False,
            reason_code="blank_input",
            character_count=length,
            max_permitted=max_length,
        )

    if length > max_length:
        return RequestBoundsResult(
            is_valid=False,
            reason_code="input_exceeds_max_length",
            character_count=length,
            max_permitted=max_length,
        )

    return RequestBoundsResult(
        is_valid=True,
        reason_code=None,
        character_count=length,
        max_permitted=max_length,
    )


def evaluate_provider_timeout_policy(
    timeout_seconds: float | int,
    *,
    max_timeout: float = MAX_PERMITTED_PROVIDER_TIMEOUT_SECONDS,
) -> PolicyEvaluationResult:
    """Evaluate whether a provider/tool execution timeout configuration is within safety limits."""
    try:
        val = float(timeout_seconds)
    except (ValueError, TypeError):
        return PolicyEvaluationResult(
            is_permitted=False,
            policy_name="provider_timeout",
            reason_code="invalid_timeout_value",
            details={"requested": timeout_seconds, "max_permitted": max_timeout},
        )

    if val <= 0.0:
        return PolicyEvaluationResult(
            is_permitted=False,
            policy_name="provider_timeout",
            reason_code="non_positive_timeout",
            details={"requested": val, "max_permitted": max_timeout},
        )

    if val > max_timeout:
        return PolicyEvaluationResult(
            is_permitted=False,
            policy_name="provider_timeout",
            reason_code="timeout_exceeds_max_permitted",
            details={"requested": val, "max_permitted": max_timeout},
        )

    return PolicyEvaluationResult(
        is_permitted=True,
        policy_name="provider_timeout",
        reason_code=None,
        details={"requested": val, "max_permitted": max_timeout},
    )


def evaluate_retry_policy(
    retry_count: int,
    *,
    max_retries: int = MAX_PERMITTED_RETRY_COUNT,
) -> PolicyEvaluationResult:
    """Evaluate whether a request retry count adheres to the zero-autonomous-retry policy."""
    if not isinstance(retry_count, int):
        return PolicyEvaluationResult(
            is_permitted=False,
            policy_name="retry_policy",
            reason_code="invalid_retry_type",
            details={"retry_count": retry_count, "max_permitted": max_retries},
        )

    if retry_count < 0:
        return PolicyEvaluationResult(
            is_permitted=False,
            policy_name="retry_policy",
            reason_code="negative_retry_count",
            details={"retry_count": retry_count, "max_permitted": max_retries},
        )

    if retry_count > max_retries:
        return PolicyEvaluationResult(
            is_permitted=False,
            policy_name="retry_policy",
            reason_code="retry_count_exceeds_policy_limit",
            details={"retry_count": retry_count, "max_permitted": max_retries},
        )

    return PolicyEvaluationResult(
        is_permitted=True,
        policy_name="retry_policy",
        reason_code=None,
        details={"retry_count": retry_count, "max_permitted": max_retries},
    )


def evaluate_response_size_limits(
    max_tokens: int | None,
    *,
    limit_cap: int = MAX_PERMITTED_RESPONSE_TOKENS,
) -> PolicyEvaluationResult:
    """Evaluate whether requested response token generation limits are within safety bounds."""
    if max_tokens is None:
        return PolicyEvaluationResult(
            is_permitted=True,
            policy_name="response_size_limit",
            reason_code=None,
            details={"requested_max_tokens": None, "default_cap": limit_cap},
        )

    if not isinstance(max_tokens, int) or max_tokens <= 0:
        return PolicyEvaluationResult(
            is_permitted=False,
            policy_name="response_size_limit",
            reason_code="invalid_max_tokens_value",
            details={"requested_max_tokens": max_tokens, "limit_cap": limit_cap},
        )

    if max_tokens > limit_cap:
        return PolicyEvaluationResult(
            is_permitted=False,
            policy_name="response_size_limit",
            reason_code="max_tokens_exceeds_safety_cap",
            details={"requested_max_tokens": max_tokens, "limit_cap": limit_cap},
        )

    return PolicyEvaluationResult(
        is_permitted=True,
        policy_name="response_size_limit",
        reason_code=None,
        details={"requested_max_tokens": max_tokens, "limit_cap": limit_cap},
    )


def is_request_within_resource_limits(
    text: str | None,
    conversation_turn_count: int = 0,
) -> PolicyEvaluationResult:
    """Composite pure check evaluating whether input length and turn count are within resource boundaries."""
    bounds = validate_request_bounds(text)
    if not bounds.is_valid:
        return PolicyEvaluationResult(
            is_permitted=False,
            policy_name="resource_limits",
            reason_code=bounds.reason_code,
            details={"character_count": bounds.character_count, "turn_count": conversation_turn_count},
        )

    if not isinstance(conversation_turn_count, int) or conversation_turn_count < 0:
        return PolicyEvaluationResult(
            is_permitted=False,
            policy_name="resource_limits",
            reason_code="invalid_turn_count",
            details={"character_count": bounds.character_count, "turn_count": conversation_turn_count},
        )

    if conversation_turn_count > MAX_CONVERSATION_WINDOW_TURNS:
        return PolicyEvaluationResult(
            is_permitted=False,
            policy_name="resource_limits",
            reason_code="conversation_turns_exceed_max_window",
            details={"character_count": bounds.character_count, "turn_count": conversation_turn_count},
        )

    return PolicyEvaluationResult(
        is_permitted=True,
        policy_name="resource_limits",
        reason_code=None,
        details={"character_count": bounds.character_count, "turn_count": conversation_turn_count},
    )


__all__ = [
    "AUTHORITATIVE_MAX_MESSAGE_LENGTH",
    "MAX_CONVERSATION_WINDOW_TURNS",
    "MAX_PERMITTED_PROVIDER_TIMEOUT_SECONDS",
    "MAX_PERMITTED_RESPONSE_TOKENS",
    "MAX_PERMITTED_RETRY_COUNT",
    "PolicyEvaluationResult",
    "RequestBoundsResult",
    "evaluate_provider_timeout_policy",
    "evaluate_response_size_limits",
    "evaluate_retry_policy",
    "is_request_within_resource_limits",
    "validate_request_bounds",
]
