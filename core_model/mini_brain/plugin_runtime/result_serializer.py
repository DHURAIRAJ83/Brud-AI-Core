"""MB-25: Result Serializer -- pure. Every plugin result is serialized
to canonical JSON. A sandbox-aware filesystem-path pass runs *first*
-- a genuinely new capability, since it only redacts paths that fall
*outside* the plugin's own approved sandbox roots, preserving ones
inside -- then the result is run through MB-23's own `feedback_
sanitizer.sanitize_text()` directly (the same regex-based email/
phone/token/API-key/JWT/database-identifier *and* generic-absolute-
path redaction MB-23 already established -- never a second redaction
implementation). Note MB-23's own pass still blanket-redacts any
remaining `/home/`, `/etc/`, `/usr/`, `/var/`-prefixed path regardless
of sandbox status (e.g. a sandbox root under `/home/<user>/...` still
has its username redacted) -- a deliberately conservative, privacy-
first behavior this module does not weaken. Output is bounded and
truncated if oversized, honoring whichever pass truncated first.
"""

from __future__ import annotations

import json
import re
from typing import Any

from core_model.mini_brain.public_chat_runtime.feedback_sanitizer import sanitize_text

MAX_OUTPUT_CHARACTERS = 8_000
_PATH_LIKE_PATTERN = re.compile(r"(?:/[\w.\-]+){2,}")


def _redact_paths_outside_sandbox(text: str, allowed_roots: list[str]) -> tuple[str, bool]:
    changed = False

    def _replace(match: re.Match[str]) -> str:
        nonlocal changed
        candidate = match.group(0)
        if any(candidate.startswith(root) for root in allowed_roots):
            return candidate
        changed = True
        return "[REDACTED_PATH_OUTSIDE_SANDBOX]"

    redacted = _PATH_LIKE_PATTERN.sub(_replace, text)
    return redacted, changed


def sanitize_result(*, result: Any, allowed_filesystem_roots: list[str]) -> dict[str, Any]:
    serialized = json.dumps(result, ensure_ascii=False, sort_keys=True, default=str)

    pre_redacted, path_redacted = _redact_paths_outside_sandbox(serialized, allowed_filesystem_roots)
    sanitized = sanitize_text(raw_text=pre_redacted)
    text = sanitized["sanitized_text"]

    redaction_categories = list(sanitized["redaction_categories_applied"])
    if path_redacted:
        redaction_categories.append("filesystem_path_outside_sandbox")

    truncated = sanitized["truncated"]
    if len(text) > MAX_OUTPUT_CHARACTERS:
        text = text[:MAX_OUTPUT_CHARACTERS]
        truncated = True
        redaction_categories.append("truncated_oversized_output")

    return {
        "sanitized_output_text": text, "truncated": truncated, "redaction_categories_applied": redaction_categories,
        "disclosure": "regex-based redaction only -- a best-effort defense, never a guarantee that all secrets or out-of-sandbox paths are caught",
    }
