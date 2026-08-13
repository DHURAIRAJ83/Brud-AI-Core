"""MB-21: Safety Violation Detector -- pure. Scans normalized provider
response text for a small, disclosed set of concrete red flags tied
directly to this phase's own non-negotiable rules -- shell-command-
looking content, executable-file download links, and secret-like
content leaking back from a provider. This is not, and does not claim
to be, a general content-safety classifier; it never blocks or
modifies a response, it only flags it for admin review.
"""

from __future__ import annotations

import re
from typing import Any

_SHELL_COMMAND_PATTERN = re.compile(
    r"\b(rm\s+-rf|sudo\s|curl\s.*\|\s*sh|wget\s.*\|\s*sh|chmod\s+\+x|/bin/(ba)?sh)\b", re.IGNORECASE
)
_EXECUTABLE_LINK_PATTERN = re.compile(r"https?://\S+\.(exe|msi|sh|bat|apk|dmg|deb|rpm)\b", re.IGNORECASE)
_SECRET_LIKE_PATTERN = re.compile(r"\b(api[_-]?key|password|secret|token)\s*[:=]\s*\S+", re.IGNORECASE)


def detect_safety_violations(*, normalized_responses: list[dict[str, Any]]) -> dict[str, Any]:
    flagged: list[dict[str, Any]] = []
    for response in normalized_responses:
        text = response.get("normalized_text")
        if not text:
            continue
        categories = []
        if _SHELL_COMMAND_PATTERN.search(text):
            categories.append("shell_command_like_content")
        if _EXECUTABLE_LINK_PATTERN.search(text):
            categories.append("executable_download_link")
        if _SECRET_LIKE_PATTERN.search(text):
            categories.append("secret_like_content_in_response")
        if categories:
            flagged.append({"provider_key": response["provider_key"], "categories": categories})

    return {
        "flagged_count": len(flagged), "flagged_responses": flagged,
        "has_violations": len(flagged) > 0,
        "disclosure": (
            "a narrow, disclosed set of concrete red flags tied directly to this phase's own "
            "non-negotiable rules (shell commands, executable download links, secret-like content) -- "
            "never a general content-safety classifier; this module only flags for admin review, it "
            "never blocks or modifies a response itself"
        ),
    }
