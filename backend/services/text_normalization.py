"""Conservative, deterministic multilingual text normalization for dataset ingestion."""

import re
import unicodedata
from dataclasses import asdict, dataclass

TAMIL_RE = re.compile(r"[\u0B80-\u0BFF]")
LATIN_RE = re.compile(r"[A-Za-z]")
ZERO_WIDTH_SAFE_REMOVE = {"\u200b", "\ufeff"}


@dataclass(frozen=True)
class NormalizationResult:
    original: str
    normalized: str
    comparison_form: str
    language: str
    changed: bool
    warnings: list[dict[str, str]]
    statistics: dict[str, int]

    def public(self) -> dict[str, object]:
        return asdict(self)


def normalize_text(value: str, language: str = "unknown") -> NormalizationResult:
    """Normalize representation and whitespace without transliteration or spelling correction."""

    original = value
    warnings: list[dict[str, str]] = []
    if "\ufffd" in value:
        warnings.append({"code": "replacement_character", "message": "Replacement character found"})
    value = value.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    value = "".join(character for character in value if character not in ZERO_WIDTH_SAFE_REMOVE)
    value = unicodedata.normalize("NFC", value)
    lines = [re.sub(r"[\t\f\v ]+", " ", line).strip() for line in value.split("\n")]
    collapsed: list[str] = []
    blank = False
    for line in lines:
        if not line:
            if not blank and collapsed:
                collapsed.append("")
            blank = True
        else:
            collapsed.append(line)
            blank = False
    normalized = "\n".join(collapsed).strip()
    has_tamil, has_latin = bool(TAMIL_RE.search(normalized)), bool(LATIN_RE.search(normalized))
    if language == "en" and has_tamil:
        warnings.append(
            {"code": "language_script_mismatch", "message": "Tamil script under English language"}
        )
    elif language == "ta" and has_latin and not has_tamil:
        warnings.append(
            {"code": "language_script_mismatch", "message": "Latin-only text under Tamil language"}
        )
    elif language == "mixed" and normalized and not (has_tamil and has_latin):
        warnings.append(
            {
                "code": "mixed_script_limited",
                "message": "Mixed language row uses one detected script",
            }
        )
    if normalized and unicodedata.combining(normalized[0]):
        warnings.append(
            {"code": "suspicious_unicode_sequence", "message": "Text starts with a combining mark"}
        )
    comparison = re.sub(r"\s+", " ", normalized).strip()
    if language in {"en", "tgl", "mixed"}:
        comparison = comparison.casefold()
    return NormalizationResult(
        original=original,
        normalized=normalized,
        comparison_form=comparison,
        language=language,
        changed=original != normalized,
        warnings=warnings,
        statistics={"original_length": len(original), "normalized_length": len(normalized)},
    )


def normalize_record_fields(
    values: dict[str, object],
) -> tuple[dict[str, object], list[dict[str, str]]]:
    """Normalize logical record text and combine non-sensitive warnings."""

    normalized = dict(values)
    warnings: list[dict[str, str]] = []
    language = str(values.get("language", "unknown"))
    for field in ("instruction", "input_text", "output_text", "normalized_input"):
        value = values.get(field)
        if isinstance(value, str):
            result = normalize_text(value, language)
            normalized[field] = result.normalized
            warnings.extend({**warning, "field": field} for warning in result.warnings)
    return normalized, warnings
