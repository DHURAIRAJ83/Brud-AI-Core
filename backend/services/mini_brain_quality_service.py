"""MB-04B: Response Quality Engine -- the only impure module in this
phase (wall-clock timing is its one piece of real I/O beyond calling
already-existing services).

Composes `MiniBrainPromptOptimizationService` (MB-04A) as a black box
-- calls its existing PUBLIC methods (`build_optimized_prompt`,
`runtime_manager`) exactly as any other caller would, imports nothing
private, and makes ZERO edits to any MB-04A file. This is the
deliberate design choice that lets MB-04B genuinely "sit after MB-04A
generation and before the final response is returned" without
touching MB-04A's Prompt Builder logic at all: the new service simply
calls the old one, then runs the quality pipeline on what comes back.

Note: this composition intentionally does NOT reuse MB-04A's own
one-rebuild-on-language-mismatch retry (`optimize_and_generate`)
-- that remains an MB-04A-only capability, still available unchanged
via its own `/prompt-optimization/generate` route. MB-04B performs a
single generation pass and then reports/cleans; it does not retry
generation itself, which would start to blur into "new architecture"
this phase is explicitly not meant to be.
"""

from __future__ import annotations

import time
from typing import Any

from backend.services.mini_brain_prompt_optimization_service import MiniBrainPromptOptimizationService
from core_model.mini_brain.prompting.context_builder import DEFAULT_KNOWLEDGE_BUDGET_CHARS
from core_model.mini_brain.quality.consistency_validator import validate_consistency
from core_model.mini_brain.quality.echo_cleaner import clean_echo_iteratively
from core_model.mini_brain.quality.echo_detector import detect_echo
from core_model.mini_brain.quality.mixed_language_resolver import resolve_response_language
from core_model.mini_brain.quality.quality_score import compute_quality_score
from core_model.mini_brain.quality.response_formatter import format_response_text, validate_formatting
from core_model.mini_brain.quality.tamil_fluency_validator import validate_tamil_fluency


class MiniBrainQualityService:
    def __init__(self, prompt_optimization_service: MiniBrainPromptOptimizationService) -> None:
        self.prompt_optimization_service = prompt_optimization_service

    def check(
        self,
        response_text: str,
        *,
        prompt_text: str = "",
        expected_output_language: str = "english",
        response_plan: dict[str, Any] | None = None,
        final_response: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        response_plan = response_plan or {}
        actions_performed: list[str] = []

        echo = detect_echo(response_text, prompt_text=prompt_text)
        cleaning = clean_echo_iteratively(response_text, prompt_text=prompt_text)
        if cleaning["insufficient_after_cleaning"]:
            # Nothing meaningful survives removing the echo -- keep the
            # original text rather than returning an empty response,
            # but flag this plainly so a caller scanning only
            # actions_performed still sees what happened.
            actions_performed.append("echo_removal_insufficient_original_text_retained")
            working_text = response_text
        elif cleaning["removed"]:
            actions_performed.append("echo_removed")
            working_text = cleaning["cleaned_text"]
        else:
            working_text = response_text

        language = resolve_response_language(working_text, expected_output_language=expected_output_language)

        tamil_result = None
        if expected_output_language == "tamil":
            tamil_result = validate_tamil_fluency(working_text)

        formatting_diagnostics = validate_formatting(working_text)
        formatted = format_response_text(working_text)
        if formatted["changed"]:
            actions_performed.append("formatting_applied")

        consistency = validate_consistency(
            response_text=working_text, response_plan=response_plan, final_response=final_response,
        )

        score = compute_quality_score(
            echo_result=echo, language_result=language, tamil_result=tamil_result,
            formatting_result=formatting_diagnostics, consistency_result=consistency,
        )

        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)

        return {
            "original_text": response_text,
            "final_text": formatted["formatted_text"],
            "echo": echo,
            "echo_cleaning": cleaning,
            "language": language,
            "tamil_fluency": tamil_result,
            "formatting": formatting_diagnostics,
            "consistency": consistency,
            "quality_score": score,
            "actions_performed": actions_performed,
            "processing_time_ms": elapsed_ms,
        }

    def validate_only(
        self,
        response_text: str,
        *,
        prompt_text: str = "",
        expected_output_language: str = "english",
        response_plan: dict[str, Any] | None = None,
        final_response: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Read-only counterpart to `check()` -- runs every validator
        but never calls the Echo Cleaner or the Response Formatter, so
        the input text is never touched. Matches the "/validate"
        endpoint's narrower diagnose-only contract."""

        started = time.perf_counter()
        response_plan = response_plan or {}

        echo = detect_echo(response_text, prompt_text=prompt_text)
        language = resolve_response_language(response_text, expected_output_language=expected_output_language)
        tamil_result = validate_tamil_fluency(response_text) if expected_output_language == "tamil" else None
        formatting_diagnostics = validate_formatting(response_text)
        consistency = validate_consistency(
            response_text=response_text, response_plan=response_plan, final_response=final_response,
        )
        score = compute_quality_score(
            echo_result=echo, language_result=language, tamil_result=tamil_result,
            formatting_result=formatting_diagnostics, consistency_result=consistency,
        )

        return {
            "echo": echo,
            "language": language,
            "tamil_fluency": tamil_result,
            "formatting": formatting_diagnostics,
            "consistency": consistency,
            "quality_score": score,
            "processing_time_ms": round((time.perf_counter() - started) * 1000, 3),
        }

    def generate_and_check(
        self,
        question: str,
        *,
        max_tokens: int = 256,
        timeout_seconds: float = 90.0,
        knowledge_budget_chars: int = DEFAULT_KNOWLEDGE_BUDGET_CHARS,
    ) -> dict[str, Any]:
        """The real, working "sits after generation, before final
        response" composition: calls MB-04A's own `build_optimized_prompt`
        and the Runtime Manager's own `generate_response` -- both
        pre-existing PUBLIC methods, called exactly as any other
        caller would -- then runs the full quality pipeline on the
        result."""

        built = self.prompt_optimization_service.build_optimized_prompt(
            question, knowledge_budget_chars=knowledge_budget_chars,
        )
        result = self.prompt_optimization_service.runtime_manager.generate_response(
            built["response_plan"], max_tokens=max_tokens, timeout_seconds=timeout_seconds,
            prebuilt_prompt=built["prompt"],
        )
        quality = self.check(
            result["text"], prompt_text=built["prompt"], expected_output_language=built["output_language"],
            response_plan=built["response_plan"], final_response=result,
        )

        return {
            "question": question,
            "response_plan": built["response_plan"],
            "prompt_used": built["prompt"],
            "raw_response": result,
            "quality": quality,
            "final_response_text": quality["final_text"],
        }

    def diagnostics(self) -> dict[str, Any]:
        """Stateless pipeline description -- no process-wide state
        exists to report on (unlike the Runtime Manager), so this
        describes the pipeline's own configuration/capabilities."""

        return {
            "pipeline_stages": [
                "echo_detector", "echo_cleaner", "mixed_language_resolver",
                "tamil_fluency_validator", "response_formatter", "consistency_validator",
                "quality_score",
            ],
            "reuses_from_mb04a": ["language_detector (unmodified)"],
            "database_tables": 0,
            "ai_model_used": False,
        }
