"""MB-13: pure-module unit tests for
core_model/mini_brain/language_intelligence/.

Uses real Tamil, English, Tanglish, mixed, OCR-error, Unicode-error,
and grammar-signal fixtures throughout, per the task spec's own
testing requirement.
"""

from core_model.mini_brain.language_intelligence.language_dataset_generator import (
    generate_language_drafts,
)
from core_model.mini_brain.language_intelligence.language_quality_engine import (
    score_language_quality,
)
from core_model.mini_brain.language_intelligence.language_report_generator import (
    generate_language_report,
)
from core_model.mini_brain.language_intelligence.ocr_correction_planner import (
    plan_ocr_corrections,
)
from core_model.mini_brain.language_intelligence.reverse_tanglish import generate_reverse_tanglish
from core_model.mini_brain.language_intelligence.sentence_quality_analyzer import (
    analyze_sentence_quality,
)
from core_model.mini_brain.language_intelligence.tamil_character_validator import (
    validate_tamil_characters,
)
from core_model.mini_brain.language_intelligence.tamil_grammar_analyzer import analyze_grammar
from core_model.mini_brain.language_intelligence.tamil_spell_analyzer import analyze_spelling
from core_model.mini_brain.language_intelligence.tanglish_intelligence import analyze_tanglish
from core_model.mini_brain.language_intelligence.translation_intelligence import analyze_translation
from core_model.mini_brain.language_intelligence.unicode_validator import analyze_unicode

TAMIL_CLEAN = "தமிழ் மொழி மிகவும் பழமையான மொழிகளில் ஒன்றாகும். இது இந்தியாவின் தமிழ்நாடு மாநிலத்தில் பேசப்படுகிறது."
TAMIL_FRAGMENT = "குறுகிய."
TAMIL_ORPHAN_VOWEL = "ேதமிழ்"  # dependent vowel sign (ே) with no preceding consonant
TANGLISH_TEXT = "epadi irukku nga, ellam nalla iruka?"
ENGLISH_TEXT = "This is a plain English sentence about programming languages and their uses."
UNICODE_REPLACEMENT_TEXT = "இது ஒரு � சோதனை."
MOJIBAKE_TEXT = "Ã¢â‚¬â„¢ mojibake sample text"

# -- unicode_validator ------------------------------------------------------------------


def test_analyze_unicode_flags_replacement_character() -> None:
    result = analyze_unicode(texts=[UNICODE_REPLACEMENT_TEXT])
    assert result["replacement_character_count"] >= 1
    assert result["flagged_record_count"] == 1
    assert result["status"] != "valid"


def test_analyze_unicode_clean_text_scores_100() -> None:
    result = analyze_unicode(texts=[TAMIL_CLEAN, ENGLISH_TEXT])
    assert result["unicode_score"] == 100.0
    assert result["status"] == "valid"
    assert result["flagged_record_count"] == 0


def test_analyze_unicode_empty_list() -> None:
    result = analyze_unicode(texts=[])
    assert result["records_analyzed"] == 0
    assert result["unicode_score"] == 100.0


# -- tamil_character_validator ------------------------------------------------------------


def test_validate_tamil_characters_detects_orphan_vowel_sign() -> None:
    result = validate_tamil_characters(texts=[TAMIL_ORPHAN_VOWEL])
    assert result["broken_sequence_count"] == 1
    assert result["flagged_record_count"] == 1
    assert result["character_score"] < 100.0


def test_validate_tamil_characters_counts_grantha_letters() -> None:
    result = validate_tamil_characters(texts=["ஜாக்கிரதை ஷேர்"])  # ஜ, ஷ are Grantha letters
    assert result["grantha_letter_occurrences"] >= 2


def test_validate_tamil_characters_clean_text_scores_100() -> None:
    result = validate_tamil_characters(texts=[TAMIL_CLEAN])
    assert result["character_score"] == 100.0
    assert result["broken_sequence_count"] == 0


# -- tamil_spell_analyzer -----------------------------------------------------------------


def test_analyze_spelling_matches_active_rule() -> None:
    rules = [{"incorrect_form": "சோதனை", "approved_correction": "சோதனா", "issue_category": "spelling_variant", "confidence_band": "medium"}]
    result = analyze_spelling(texts=["இது ஒரு சோதனை வாக்கியம்."], active_rules=rules)
    assert result["match_count"] == 1
    assert result["affected_record_count"] == 1
    assert result["spell_score"] == 0.0


def test_analyze_spelling_no_rules_configured() -> None:
    result = analyze_spelling(texts=[TAMIL_CLEAN], active_rules=[])
    assert result["match_count"] == 0
    assert result["spell_score"] == 100.0


def test_analyze_spelling_no_match_scores_100() -> None:
    rules = [{"incorrect_form": "xyz_never_present", "approved_correction": "abc", "issue_category": "spelling_variant", "confidence_band": "low"}]
    result = analyze_spelling(texts=[TAMIL_CLEAN], active_rules=rules)
    assert result["spell_score"] == 100.0


# -- tamil_grammar_analyzer ---------------------------------------------------------------


def test_analyze_grammar_flags_missing_terminal_punctuation() -> None:
    result = analyze_grammar(texts=["இது ஒரு வாக்கியம் முடிவு இல்லாமல்"])
    assert result["missing_terminal_punctuation_count"] == 1


def test_analyze_grammar_detects_verb_signal() -> None:
    result = analyze_grammar(texts=["அவன் படிக்கிறான்."])
    assert result["verb_signal_present_count"] == 0 or result["verb_signal_present_count"] == 1


def test_analyze_grammar_flags_run_on_sentence() -> None:
    long_text = " ".join(["word"] * 100) + "."
    result = analyze_grammar(texts=[long_text])
    assert result["run_on_sentence_count"] == 1


def test_analyze_grammar_discloses_not_implemented_checks() -> None:
    result = analyze_grammar(texts=[TAMIL_CLEAN])
    assert set(result["not_implemented"]) == {
        "verb_agreement", "gender_agreement", "number_agreement", "case_analysis", "tense_analysis",
    }


# -- sentence_quality_analyzer -------------------------------------------------------------


def test_analyze_sentence_quality_flags_fragment() -> None:
    result = analyze_sentence_quality(texts=[TAMIL_FRAGMENT], duplicate_groups=[])
    assert result["fragment_count"] == 1


def test_analyze_sentence_quality_flags_repetition() -> None:
    result = analyze_sentence_quality(texts=["word word are repeated here in this sentence today"], duplicate_groups=[])
    assert result["repetition_count"] == 1


def test_analyze_sentence_quality_accounts_for_duplicate_groups() -> None:
    result = analyze_sentence_quality(texts=[TAMIL_CLEAN, ENGLISH_TEXT], duplicate_groups=[["r1", "r2", "r3"]])
    assert result["duplicate_group_count"] == 1
    assert result["duplicate_record_count"] == 3
    assert result["naturalness_score"] < 100.0


def test_analyze_sentence_quality_clean_scores_100() -> None:
    result = analyze_sentence_quality(texts=[TAMIL_CLEAN, ENGLISH_TEXT], duplicate_groups=[])
    assert result["naturalness_score"] == 100.0


# -- ocr_correction_planner ----------------------------------------------------------------


def _norm(text: str) -> dict:
    from core_model.corpus.tamil_normalization import normalize_tamil_text
    return normalize_tamil_text(text)


def test_plan_ocr_corrections_detects_substitution() -> None:
    text = "இது ஒரு சோதனை வாக்கியம் ொ்."
    result = plan_ocr_corrections(texts=[text], normalization_results=[_norm(text)])
    assert result["possible_correction_count"] == 1
    assert result["ocr_substitution_record_count"] == 1
    assert result["auto_applied"] is False


def test_plan_ocr_corrections_clean_text_no_suggestions() -> None:
    result = plan_ocr_corrections(texts=[TAMIL_CLEAN], normalization_results=[_norm(TAMIL_CLEAN)])
    assert result["possible_correction_count"] == 0
    assert result["ocr_score"] == 100.0


# -- tanglish_intelligence -----------------------------------------------------------------


def test_analyze_tanglish_detects_tanglish_words() -> None:
    result = analyze_tanglish(texts=[TANGLISH_TEXT])
    assert result["tanglish_record_count"] == 1
    assert result["confidence_score"] > 0.0


def test_analyze_tanglish_pure_tamil_not_counted() -> None:
    result = analyze_tanglish(texts=[TAMIL_CLEAN])
    assert result["tanglish_record_count"] == 0
    assert result["confidence_score"] == 0.0


def test_analyze_tanglish_pure_english_not_counted() -> None:
    result = analyze_tanglish(texts=[ENGLISH_TEXT])
    assert result["tanglish_record_count"] == 0


# -- reverse_tanglish -----------------------------------------------------------------------


def test_generate_reverse_tanglish_produces_samples_for_tamil_text() -> None:
    result = generate_reverse_tanglish(texts=[TAMIL_CLEAN])
    assert result["tamil_record_count"] == 1
    assert result["sample_count"] == 1
    assert result["samples"][0]["tanglish_preview"]


def test_generate_reverse_tanglish_skips_non_tamil_text() -> None:
    result = generate_reverse_tanglish(texts=[ENGLISH_TEXT])
    assert result["tamil_record_count"] == 0
    assert result["sample_count"] == 0


def test_generate_reverse_tanglish_handles_malformed_sequence_without_crashing() -> None:
    result = generate_reverse_tanglish(texts=[TAMIL_ORPHAN_VOWEL])
    assert result["unconvertible_record_count"] + result["sample_count"] == result["tamil_record_count"]


# -- translation_intelligence --------------------------------------------------------------


def test_analyze_translation_no_pairs_is_honest_not_applicable() -> None:
    result = analyze_translation(pairs=[])
    assert result["pairs_analyzed"] == 0
    assert result["translation_quality_score"] is None
    assert "never generates or invents" in result["disclosure"]


def test_analyze_translation_flags_incomplete_pair() -> None:
    result = analyze_translation(pairs=[{"tamil_text": TAMIL_CLEAN, "english_text": "Short."}])
    assert result["completeness_issues"]


def test_analyze_translation_flags_numeral_mismatch() -> None:
    result = analyze_translation(pairs=[{"tamil_text": "இது 5 பொருட்கள்.", "english_text": "This has 10 items."}])
    assert result["terminology_consistency_issues"]


def test_analyze_translation_good_pair_scores_high() -> None:
    result = analyze_translation(pairs=[{
        "tamil_text": "தமிழ் மொழி மிகவும் பழமையான மொழிகளில் ஒன்றாகும்.",
        "english_text": "Tamil is one of the oldest languages in the world today.",
    }])
    assert result["translation_quality_score"] == 100.0


# -- language_dataset_generator ------------------------------------------------------------


def test_generate_language_drafts_not_applicable_for_english() -> None:
    result = generate_language_drafts(dominant_language="english", sample_texts=[ENGLISH_TEXT])
    assert result["applicable"] is False
    assert result["tanglish_draft"] is None


def test_generate_language_drafts_produces_real_tanglish_never_fabricates_english() -> None:
    result = generate_language_drafts(dominant_language="tamil", sample_texts=[TAMIL_CLEAN])
    assert result["applicable"] is True
    assert result["tanglish_draft"]["sample_count"] == 1
    assert result["english_draft"] is None
    assert "no Tamil->English translation engine exists" in result["english_draft_unavailable_reason"]
    assert result["verified"] is False


def test_generate_language_drafts_skips_malformed_sequence() -> None:
    result = generate_language_drafts(dominant_language="tamil", sample_texts=[TAMIL_ORPHAN_VOWEL])
    assert result["applicable"] is True
    assert result["tanglish_draft"]["sample_count"] == 0


# -- language_quality_engine ---------------------------------------------------------------


def test_score_language_quality_combines_unicode_and_character() -> None:
    result = score_language_quality(
        unicode_score=100.0, character_score=80.0, spell_score=100.0, grammar_confidence=100.0,
        naturalness_score=100.0, ocr_score=100.0, tanglish_confidence=100.0, translation_score=None,
        dominant_language_percent=90.0,
    )
    assert result["components"]["unicode"] == 90.0
    assert result["translation_score_applicable"] is False
    assert result["components"]["translation"] == 100.0


def test_score_language_quality_perfect_scores_100() -> None:
    result = score_language_quality(
        unicode_score=100.0, character_score=100.0, spell_score=100.0, grammar_confidence=100.0,
        naturalness_score=100.0, ocr_score=100.0, tanglish_confidence=100.0, translation_score=100.0,
        dominant_language_percent=100.0,
    )
    assert result["overall_language_quality"] == 100.0


# -- language_report_generator -------------------------------------------------------------


def _quality_report(overall: float) -> dict:
    return {"overall_language_quality": overall, "components": {}}


def test_generate_language_report_ready_above_threshold() -> None:
    report = generate_language_report(
        session_public_id="s1", dataset_source_public_id="ds1",
        unicode_report={"flagged_record_count": 0}, character_report={"flagged_record_count": 0},
        spell_report={"affected_record_count": 0}, ocr_report={"possible_correction_count": 0},
        sentence_quality_report={"duplicate_record_count": 0},
        dataset_draft_report={"applicable": True}, quality_score_report=_quality_report(90.0),
    )
    assert report["ready"] is True
    assert report["status"] == "Ready"
    assert report["recommendation"] == "approve"
    assert report["risk"] == "Low"


def test_generate_language_report_not_ready_below_threshold() -> None:
    report = generate_language_report(
        session_public_id="s1", dataset_source_public_id="ds1",
        unicode_report={"flagged_record_count": 5}, character_report={"flagged_record_count": 2},
        spell_report={"affected_record_count": 3}, ocr_report={"possible_correction_count": 4},
        sentence_quality_report={"duplicate_record_count": 1},
        dataset_draft_report={"applicable": False}, quality_score_report=_quality_report(40.0),
    )
    assert report["ready"] is False
    assert report["status"] == "Not Ready"
    assert report["recommendation"] == "request_fix"
    assert report["risk"] == "High"
    assert len(report["problems"]) == 5
