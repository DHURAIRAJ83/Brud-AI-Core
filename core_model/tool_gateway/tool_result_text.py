"""Phase 20 Step 21 -- deterministic, template-based reply text for a
successful tool execution.

Deliberately **not** an LLM call, for the same reason
`web_answer_template.py` isn't one: the structured `output_payload`
from `DeterministicToolExecutionService` is already the authoritative
result (Step 21's own requirement -- "the model may format a short
natural-language explanation... but the structured result remains
authoritative"). A template mechanically guarantees the number in the
reply text is *exactly* the number the tool computed; routing this
through the model would reopen the "tool result is not model-generated
calculation" invariant Phase 20 exists to close.
"""

from __future__ import annotations

from typing import Any

_CALCULATOR_PREFIX = {"ta": "பதில்", "en": "Result"}
_CONVERSION_TEMPLATE = {
    "ta": "{value} {source_unit} = {result} {target_unit}",
    "en": "{value} {source_unit} = {result} {target_unit}",
}
_DATE_DIFFERENCE_TEMPLATE = {
    "ta": "வித்தியாசம்: {result_days} நாட்கள்.",
    "en": "Difference: {result_days} days.",
}
_DATE_RESULT_TEMPLATE = {
    "ta": "விடை தேதி: {result_date}",
    "en": "Resulting date: {result_date}",
}


def format_tool_result_text(
    *, tool_name: str, output_payload: dict[str, Any], answer_language: str
) -> str:
    lang = answer_language if answer_language in ("ta", "en") else "en"

    if tool_name == "calculator":
        prefix = _CALCULATOR_PREFIX[lang]
        return f"{prefix}: {output_payload['expression']} = {output_payload['result']}"

    if tool_name == "unit_conversion":
        return _CONVERSION_TEMPLATE[lang].format(**output_payload)

    if tool_name == "date_time_arithmetic":
        if output_payload.get("result_days") is not None:
            return _DATE_DIFFERENCE_TEMPLATE[lang].format(**output_payload)
        return _DATE_RESULT_TEMPLATE[lang].format(**output_payload)

    return str(output_payload)


__all__ = ["format_tool_result_text"]
