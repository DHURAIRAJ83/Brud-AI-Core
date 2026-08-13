"""MB-05: SFT Readiness Analyzer -- instruction/response quality,
conversation format, system prompts, answer completeness, and role
consistency for instruction-tuning suitability. Built from the
records directly plus the already-computed Quality analysis
(`unbalanced_conversation_turns` issues, reused rather than
re-derived).
"""

from __future__ import annotations

from typing import Any

MIN_ANSWER_CHARS = 10
READY_INSTRUCTION_RATIO = 0.9
READY_COMPLETENESS_RATIO = 0.85


def assess_sft_readiness(*, records: list[dict[str, Any]], quality: dict[str, Any]) -> dict[str, Any]:
    total = len(records)
    if total == 0:
        return {"status": "Not Ready", "reasons": ["no records available"]}

    instruction_present = sum(1 for r in records if (r.get("instruction") or "").strip())
    instruction_ratio = round(instruction_present / total, 3)

    complete_answers = sum(1 for r in records if len((r.get("output_text") or "").strip()) >= MIN_ANSWER_CHARS)
    completeness_ratio = round(complete_answers / total, 3)

    system_prompt_count = sum(1 for r in records if (r.get("metadata") or {}).get("system_prompt"))
    system_prompt_ratio = round(system_prompt_count / total, 3)

    chat_records = [r for r in records if r.get("record_type") == "chat"]
    unbalanced_turn_issue_count = sum(
        1 for entry in quality.get("flagged_record_details", [])
        for issue in entry["issues"] if issue["issue_type"] == "unbalanced_conversation_turns"
    )
    role_consistency_ratio = (
        round(1 - (unbalanced_turn_issue_count / len(chat_records)), 3) if chat_records else None
    )

    clean_ratio = quality.get("clean_ratio") or 0.0

    blockers: list[str] = []
    if instruction_ratio < 0.5:
        blockers.append(f"only {round(instruction_ratio * 100, 1)}% of records have a non-empty instruction")
    if completeness_ratio < 0.5:
        blockers.append(f"only {round(completeness_ratio * 100, 1)}% of records have a complete (>= {MIN_ANSWER_CHARS} char) answer")
    if clean_ratio < 0.5:
        blockers.append(f"response quality too low: clean_ratio {clean_ratio} is below 0.5")
    if blockers:
        return {
            "status": "Not Ready", "reasons": blockers, "instruction_quality_ratio": instruction_ratio,
            "answer_completeness_ratio": completeness_ratio, "system_prompt_coverage_ratio": system_prompt_ratio,
            "role_consistency_ratio": role_consistency_ratio,
        }

    improvements: list[str] = []
    if instruction_ratio < READY_INSTRUCTION_RATIO:
        improvements.append(f"instruction quality {round(instruction_ratio * 100, 1)}% is below the {READY_INSTRUCTION_RATIO * 100:.0f}% Ready threshold")
    if completeness_ratio < READY_COMPLETENESS_RATIO:
        improvements.append(f"answer completeness {round(completeness_ratio * 100, 1)}% is below the {READY_COMPLETENESS_RATIO * 100:.0f}% Ready threshold")
    if role_consistency_ratio is not None and role_consistency_ratio < 0.9:
        improvements.append(f"{unbalanced_turn_issue_count} conversation record(s) have unbalanced roles")

    status = "Needs Improvement" if improvements else "Ready"
    if status == "Ready":
        improvements = [
            f"instruction quality {round(instruction_ratio * 100, 1)}% >= {READY_INSTRUCTION_RATIO * 100:.0f}%",
            f"answer completeness {round(completeness_ratio * 100, 1)}% >= {READY_COMPLETENESS_RATIO * 100:.0f}%",
        ]

    return {
        "status": status, "reasons": improvements, "instruction_quality_ratio": instruction_ratio,
        "answer_completeness_ratio": completeness_ratio, "system_prompt_coverage_ratio": system_prompt_ratio,
        "role_consistency_ratio": role_consistency_ratio,
    }
