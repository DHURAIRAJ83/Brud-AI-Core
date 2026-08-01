"""Minimal live public-chat output safety gate (Step 7). Reuses
existing detectors entirely -- no new pattern lists:

- `core_model.model_evaluation.refusal_checks.detect_harmful_details()`
  for unsafe operational detail.
- `core_model.corpus.secret_detection.detect_secrets()` for secret and
  private-path leakage (it already covers absolute paths).
- `core_model.corpus.pii_detection.detect_pii()` for PII leakage.
- `InferenceRuntimeService.run_generation()`'s own already-computed
  `prompt_leakage`/`role_token_leakage` flags for system-prompt
  leakage (passed in, not recomputed here).

Malicious retrieved-content influence is mitigated upstream, at
context-assembly time, by `core_model.conversation.injection_guard
.assess_context_item_injection()` (already wired into
`ChatOrchestrationService`) -- a flagged/quarantined chunk never
reaches generation in the first place, so this gate does not
re-implement that check.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core_model.corpus.pii_detection import detect_pii
from core_model.corpus.secret_detection import detect_secrets
from core_model.model_evaluation.refusal_checks import detect_harmful_details


@dataclass(frozen=True)
class OutputSafetyDecision:
    passed: bool
    blocked_reasons: tuple[str, ...] = field(default_factory=tuple)


def evaluate_output_safety(
    answer_text: str, *, prompt_leakage: bool = False, role_token_leakage: bool = False
) -> OutputSafetyDecision:
    reasons: list[str] = []

    if prompt_leakage:
        reasons.append("system_prompt_leakage")
    if role_token_leakage:
        reasons.append("role_token_leakage")

    secrets = detect_secrets(answer_text)
    if secrets["status"] == "blocked":
        reasons.append("secret_exposure")

    pii = detect_pii(answer_text)
    if pii["total_findings"] > 0:
        reasons.append("pii_leakage")

    harmful = detect_harmful_details(answer_text)
    if harmful["harmful_details_present"]:
        reasons.append("unsafe_operational_detail")

    return OutputSafetyDecision(passed=not reasons, blocked_reasons=tuple(reasons))


__all__ = ["OutputSafetyDecision", "evaluate_output_safety"]
