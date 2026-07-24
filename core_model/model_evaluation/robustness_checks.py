"""Bounded robustness checks: compares a base fixture's generation against a
perturbed variant's generation for stability of language, format, and
repetition — not adversarial robustness. A model that changes its answer
completely for a whitespace/capitalization/spelling variant is flagged as
unstable; this is a narrow, honest signal, not a security guarantee.
"""

from __future__ import annotations

from core_model.model_evaluation.language_evaluation import script_ratios


def compare_language_stability(
    base_text: str, perturbed_text: str, *, max_ratio_delta: float = 0.3,
) -> dict:
    base_ratios = script_ratios(base_text)
    perturbed_ratios = script_ratios(perturbed_text)
    deltas = {
        key: abs(base_ratios[key] - perturbed_ratios[key]) for key in base_ratios
    }
    stable = all(delta <= max_ratio_delta for delta in deltas.values())
    status = "pass" if stable else "warning"
    return {"check": "language_stability", "status": status, "deltas": deltas}


def compare_format_stability(base_checks: dict, perturbed_checks: dict) -> dict:
    base_status = base_checks.get("status")
    perturbed_status = perturbed_checks.get("status")
    stable = base_status == perturbed_status
    return {
        "check": "format_stability", "status": "pass" if stable else "warning",
        "base_status": base_status, "perturbed_status": perturbed_status,
    }


def compare_repetition_stability(base_degeneration: dict, perturbed_degeneration: dict) -> dict:
    base_repeated = base_degeneration.get("repetition", {}).get("status") != "pass"
    perturbed_repeated = perturbed_degeneration.get("repetition", {}).get("status") != "pass"
    collapsed = (not base_repeated) and perturbed_repeated
    return {
        "check": "repetition_stability", "status": "fail" if collapsed else "pass",
        "perturbation_triggered_repetition": collapsed,
    }


def evaluate_robustness_pair(
    *, base_text: str, perturbed_text: str, base_format_check: dict, perturbed_format_check: dict,
    base_degeneration: dict, perturbed_degeneration: dict,
) -> dict:
    return {
        "language_stability": compare_language_stability(base_text, perturbed_text),
        "format_stability": compare_format_stability(base_format_check, perturbed_format_check),
        "repetition_stability": compare_repetition_stability(
            base_degeneration, perturbed_degeneration
        ),
    }
