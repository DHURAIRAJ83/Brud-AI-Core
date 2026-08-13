"""MB-04B: pure-module unit tests for core_model/mini_brain/quality/.

Several cases below are drawn directly from MB-04A's own real
benchmark data (10 questions x baseline/optimized generations against
the real Qwen2.5-0.5B-Instruct model) -- these are not synthetic
examples, they are the exact real failures MB-04A's completion report
already documented, used here as ground truth.
"""

from core_model.mini_brain.quality.consistency_validator import validate_consistency
from core_model.mini_brain.quality.echo_cleaner import clean_echo, clean_echo_iteratively
from core_model.mini_brain.quality.echo_detector import detect_echo
from core_model.mini_brain.quality.mixed_language_resolver import resolve_response_language
from core_model.mini_brain.quality.quality_score import compute_quality_score
from core_model.mini_brain.quality.response_formatter import format_response_text, validate_formatting
from core_model.mini_brain.quality.tamil_fluency_validator import validate_tamil_fluency

# Real prompt/response pair from MB-04A's own benchmark: the
# "workflow" question's optimized response was two disjoint verbatim
# copies of the prompt's own static Response-format/Confidence text.
REAL_WORKFLOW_PROMPT_TAIL = (
    "Response format: A short, direct paragraph. No markdown headers, no bullet lists "
    "unless the question specifically asks for steps. No code fences unless the "
    "question is about code.\n\nConfidence: high. Sufficient matching knowledge is "
    "available -- answer directly.\n\nYou must respond in English only.\n\nAnswer:"
)
REAL_WORKFLOW_ECHOED_RESPONSE = (
    "A short, direct paragraph. No markdown headers, no bullet lists unless the "
    "question specifically asks for steps. No code fences unless the question is "
    "about code. Confidence: high. Sufficient matching knowledge is available -- "
    "answer directly. You must respond"
)

# Real: the "tamil" question's optimized response was a 100% echo of
# the Tamil language directive itself, not any generated Tamil content.
REAL_TAMIL_DIRECTIVE = "இந்த கேள்விக்கு தமிழில் மட்டுமே பதிலளிக்க வேண்டும்."
REAL_TAMIL_ECHOED_RESPONSE = "இந்த கேள்விக்கு தமிழில் மட்டுமே பதிலளிக்க வே"

# Real: the "dataset" question's optimized response was genuine,
# on-topic, grounded content -- no echo.
REAL_DATASET_RESPONSE = (
    "Duplicate Detection works by checking if the dataset contains any records that "
    "have been approved for testing, and if so, then those records are considered "
    "duplicates."
)


# -- echo_detector -------------------------------------------------------

def test_detects_dominant_echo_in_real_workflow_case() -> None:
    result = detect_echo(REAL_WORKFLOW_ECHOED_RESPONSE, prompt_text=REAL_WORKFLOW_PROMPT_TAIL)
    assert result["echo_detected"] is True
    assert result["severity"] == "dominant"
    assert result["overlap_ratio"] > 0.6


def test_detects_dominant_echo_in_real_tamil_directive_case() -> None:
    result = detect_echo(REAL_TAMIL_ECHOED_RESPONSE, prompt_text=REAL_TAMIL_DIRECTIVE)
    assert result["echo_detected"] is True
    assert result["severity"] == "dominant"


def test_no_echo_for_genuine_grounded_response() -> None:
    result = detect_echo(REAL_DATASET_RESPONSE, prompt_text="Some unrelated prompt text about training.")
    assert result["echo_detected"] is False
    assert result["severity"] == "none"


def test_no_echo_when_no_prompt_provided() -> None:
    result = detect_echo("Any response text at all.", prompt_text="")
    assert result["echo_detected"] is False


def test_label_echo_detected_without_verbatim_overlap() -> None:
    result = detect_echo(
        "Primary knowledge: something. Supporting knowledge: other things. Matched items: none.",
        prompt_text="",
    )
    assert result["echo_type"] == "label_echo"
    assert len(result["matched_labels"]) >= 2


def test_short_natural_overlap_is_not_flagged_as_echo() -> None:
    # Two unrelated texts sharing only a short, ordinary phrase should
    # not trigger the (40-char) verbatim threshold.
    result = detect_echo("The dataset needs review.", prompt_text="The dataset needs approval before use.")
    assert result["echo_detected"] is False


# -- echo_cleaner ---------------------------------------------------------

def test_clean_echo_removes_overlap_and_preserves_real_content() -> None:
    text = REAL_TAMIL_DIRECTIVE + " Duplicate Detection uses hashing."
    echo = detect_echo(text, prompt_text=REAL_TAMIL_DIRECTIVE)
    cleaned = clean_echo(text, echo_diagnostics=echo)
    assert cleaned["removed"] is True
    assert "hashing" in cleaned["cleaned_text"]
    assert "தமிழில்" not in cleaned["cleaned_text"]


def test_clean_echo_never_removes_anything_when_no_overlap() -> None:
    cleaned = clean_echo("Genuine answer text.", echo_diagnostics={"overlap_text": ""})
    assert cleaned["removed"] is False
    assert cleaned["cleaned_text"] == "Genuine answer text."


def test_clean_echo_reports_insufficient_rather_than_fabricating() -> None:
    echo = detect_echo(REAL_TAMIL_ECHOED_RESPONSE, prompt_text=REAL_TAMIL_DIRECTIVE)
    cleaned = clean_echo(REAL_TAMIL_ECHOED_RESPONSE, echo_diagnostics=echo)
    assert cleaned["insufficient_after_cleaning"] is True
    assert cleaned["cleaned_text"] == ""


def test_clean_echo_iteratively_removes_multiple_disjoint_fragments() -> None:
    # Real case: the workflow response echoes the Response-format
    # sentence AND (in the full real prompt) the Confidence/language
    # directive tail -- a single clean_echo() pass only strips the
    # longest one.
    full_prompt = REAL_WORKFLOW_PROMPT_TAIL
    result = clean_echo_iteratively(REAL_WORKFLOW_ECHOED_RESPONSE, prompt_text=full_prompt)
    assert result["passes"] >= 1
    assert result["insufficient_after_cleaning"] is True


def test_clean_echo_iteratively_stops_within_pass_cap() -> None:
    result = clean_echo_iteratively("Real genuine content here.", prompt_text="Unrelated prompt.")
    assert result["passes"] == 0
    assert result["cleaned_text"] == "Real genuine content here."


# -- mixed_language_resolver -----------------------------------------------

def test_response_language_matches_expectation() -> None:
    result = resolve_response_language("This is an English response.", expected_output_language="english")
    assert result["matches_expectation"] is True


def test_response_language_mismatch_detected() -> None:
    result = resolve_response_language("This is an English response.", expected_output_language="tamil")
    assert result["matches_expectation"] is False
    assert result["resolved_output_language"] == "english"


def test_tamil_response_matches_tamil_expectation() -> None:
    result = resolve_response_language(REAL_TAMIL_ECHOED_RESPONSE, expected_output_language="tamil")
    assert result["matches_expectation"] is True


# -- tamil_fluency_validator ------------------------------------------------

def test_real_tamil_response_is_script_structurally_valid() -> None:
    # Honest finding from real testing: this response is well-formed
    # Tamil Unicode script (no broken combining sequences) even though
    # it is ALSO a pure echo (caught separately by echo_detector) --
    # script validity and "is this a real answer" are different checks.
    result = validate_tamil_fluency(REAL_TAMIL_ECHOED_RESPONSE)
    assert result["passed"] is True


def test_word_repetition_detected() -> None:
    result = validate_tamil_fluency("word word தமிழ் தமிழ் more text here")
    assert result["passed"] is False
    assert any("word_repetition" in issue for issue in result["issues"])


def test_fragment_only_answer_detected() -> None:
    result = validate_tamil_fluency("ok")
    assert result["passed"] is False
    assert "fragment_only_answer" in result["issues"]


def test_mixed_script_half_translated_detected() -> None:
    result = validate_tamil_fluency(
        "தமிழ் dataset create pannalam workflow system database integration testing"
    )
    assert result["passed"] is False
    assert "mixed_script_or_half_translated" in result["issues"]


def test_broken_orphan_vowel_sign_detected() -> None:
    # A dependent vowel sign with no preceding Tamil consonant is a
    # genuine Unicode structural violation.
    broken = "ாசெய்தி இது ஒரு சோதனை உரை ஆகும் மேலும் இது"
    result = validate_tamil_fluency(broken)
    assert any("broken_tamil_script_sequences" in issue for issue in result["issues"])


def test_excessive_punctuation_run_detected() -> None:
    result = validate_tamil_fluency("இது ஒரு சோதனை பதில் ஆகும்???!!!...")
    assert "invalid_punctuation_pattern" in result["issues"]


# -- response_formatter ------------------------------------------------------

def test_decimal_numbers_never_mangled() -> None:
    text = "The value is 3.14 and the version is 2.0 released today."
    assert validate_formatting(text)["passed"] is True
    assert format_response_text(text)["formatted_text"] == text


def test_missing_space_after_punctuation_detected_and_fixed() -> None:
    text = "First point.Second point."
    assert validate_formatting(text)["passed"] is False
    formatted = format_response_text(text)
    assert formatted["formatted_text"] == "First point. Second point."


def test_excessive_blank_lines_collapsed() -> None:
    text = "Line one\n\n\n\nLine two"
    formatted = format_response_text(text)
    assert formatted["formatted_text"] == "Line one\n\nLine two"
    assert "collapsed_blank_lines" in formatted["changes"]


def test_bullet_markers_normalized() -> None:
    text = "* item one\n* item two\n- item three"
    formatted = format_response_text(text)
    assert formatted["formatted_text"] == "- item one\n- item two\n- item three"


def test_formatting_never_changes_word_content() -> None:
    text = "word   with    extra   spaces and PascalCase and snake_case_words"
    formatted = format_response_text(text)
    original_words = set(text.split())
    formatted_words = set(formatted["formatted_text"].split())
    assert original_words == formatted_words


# -- consistency_validator ---------------------------------------------------

def test_grounded_response_passes() -> None:
    plan = {
        "confidence_band": "high",
        "validated_knowledge": {"primary": ["Duplicate Detection"], "supporting": []},
        "validated_context": {"matched_items": []},
    }
    result = validate_consistency(response_text=REAL_DATASET_RESPONSE, response_plan=plan)
    assert result["passed"] is True


def test_ungrounded_response_flagged() -> None:
    plan = {
        "confidence_band": "high",
        "validated_knowledge": {"primary": ["Tokenizer Training"], "supporting": []},
        "validated_context": {"matched_items": []},
    }
    result = validate_consistency(response_text="This talks about something else entirely.", response_plan=plan)
    assert "response_not_grounded_in_provided_knowledge" in result["issues"]


def test_high_confidence_without_knowledge_flagged() -> None:
    plan = {
        "confidence_band": "high",
        "validated_knowledge": {"primary": [], "supporting": []},
        "validated_context": {"matched_items": []},
    }
    result = validate_consistency(response_text="Some answer.", response_plan=plan)
    assert "confidence_without_backing_knowledge" in result["issues"]


def test_forbidden_claim_detected() -> None:
    plan = {"confidence_band": "high", "validated_knowledge": {"primary": ["X"], "supporting": []}, "validated_context": {}}
    result = validate_consistency(response_text="I have started training the model now, X.", response_plan=plan)
    assert any("forbidden_claim" in issue for issue in result["issues"])


def test_disclaimers_not_preserved_flagged() -> None:
    plan = {
        "confidence_band": "none", "validated_knowledge": {"primary": [], "supporting": []},
        "validated_context": {}, "disclaimers": ["Admin-only guidance."],
    }
    result = validate_consistency(
        response_text="Some answer.", response_plan=plan, final_response={"disclaimers": []},
    )
    assert "disclaimers_not_preserved" in result["issues"]


def test_disclaimers_preserved_passes() -> None:
    plan = {
        "confidence_band": "none", "validated_knowledge": {"primary": [], "supporting": []},
        "validated_context": {}, "disclaimers": ["Admin-only guidance."],
    }
    result = validate_consistency(
        response_text="Some answer.", response_plan=plan,
        final_response={"disclaimers": ["Admin-only guidance."]},
    )
    assert result["passed"] is True


# -- quality_score -------------------------------------------------------------

def _passing_diagnostics(**overrides):
    base = {
        "echo_result": {"echo_detected": False, "overlap_ratio": 0.0, "severity": "none"},
        "language_result": {"matches_expectation": True},
        "tamil_result": None,
        "formatting_result": {"issues": []},
        "consistency_result": {"issues": []},
    }
    base.update(overrides)
    return base


def test_all_passing_gives_overall_100() -> None:
    score = compute_quality_score(**_passing_diagnostics())
    assert score["overall_quality"] == 100


def test_dominant_echo_caps_overall_score() -> None:
    diagnostics = _passing_diagnostics(
        echo_result={"echo_detected": True, "overlap_ratio": 0.95, "severity": "dominant"},
    )
    score = compute_quality_score(**diagnostics)
    assert score["echo_score"] <= 10
    assert score["overall_quality"] <= score["echo_score"]


def test_language_mismatch_zeroes_language_score() -> None:
    diagnostics = _passing_diagnostics(language_result={"matches_expectation": False})
    score = compute_quality_score(**diagnostics)
    assert score["language_score"] == 0


def test_tamil_score_is_none_when_not_applicable() -> None:
    score = compute_quality_score(**_passing_diagnostics())
    assert score["tamil_score"] is None


def test_scores_never_go_negative() -> None:
    diagnostics = _passing_diagnostics(
        consistency_result={"issues": ["a", "b", "c", "d", "e", "f"]},
    )
    score = compute_quality_score(**diagnostics)
    assert score["consistency_score"] == 0
