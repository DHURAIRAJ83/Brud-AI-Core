"""MB-13: Reverse Tanglish -- pure. Reuses `core_model.admin_assistant.
localization.tanglish_renderer.to_tanglish()` unchanged (a
deterministic, character-level Tamil-Unicode -> Latin-script phonetic
transliterator, already built and tested for Phase 10A) -- never a
second implementation. Useful for search, dataset expansion, and
Public Chat support, per the task spec; never overwrites the original
Tamil text.
"""

from __future__ import annotations

from typing import Any

from core_model.admin_assistant.localization.tanglish_renderer import to_tanglish

MAX_SAMPLES_STORED = 200
_TAMIL_RANGE = (0x0B80, 0x0BFF)


def generate_reverse_tanglish(*, texts: list[str]) -> dict[str, Any]:
    total = len(texts)
    samples: list[dict[str, Any]] = []
    tamil_record_count = 0
    unconvertible_indices: list[int] = []

    for i, text in enumerate(texts):
        lo, hi = _TAMIL_RANGE
        tamil_chars = sum(1 for ch in text if lo <= ord(ch) <= hi)
        if tamil_chars == 0:
            continue
        tamil_record_count += 1
        try:
            tanglish_preview = to_tanglish(text)[:80]
        except KeyError:
            # A malformed/orphaned Tamil vowel-sign sequence (a real OCR
            # artifact this phase exists to catch) -- to_tanglish()
            # assumes well-formed input. Report as unconvertible rather
            # than crash or fabricate a transliteration.
            unconvertible_indices.append(i)
            continue
        samples.append({"record_index": i, "tanglish_preview": tanglish_preview})

    return {
        "records_analyzed": total,
        "tamil_record_count": tamil_record_count,
        "samples": samples[:MAX_SAMPLES_STORED],
        "sample_count": len(samples),
        "unconvertible_record_count": len(unconvertible_indices),
        "unconvertible_record_indices": unconvertible_indices[:MAX_SAMPLES_STORED],
        "use_cases": ["search", "dataset_expansion", "public_chat_support"],
        "disclosure": (
            "deterministic phonetic transliteration, reused unchanged from core_model."
            "admin_assistant.localization.tanglish_renderer -- a formal phonetic rendering, not "
            "necessarily the exact colloquial spelling a native speaker would type; records with a "
            "malformed/orphaned Tamil vowel-sign sequence (a real OCR artifact) are reported as "
            "unconvertible rather than crashing or producing a fabricated result"
        ),
    }
