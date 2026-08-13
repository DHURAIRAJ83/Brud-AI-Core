"""MB-04A: selects and budgets what goes into the prompt's Knowledge
section -- Primary always included, Supporting only if budget
remains, Optional only if space still remains after both. Workflow
and Rules (disclaimers) come straight from the Response Plan MB-03
already produced; nothing here re-derives or overrides MB-03's own
decisions, it only formats and budgets them.

Note: MB-03's final Response Plan contract intentionally exposes only
`validated_knowledge.primary` / `.supporting` (see MB-03's own
"the future model must receive only Validated Context/Knowledge/
Workflow/Response Plan -- nothing else" rule) -- there is no
"optional" tier in the Response Plan today, so `optional_texts` will
realistically always be empty unless a future phase changes that
contract. The allocation logic below still honors "ignore Optional
unless space allows" structurally, for whenever that becomes true.
"""

from __future__ import annotations

from typing import Any

from core_model.mini_brain.prompting.knowledge_compressor import compress_knowledge

DEFAULT_KNOWLEDGE_BUDGET_CHARS = 900


def build_context(
    response_plan: dict[str, Any],
    *,
    primary_texts: list[str],
    supporting_texts: list[str],
    optional_texts: list[str] | None = None,
    total_budget_chars: int = DEFAULT_KNOWLEDGE_BUDGET_CHARS,
) -> dict[str, Any]:
    optional_texts = optional_texts or []

    compressed_primary = compress_knowledge(primary_texts, max_chars=total_budget_chars)
    used = sum(len(t) for t in compressed_primary)

    remaining = max(0, total_budget_chars - used)
    compressed_supporting = compress_knowledge(supporting_texts, max_chars=remaining) if remaining else []
    used += sum(len(t) for t in compressed_supporting)

    remaining = max(0, total_budget_chars - used)
    compressed_optional = compress_knowledge(optional_texts, max_chars=remaining) if remaining else []
    used += sum(len(t) for t in compressed_optional)

    workflow = response_plan.get("validated_workflow") or {}
    workflow_lines: list[str] = []
    if workflow.get("current_step"):
        workflow_lines.append(f"Current step: {workflow['current_step']}")
    if workflow.get("next_steps"):
        workflow_lines.append(f"Next steps: {', '.join(workflow['next_steps'])}")
    if workflow.get("dependencies"):
        workflow_lines.append(f"Dependencies: {', '.join(workflow['dependencies'])}")

    rules_lines = list(response_plan.get("disclaimers") or [])

    return {
        "primary": compressed_primary,
        "supporting": compressed_supporting,
        "optional": compressed_optional,
        "workflow_lines": workflow_lines,
        "rules_lines": rules_lines,
        "total_chars_used": used,
        "total_budget_chars": total_budget_chars,
    }
