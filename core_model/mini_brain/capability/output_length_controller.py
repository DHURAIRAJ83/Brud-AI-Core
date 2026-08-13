"""MB-04C: Output Length Controller -- deterministic checks for too
short, too long, cut off, or unfinished responses. Report only; this
module never rewrites text (that would be MB-04B's or a Prompt
Builder's job, not this phase's).

`cut_off` is the most reliable of these signals: MB-04's own Runtime
Manager already reports `stop_reason` from the real llama.cpp backend
("length" means generation stopped only because it hit the max_tokens
ceiling, not because the model reached a natural end) -- combined with
checking whether the text ends mid-sentence, this is a precise,
evidence-grounded signal, not a guess.
"""

from __future__ import annotations

from typing import Any

MIN_MEANINGFUL_CHARS = 15
MIN_MEANINGFUL_WORDS = 3
_SENTENCE_END_CHARS = (".", "!", "?", '"', "'", ")", "。")
_DANGLING_WORD_ENDINGS = (
    "and", "or", "but", "the", "a", "an", "to", "of", "in", "on", "with", "is",
    "are", "was", "were", "for", "as", "that", "this",
)


def _ends_mid_sentence(text: str) -> bool:
    stripped = text.rstrip()
    if not stripped:
        return False
    return stripped[-1] not in _SENTENCE_END_CHARS


def _ends_on_dangling_word(text: str) -> bool:
    words = text.strip().split()
    if not words:
        return False
    last = words[-1].strip(".,!?;:\"'()").lower()
    return last in _DANGLING_WORD_ENDINGS


def evaluate_output_length(
    text: str, *, stop_reason: str | None, target_max_tokens: int, tokens_generated: int | None = None,
) -> dict[str, Any]:
    text = text or ""
    stripped = text.strip()
    char_count = len(stripped)
    word_count = len(stripped.split())

    issues: list[str] = []

    too_short = char_count < MIN_MEANINGFUL_CHARS or word_count < MIN_MEANINGFUL_WORDS
    if too_short:
        issues.append("too_short")

    # "too_long" cannot really happen given max_tokens caps generation,
    # but is still checked directly rather than assumed impossible.
    # Real data (MB-04A benchmark) showed the backend can overshoot the
    # requested budget by a token or two (49 generated against a
    # 48-token request) -- an ordinary llama.cpp stopping-check quirk,
    # not a real problem, so a small tolerance avoids flagging normal
    # noise as an issue.
    overshoot_tolerance = max(5, round(target_max_tokens * 0.1))
    too_long = tokens_generated is not None and tokens_generated > target_max_tokens + overshoot_tolerance
    if too_long:
        issues.append("too_long")

    hit_token_ceiling = stop_reason == "length"
    ends_mid_sentence = _ends_mid_sentence(stripped) if stripped else False
    cut_off = hit_token_ceiling and ends_mid_sentence
    if cut_off:
        issues.append("cut_off")

    unfinished = cut_off or (bool(stripped) and _ends_on_dangling_word(stripped))
    if unfinished and "cut_off" not in issues:
        issues.append("unfinished")

    return {
        "char_count": char_count,
        "word_count": word_count,
        "too_short": too_short,
        "too_long": too_long,
        "cut_off": cut_off,
        "unfinished": unfinished,
        "issues": issues,
    }
