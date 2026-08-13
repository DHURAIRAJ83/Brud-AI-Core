"""MB-16: Text Section builder -- pure. Reuses MB-13's own already-
computed language/Unicode/OCR/Tanglish/quality reports -- never
re-runs any language analysis itself. When no MB-13 session is linked,
the text section is honestly built from raw OCR text alone, with every
language-quality field `None`.
"""

from __future__ import annotations

from typing import Any


def build_text_section(*, ocr_text: str, language_session: dict[str, Any] | None) -> dict[str, Any]:
    if language_session is None:
        return {
            "ocr_text": ocr_text, "ocr_char_count": len(ocr_text), "language_session_linked": False,
            "dominant_language": None, "unicode_score": None, "language_quality_score": None,
            "language_quality_status": None,
            "disclosure": "no MB-13 Language Intelligence session linked -- language quality fields are unavailable, not zero",
        }

    language_scan = language_session.get("language_scan_report", {})
    unicode_report = language_session.get("unicode_report", {})
    quality = language_session.get("quality_score_report", {})
    report = language_session.get("language_report", {})

    return {
        "ocr_text": ocr_text, "ocr_char_count": len(ocr_text), "language_session_linked": True,
        "dominant_language": language_scan.get("dominant_language"),
        "unicode_score": unicode_report.get("unicode_score"),
        "language_quality_score": quality.get("overall_language_quality"),
        "language_quality_status": report.get("status"),
        "tanglish_report": language_session.get("tanglish_report", {}),
        "translation_report": language_session.get("translation_report", {}),
    }
