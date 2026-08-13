"""MB-04B: Response Formatter -- validates and improves whitespace,
paragraph, bullet, and code-fence formatting WITHOUT touching word
content. Deliberately conservative and cheap: plain string operations
throughout (split/join/strip), no regex, single pass per line.

Two entry points, matching the pipeline's own two named stages:
- `validate_formatting()` -- read-only diagnostics (the "Formatting
  Validator" stage): what's wrong, never changes anything.
- `format_response_text()` -- the actual fixer (the "Response
  Formatter" module): applies only the specific, narrow fixes below.

Note: this module lives at
`core_model/mini_brain/quality/response_formatter.py`, a distinct
package path from MB-04's own
`core_model/mini_brain/runtime/response_formatter.py` (which wraps a
raw model response into the final envelope with disclaimers). Python
namespaces by full module path, so there is no import collision --
but the identical filename is worth calling out explicitly so nobody
confuses the two.
"""

from __future__ import annotations

from typing import Any

MAX_CONSECUTIVE_BLANK_LINES = 1
BULLET_MARKERS = ("*", "•", "-")
_SENTENCE_END_PUNCTUATION = (".", "!", "?")


def _collapse_blank_lines(lines: list[str]) -> tuple[list[str], bool]:
    out: list[str] = []
    blank_run = 0
    changed = False
    for line in lines:
        if line.strip() == "":
            blank_run += 1
            if blank_run <= MAX_CONSECUTIVE_BLANK_LINES:
                out.append("")
            else:
                changed = True
        else:
            blank_run = 0
            out.append(line)
    return out, changed


def _normalize_line_whitespace(line: str) -> tuple[str, bool]:
    stripped = line.rstrip()
    collapsed = " ".join(stripped.split()) if stripped.strip() else stripped
    # Preserve leading indentation for list items / code, only collapse
    # *internal* runs of spaces, not leading structure.
    leading = len(line) - len(line.lstrip(" "))
    result = (" " * leading) + collapsed.lstrip(" ") if collapsed else collapsed
    return result, result != line


def _normalize_bullet_marker(line: str) -> tuple[str, bool]:
    lstripped = line.lstrip(" ")
    leading = line[: len(line) - len(lstripped)]
    for marker in BULLET_MARKERS:
        prefix = marker + " "
        if lstripped.startswith(prefix) and marker != "-":
            return leading + "- " + lstripped[len(prefix):], True
    return line, False


def _ensure_space_after_sentence_punctuation(text: str) -> tuple[str, bool]:
    """Inserts a space after '.', '!', '?' when immediately followed by
    a letter with no space -- but only when the punctuation itself
    follows a LETTER (never a digit), so decimals like "3.14" and
    version numbers are never touched."""

    if not text:
        return text, False
    out_chars: list[str] = []
    changed = False
    for i, ch in enumerate(text):
        out_chars.append(ch)
        if (
            ch in _SENTENCE_END_PUNCTUATION
            and i > 0
            and text[i - 1].isalpha()
            and i + 1 < len(text)
            and text[i + 1].isalpha()
        ):
            out_chars.append(" ")
            changed = True
    return "".join(out_chars), changed


def validate_formatting(text: str) -> dict[str, Any]:
    text = text or ""
    issues: list[str] = []
    lines = text.split("\n")

    blank_run = 0
    for line in lines:
        if line.strip() == "":
            blank_run += 1
            if blank_run > MAX_CONSECUTIVE_BLANK_LINES:
                issues.append("excessive_blank_lines")
                break
        else:
            blank_run = 0

    if any(line != line.rstrip() for line in lines):
        issues.append("trailing_whitespace")

    if any("  " in line.strip() for line in lines):
        issues.append("multiple_internal_spaces")

    if any(
        any(line.lstrip(" ").startswith(m + " ") for m in BULLET_MARKERS if m != "-")
        for line in lines
    ):
        issues.append("inconsistent_bullet_markers")

    _, punctuation_changed = _ensure_space_after_sentence_punctuation(text)
    if punctuation_changed:
        issues.append("missing_space_after_sentence_punctuation")

    fence_count = text.count("```")
    if fence_count % 2 != 0:
        issues.append("unclosed_code_fence")

    return {"passed": len(issues) == 0, "issues": issues}


def format_response_text(text: str) -> dict[str, Any]:
    text = text or ""
    original = text

    lines = text.split("\n")
    lines, blank_changed = _collapse_blank_lines(lines)

    normalized_lines: list[str] = []
    ws_changed = False
    bullet_changed = False
    for line in lines:
        line, changed_ws = _normalize_line_whitespace(line)
        line, changed_bullet = _normalize_bullet_marker(line)
        normalized_lines.append(line)
        ws_changed = ws_changed or changed_ws
        bullet_changed = bullet_changed or changed_bullet

    joined = "\n".join(normalized_lines)
    joined, punctuation_changed = _ensure_space_after_sentence_punctuation(joined)

    changes: list[str] = []
    if blank_changed:
        changes.append("collapsed_blank_lines")
    if ws_changed:
        changes.append("normalized_whitespace")
    if bullet_changed:
        changes.append("normalized_bullet_markers")
    if punctuation_changed:
        changes.append("added_space_after_punctuation")

    return {
        "formatted_text": joined,
        "changed": joined != original,
        "changes": changes,
    }
