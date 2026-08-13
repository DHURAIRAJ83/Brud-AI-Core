"""MB-04B: Echo Detector -- finds when the model copied the prompt
instead of answering it. This is not a hypothetical: MB-04A's own
completion report documented 4/10 baseline and 2/10 optimized real
responses doing exactly this (verbatim-echoing labeled prompt lines
like "Primary knowledge:" or the "Response format:" boilerplate).

Two independent, deterministic signals, no AI:
1. Verbatim overlap -- the longest contiguous substring shared between
   the response and the prompt, found via Python's standard-library
   `difflib.SequenceMatcher` (not regex, not a hand-rolled DP scan).
2. Known structural labels -- a small, locally-owned list of prompt
   section labels observed across MB-04's and MB-04A's own templates
   (e.g. "Response format:", "Confidence:", "Primary knowledge:").
   This module does not import those labels from MB-04/MB-04A; it
   defines its own copy, so this module has zero code dependency on
   either prompt template's internals.

Honest, evidence-based design note: a long verbatim overlap alone does
not distinguish two very different situations -- the model echoing the
prompt's own INSTRUCTIONS (Role/Task/Rules/Format/Confidence -- always
a real failure), versus the model correctly QUOTING a fact from the
prompt's Knowledge section (often legitimate grounding, not a defect).
Verified directly against MB-04A's real benchmark data: a response
whose overlap coincides with a matched label (e.g. "Confidence:",
"Task:") is reliably an instruction echo; a response with overlap but
no matched label is more often a partial factual quote. `severity`
below uses the overlap RATIO (how much of the whole response is
copied) as the strongest single signal, since it is language-agnostic
and caught a Tamil-directive echo that had no matching English label
at all.
"""

from __future__ import annotations

import difflib
from typing import Any

# Observed prompt-structure labels from BOTH MB-04's flat template and
# MB-04A's structured template -- a fresh, MB-04B-owned list, not an
# import of either module's internals.
DEFAULT_KNOWN_LABELS: tuple[str, ...] = (
    "Role:", "Task:", "Knowledge:", "Primary:", "Supporting:", "Workflow:", "Rules:",
    "Expected response language:", "Response format:", "Confidence:", "Answer:",
    "Primary knowledge:", "Supporting knowledge:", "Matched items:",
    "Current workflow step:", "Next steps:", "Detected intent:", "Question:",
)

MIN_ECHO_SUBSTRING_LENGTH = 40
MIN_LABEL_HITS_FOR_ECHO = 2
DOMINANT_OVERLAP_RATIO = 0.6
# Bound worst-case difflib cost on pathologically long prompts -- only
# the tail (closest to "Answer:", where echoes actually originate) is
# compared once the prompt exceeds this length.
MAX_PROMPT_COMPARISON_CHARS = 4000


def _longest_common_substring(a: str, b: str) -> tuple[int, str]:
    if not a or not b:
        return 0, ""
    matcher = difflib.SequenceMatcher(None, a, b, autojunk=False)
    match = matcher.find_longest_match(0, len(a), 0, len(b))
    return match.size, a[match.a : match.a + match.size]


def detect_echo(
    response_text: str, *, prompt_text: str = "", known_labels: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    known_labels = known_labels if known_labels is not None else DEFAULT_KNOWN_LABELS
    response_text = response_text or ""

    comparison_prompt = prompt_text
    if len(comparison_prompt) > MAX_PROMPT_COMPARISON_CHARS:
        comparison_prompt = comparison_prompt[-MAX_PROMPT_COMPARISON_CHARS:]

    overlap_length, overlap_text = (
        _longest_common_substring(response_text, comparison_prompt) if comparison_prompt else (0, "")
    )

    lowered_response = response_text.lower()
    matched_labels = [label for label in known_labels if label.lower() in lowered_response]

    response_len = max(len(response_text), 1)
    overlap_ratio = round(overlap_length / response_len, 3)

    verbatim_echo = overlap_length >= MIN_ECHO_SUBSTRING_LENGTH
    label_echo = len(matched_labels) >= MIN_LABEL_HITS_FOR_ECHO

    if verbatim_echo and label_echo:
        echo_type = "verbatim_and_label"
    elif verbatim_echo:
        echo_type = "verbatim_prompt_overlap"
    elif label_echo:
        echo_type = "label_echo"
    else:
        echo_type = "none"

    if overlap_ratio >= DOMINANT_OVERLAP_RATIO:
        severity = "dominant"  # most/all of the response is copied text -- little to no real answer
    elif verbatim_echo or label_echo:
        severity = "partial"  # some copying, but likely coexists with real generated content
    else:
        severity = "none"

    return {
        "echo_detected": verbatim_echo or label_echo,
        "echo_type": echo_type,
        "severity": severity,
        "overlap_length_chars": overlap_length,
        "overlap_ratio": overlap_ratio,
        "overlap_text": overlap_text,
        "matched_labels": matched_labels,
    }
