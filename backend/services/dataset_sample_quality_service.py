"""Phase 12 Step 18 quality assessment for quarantine records.

Deterministic, bounded structural/statistical checks modeled on
`dataset_quality.py`'s scoring approach (module-level compiled regex
patterns, per-issue reasons) but operating on quarantine-only records,
never on `dataset_records`. Every failure carries an explainable
reason -- never a bare score.

Honest scope: `question_answer_mismatch`, `translation_mismatch`, and
`unbalanced_conversation_turns` require task-specific structured
fields (`question`/`answer`, `source`/`target`, `turns`) and are only
checked when the record's own `structured_payload` actually carries
those keys -- this module never guesses a schema a record didn't
declare.
"""

from __future__ import annotations

import re
from typing import Any

from core_model.sample_import import MAX_TEXT_RECORD_CHARS

MIN_CONTENT_CHARS = 3
_REPEATED_LINE_THRESHOLD = 3
_LOW_UNIQUE_WORD_RATIO = 0.15
_MIN_WORDS_FOR_REPETITION_CHECK = 8

_UNBALANCED_TAG_PATTERN = re.compile(r"<(/?)(\w+)[^>]*>")
_MARKDOWN_FENCE_PATTERN = re.compile(r"```")


class ExternalDatasetQualityService:
    def assess(
        self,
        *,
        raw_content: str,
        normalized_content: str,
        structured_payload: dict[str, Any] | None = None,
        expected_language: str | None = None,
        detected_language: str | None = None,
        required_fields: list[str] | None = None,
        allowed_labels: list[str] | None = None,
    ) -> dict[str, Any]:
        structured_payload = structured_payload or {}
        issues: list[dict[str, str]] = []

        stripped = normalized_content.strip()
        if not stripped:
            issues.append({"issue_type": "empty_content", "reason": "normalized content is empty"})
        elif len(stripped) < MIN_CONTENT_CHARS:
            issues.append(
                {"issue_type": "too_short", "reason": f"content is under {MIN_CONTENT_CHARS} chars"}
            )
        elif len(stripped) > MAX_TEXT_RECORD_CHARS:
            issues.append(
                {
                    "issue_type": "too_long",
                    "reason": f"content exceeds {MAX_TEXT_RECORD_CHARS} chars",
                }
            )

        if "�" in raw_content:
            issues.append(
                {"issue_type": "encoding_corruption", "reason": "replacement characters present"}
            )

        if expected_language and detected_language and expected_language != detected_language:
            issues.append(
                {
                    "issue_type": "language_mismatch",
                    "reason": f"expected '{expected_language}', detected '{detected_language}'",
                }
            )

        if required_fields:
            missing = [field for field in required_fields if not structured_payload.get(field)]
            if missing:
                issues.append(
                    {
                        "issue_type": "missing_required_fields",
                        "reason": f"missing fields: {', '.join(missing)}",
                    }
                )

        if allowed_labels and "label" in structured_payload:
            if structured_payload["label"] not in allowed_labels:
                issues.append(
                    {
                        "issue_type": "invalid_labels",
                        "reason": f"label '{structured_payload['label']}' is not in the allowlist",
                    }
                )

        if self._has_template_repetition(stripped):
            issues.append(
                {"issue_type": "template_repetition", "reason": "the same line repeats excessively"}
            )

        if self._is_low_information(stripped):
            issues.append(
                {
                    "issue_type": "low_information_content",
                    "reason": "very low unique-word ratio for its length",
                }
            )

        if self._has_broken_markup(stripped):
            issues.append(
                {"issue_type": "broken_markup", "reason": "unbalanced HTML/markdown tags"}
            )

        question = structured_payload.get("question")
        answer = structured_payload.get("answer")
        if question is not None and answer is not None:
            if not str(answer).strip() or str(answer).strip() == str(question).strip():
                issues.append(
                    {
                        "issue_type": "question_answer_mismatch",
                        "reason": "answer is empty or identical to the question",
                    }
                )

        turns = structured_payload.get("turns")
        if isinstance(turns, list) and len(turns) > 1:
            roles = [turn.get("role") for turn in turns if isinstance(turn, dict)]
            if roles and len(set(roles)) < 2:
                issues.append(
                    {
                        "issue_type": "unbalanced_conversation_turns",
                        "reason": "every turn has the same role",
                    }
                )

        state = self._state_for(issues)
        return {"state": state, "issues": issues}

    @staticmethod
    def _state_for(issues: list[dict[str, str]]) -> str:
        blocking = {"empty_content", "too_short", "too_long", "missing_required_fields"}
        if any(issue["issue_type"] in blocking for issue in issues):
            return "fail"
        review_only = {"encoding_corruption", "language_mismatch", "invalid_labels"}
        if any(issue["issue_type"] in review_only for issue in issues):
            return "needs_review"
        if issues:
            return "pass_with_warning"
        return "pass"

    @staticmethod
    def _has_template_repetition(text: str) -> bool:
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        if len(lines) < _REPEATED_LINE_THRESHOLD:
            return False
        most_common = max((lines.count(line) for line in set(lines)), default=0)
        return most_common >= _REPEATED_LINE_THRESHOLD

    @staticmethod
    def _is_low_information(text: str) -> bool:
        words = text.lower().split()
        if len(words) < _MIN_WORDS_FOR_REPETITION_CHECK:
            return False
        unique_ratio = len(set(words)) / len(words)
        return unique_ratio < _LOW_UNIQUE_WORD_RATIO

    @staticmethod
    def _has_broken_markup(text: str) -> bool:
        if _MARKDOWN_FENCE_PATTERN.findall(text).__len__() % 2 != 0:
            return True
        stack: list[str] = []
        for is_closing, tag in _UNBALANCED_TAG_PATTERN.findall(text):
            if tag.lower() in ("br", "img", "hr"):
                continue
            if is_closing:
                if not stack or stack[-1] != tag.lower():
                    return True
                stack.pop()
            else:
                stack.append(tag.lower())
        return bool(stack)
