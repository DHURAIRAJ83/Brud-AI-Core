"""MB-04A: Prompt & Context Optimization -- the only impure module in
this phase. Orchestrates: MB-03's unchanged `MiniBrainIntelligenceService`
-> the new deterministic prompting pipeline (language detection,
Tanglish normalization for internal grounding only, knowledge
compression, template selection, structured prompt building) -> the
unchanged MB-04 `MiniBrainInMemoryModelLoader.generate_response()`,
using its new-but-additive `prebuilt_prompt` parameter -> one
deterministic rebuild-and-retry if the Response Validator finds the
language doesn't match.

Read-only against Knowledge Core (via `MiniBrainKnowledgeRepository`,
same repository MB-03 already reads) to resolve the Response Plan's
knowledge item TITLES into their full description TEXT for
compression -- the Response Plan itself only ever carries titles, by
MB-03's own deliberate design.
"""

from __future__ import annotations

import time
from typing import Any

from backend.core.config import Settings
from backend.database.repositories.mini_brain_knowledge import MiniBrainKnowledgeRepository, public_row
from backend.services.mini_brain_intelligence_service import MiniBrainIntelligenceService
from backend.services.mini_brain_runtime_manager_service import MiniBrainInMemoryModelLoader
from core_model.mini_brain.prompting.context_builder import DEFAULT_KNOWLEDGE_BUDGET_CHARS, build_context
from core_model.mini_brain.prompting.language_detector import detect_language, resolve_output_language
from core_model.mini_brain.prompting.prompt_builder import build_prompt, rebuild_with_stronger_language_directive
from core_model.mini_brain.prompting.prompt_templates import select_template_category, template_text
from core_model.mini_brain.prompting.response_validator import validate_response
from core_model.mini_brain.prompting.tanglish_normalizer import normalize_tanglish


class MiniBrainPromptOptimizationService:
    def __init__(
        self,
        knowledge_repository: MiniBrainKnowledgeRepository,
        intelligence_service: MiniBrainIntelligenceService,
        runtime_manager: MiniBrainInMemoryModelLoader,
        settings: Settings,
    ) -> None:
        self.knowledge_repository = knowledge_repository
        self.intelligence_service = intelligence_service
        self.runtime_manager = runtime_manager
        self.settings = settings

    def _resolve_item_texts(self, titles: list[str]) -> list[str]:
        if not titles:
            return []
        with self.knowledge_repository.transaction() as connection:
            rows = self.knowledge_repository.all_items(connection)
            by_title = {row["title"]: public_row(row) for row in rows}
        texts = []
        for title in titles:
            item = by_title.get(title)
            if item and item.get("description"):
                texts.append(f"{title}: {item['description']}")
            else:
                texts.append(title)
        return texts

    def language_detect(self, question: str) -> dict[str, Any]:
        analysis = detect_language(question)
        return {
            **analysis,
            "resolved_output_language": resolve_output_language(analysis),
            "tanglish_normalized_internal": normalize_tanglish(question) if analysis["language"] in ("tanglish", "mixed") else None,
        }

    def build_optimized_prompt(self, question: str, *, knowledge_budget_chars: int = DEFAULT_KNOWLEDGE_BUDGET_CHARS) -> dict[str, Any]:
        """Runs the deterministic pipeline up to (but not including)
        model generation -- MB-03 analyze() + language + template +
        context + prompt text. Used by both `optimize_and_generate`
        and the `/compare` benchmark endpoint."""

        response_plan = self.intelligence_service.analyze(question)["response_plan"]

        language_analysis = detect_language(question)
        output_language = resolve_output_language(language_analysis)

        # Tanglish/mixed input is normalized to Tamil internally ONLY
        # to strengthen the language signal already computed above --
        # normalized text is never sent to the model or shown to the
        # user, per MB-04A's own instruction.
        _ = normalize_tanglish(question) if language_analysis["language"] in ("tanglish", "mixed") else None

        template_category = select_template_category(
            intent=response_plan["intent"], question_type=response_plan.get("question_type", "general"),
            question=question,
        )

        primary_texts = self._resolve_item_texts(response_plan["validated_knowledge"]["primary"])
        supporting_texts = self._resolve_item_texts(response_plan["validated_knowledge"]["supporting"])
        context = build_context(
            response_plan, primary_texts=primary_texts, supporting_texts=supporting_texts,
            total_budget_chars=knowledge_budget_chars,
        )

        prompt = build_prompt(
            question=question, template_text=template_text(template_category), context=context,
            output_language=output_language, confidence_band=response_plan["confidence_band"],
            intent=response_plan["intent"],
        )

        return {
            "response_plan": response_plan,
            "language_analysis": language_analysis,
            "output_language": output_language,
            "template_category": template_category,
            "context": context,
            "prompt": prompt,
        }

    def optimize_and_generate(
        self, question: str, *, max_tokens: int = 256, timeout_seconds: float = 90.0,
        knowledge_budget_chars: int = DEFAULT_KNOWLEDGE_BUDGET_CHARS,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        built = self.build_optimized_prompt(question, knowledge_budget_chars=knowledge_budget_chars)

        result = self.runtime_manager.generate_response(
            built["response_plan"], max_tokens=max_tokens, timeout_seconds=timeout_seconds,
            prebuilt_prompt=built["prompt"],
        )
        validation = validate_response(
            result["text"], expected_output_language=built["output_language"],
            confidence_band=built["response_plan"]["confidence_band"],
        )

        rebuilt = False
        final_prompt = built["prompt"]
        if not validation["passed"] and "language_mismatch" in " ".join(validation["issues"]):
            final_prompt = rebuild_with_stronger_language_directive(
                built["prompt"], output_language=built["output_language"],
            )
            result = self.runtime_manager.generate_response(
                built["response_plan"], max_tokens=max_tokens, timeout_seconds=timeout_seconds,
                prebuilt_prompt=final_prompt,
            )
            validation = validate_response(
                result["text"], expected_output_language=built["output_language"],
                confidence_band=built["response_plan"]["confidence_band"],
            )
            rebuilt = True

        return {
            "question": question,
            "language_analysis": built["language_analysis"],
            "output_language": built["output_language"],
            "template_category": built["template_category"],
            "prompt_used": final_prompt,
            "prompt_length_chars": len(final_prompt),
            "rebuilt": rebuilt,
            "response": result,
            "validation": validation,
            "total_seconds": round(time.perf_counter() - started, 3),
        }
