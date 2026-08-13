"""MB-04C: Model Capability Optimization -- the only impure module in
this phase (wall-clock timing plus calling already-existing services).

Composes `MiniBrainPromptOptimizationService` (MB-04A) and reuses
`MiniBrainInMemoryModelLoader.generate_response()` (MB-04) exactly
as any other caller would -- zero edits to either file, zero
duplicated Runtime logic. Also reuses two pure MB-04B functions by
import (`detect_echo`, `validate_consistency`) rather than
re-implementing echo/forbidden-claim detection a third time.

The ONE retry, if triggered, is a single `if` block -- not a loop --
so a second retry is structurally impossible, not merely policy.
"""

from __future__ import annotations

import time
from typing import Any

from backend.services.mini_brain_prompt_optimization_service import MiniBrainPromptOptimizationService
from core_model.mini_brain.capability.capability_selector import select_capability_category
from core_model.mini_brain.capability.generation_strategy import select_strategy
from core_model.mini_brain.capability.model_profiles import get_profile, list_profiles
from core_model.mini_brain.capability.output_length_controller import evaluate_output_length
from core_model.mini_brain.capability.retry_strategy import should_retry
from core_model.mini_brain.capability.stability_checker import check_stability
from core_model.mini_brain.quality.consistency_validator import validate_consistency
from core_model.mini_brain.quality.echo_detector import detect_echo


class MiniBrainCapabilityService:
    def __init__(self, prompt_optimization_service: MiniBrainPromptOptimizationService) -> None:
        self.prompt_optimization_service = prompt_optimization_service

    def _current_profile(self) -> dict[str, Any]:
        status = self.prompt_optimization_service.runtime_manager.status()
        current_model = status.get("current_model")
        if current_model is None:
            return get_profile(None, None)
        return get_profile(current_model.get("name"), current_model.get("quantization"))

    def analyze(self, question: str) -> dict[str, Any]:
        """Pure-relative-to-runtime: builds the prompt via MB-04A
        (unmodified), determines category/strategy/model profile.
        Never calls the Runtime -- no generation happens here."""

        built = self.prompt_optimization_service.build_optimized_prompt(question)
        response_plan = built["response_plan"]
        knowledge = response_plan.get("validated_knowledge", {}) or {}
        has_knowledge = bool(knowledge.get("primary") or knowledge.get("supporting"))

        category = select_capability_category(
            intent=response_plan.get("intent", "unknown"), question=question, has_knowledge=has_knowledge,
        )
        strategy = select_strategy(category=category, question_type=response_plan.get("question_type", "general"))
        profile = self._current_profile()

        return {"built": built, "category": category, "strategy": strategy, "profile": profile}

    def generate(self, question: str, *, timeout_seconds: float = 90.0) -> dict[str, Any]:
        started = time.perf_counter()
        analysis = self.analyze(question)
        built = analysis["built"]
        strategy = analysis["strategy"]
        profile = analysis["profile"]
        response_plan = built["response_plan"]

        max_tokens = min(strategy["max_tokens"], profile["response_limits"]["max_tokens_ceiling"])
        prompt_with_directive = built["prompt"]
        if strategy.get("directive"):
            prompt_with_directive = f"{built['prompt']}\n\n{strategy['directive']}"

        result = self.prompt_optimization_service.runtime_manager.generate_response(
            response_plan, max_tokens=max_tokens, timeout_seconds=timeout_seconds,
            prebuilt_prompt=prompt_with_directive,
        )

        length_eval = evaluate_output_length(
            result["text"], stop_reason=result["generation_stats"]["stop_reason"],
            target_max_tokens=max_tokens, tokens_generated=result["generation_stats"]["tokens_generated"],
        )
        echo = detect_echo(result["text"], prompt_text=prompt_with_directive)
        blocked = response_plan.get("suggested_response_type") == "training_boundary_notice"
        consistency = validate_consistency(response_text=result["text"], response_plan=response_plan)
        forbidden_claim_detected = any("forbidden_claim" in issue for issue in consistency["issues"])

        retry_decision = should_retry(
            length_issues=length_eval["issues"], echo_severity=echo["severity"],
            blocked=blocked, forbidden_claim_detected=forbidden_claim_detected,
        )

        retried = False
        stability = None
        final_result = result
        final_length_eval = length_eval
        final_echo = echo

        if retry_decision["retry"]:
            retry_max_tokens = max_tokens
            if retry_decision.get("bump_tokens"):
                retry_max_tokens = min(max_tokens * 2, profile["response_limits"]["max_tokens_ceiling"])

            retry_result = self.prompt_optimization_service.runtime_manager.generate_response(
                response_plan, max_tokens=retry_max_tokens, timeout_seconds=timeout_seconds,
                prebuilt_prompt=prompt_with_directive,
            )
            retried = True
            stability = check_stability(
                first_text=result["text"], retry_text=retry_result["text"], prompt_text=prompt_with_directive,
            )

            retry_length_eval = evaluate_output_length(
                retry_result["text"], stop_reason=retry_result["generation_stats"]["stop_reason"],
                target_max_tokens=retry_max_tokens, tokens_generated=retry_result["generation_stats"]["tokens_generated"],
            )
            retry_echo = detect_echo(retry_result["text"], prompt_text=prompt_with_directive)

            # Prefer the retry only if it is no worse than the first
            # attempt -- never blindly trust the second try.
            if len(retry_length_eval["issues"]) <= len(length_eval["issues"]) and retry_echo["severity"] != "dominant":
                final_result = retry_result
                final_length_eval = retry_length_eval
                final_echo = retry_echo

        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)

        return {
            "question": question,
            "category": analysis["category"],
            "strategy": strategy,
            "profile": profile,
            "max_tokens_used": max_tokens,
            "response": final_result,
            "output_length": final_length_eval,
            "echo": final_echo,
            "retry": {"attempted": retried, "decision": retry_decision},
            "stability": stability,
            "warnings": self._build_warnings(final_length_eval, final_echo, retry_decision, profile),
            "generation_time_ms": elapsed_ms,
        }

    @staticmethod
    def _build_warnings(length_eval, echo, retry_decision, profile) -> list[str]:
        warnings: list[str] = []
        if length_eval["issues"]:
            warnings.append(f"output_length_issues: {length_eval['issues']}")
        if echo["severity"] != "none":
            warnings.append(f"echo_severity: {echo['severity']}")
        if not profile.get("verified", False):
            warnings.append("model_profile_unverified_estimates_only")
        if retry_decision["retry"] and retry_decision["reason"] in (
            "blocked_response_never_retried", "forbidden_claim_detected_never_retried",
        ):
            warnings.append(retry_decision["reason"])
        return warnings

    def profile_for(self, model_name: str | None = None, quantization: str | None = None) -> dict[str, Any]:
        if model_name is None:
            return self._current_profile()
        return get_profile(model_name, quantization)

    def diagnostics(self) -> dict[str, Any]:
        return {
            "pipeline_stages": [
                "model_profile_manager", "capability_selector", "generation_strategy",
                "output_length_controller", "retry_strategy", "stability_checker",
            ],
            "known_profiles": list(list_profiles().keys()),
            "reuses_from_mb04b": ["echo_detector (unmodified)", "consistency_validator (unmodified)"],
            "database_tables": 0,
            "ai_model_used": False,
            "max_retries": 1,
        }
