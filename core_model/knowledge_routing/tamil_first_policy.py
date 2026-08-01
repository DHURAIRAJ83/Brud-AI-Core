"""Tamil-first policy check (Step 11) -- a cross-cutting validator over
the already-recommended execution route, not a new classification
layer.

Tamil-first means: Tamil grammar/meaning/orthography/translation
questions should prioritize `core_model` (the base model's own Tamil
language competence), never routed elsewhere merely because a web/RAG
source happens to exist. It does NOT mean every Tamil-language request
defaults to `core_model` -- a Tamil current-affairs question must still
route to `trusted_web` because of its *freshness*, not be forced to
`core_model` merely because of its *language*. This module's
`language_first_policy_violation` detector exists to catch exactly that
failure mode if it ever occurs (a bug indicator, not a policy the
recommenders should ever intentionally trigger).
"""

from __future__ import annotations

from dataclasses import dataclass

from core_model.knowledge_routing import POLICY_VERSION

_TAMIL_LANGUAGE_DOMAINS = frozenset({"tamil_language"})
_VOLATILE_FRESHNESS = frozenset({"real_time", "time_sensitive"})


@dataclass(frozen=True)
class TamilFirstCheckResult:
    policy_applied: bool
    violation: bool
    reason_codes: tuple[str, ...]
    policy_version: str


def check_tamil_first_policy(
    *,
    language_category: str,
    domain: str,
    freshness: str,
    execution_route: str,
) -> TamilFirstCheckResult:
    is_tamil = language_category in ("ta", "mixed")

    violation = (
        is_tamil
        and execution_route == "core_model"
        and freshness in _VOLATILE_FRESHNESS
        and domain not in _TAMIL_LANGUAGE_DOMAINS
    )
    if violation:
        return TamilFirstCheckResult(
            policy_applied=False,
            violation=True,
            reason_codes=("TAMIL_FIRST_POLICY_VIOLATION",),
            policy_version=POLICY_VERSION,
        )

    applied = is_tamil and domain in _TAMIL_LANGUAGE_DOMAINS and execution_route == "core_model"
    if applied:
        return TamilFirstCheckResult(
            policy_applied=True,
            violation=False,
            reason_codes=("TAMIL_FIRST_PRIORITY_APPLIED",),
            policy_version=POLICY_VERSION,
        )

    return TamilFirstCheckResult(
        policy_applied=False,
        violation=False,
        reason_codes=(),
        policy_version=POLICY_VERSION,
    )


__all__ = ["TamilFirstCheckResult", "check_tamil_first_policy"]
