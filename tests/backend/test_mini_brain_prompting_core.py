"""MB-04A: pure-module unit tests for core_model/mini_brain/prompting/.

No I/O, no model, no database -- every test here is a plain function
call against deterministic logic.
"""

from core_model.mini_brain.prompting.context_builder import build_context
from core_model.mini_brain.prompting.knowledge_compressor import compress_knowledge, dedupe_texts
from core_model.mini_brain.prompting.language_detector import detect_language, resolve_output_language
from core_model.mini_brain.prompting.prompt_builder import build_prompt, rebuild_with_stronger_language_directive
from core_model.mini_brain.prompting.prompt_templates import (
    TEMPLATES,
    select_template_category,
    template_text,
)
from core_model.mini_brain.prompting.response_validator import validate_response
from core_model.mini_brain.prompting.tanglish_normalizer import normalization_coverage, normalize_tanglish


# -- language_detector -------------------------------------------------------

def test_detects_pure_english() -> None:
    analysis = detect_language("How should tokenizer training begin?")
    assert analysis["language"] == "english"
    assert resolve_output_language(analysis) == "english"


def test_detects_pure_tamil() -> None:
    analysis = detect_language("தமிழில் dataset எப்படி உருவாக்குவது?")
    assert analysis["language"] == "tamil"
    assert resolve_output_language(analysis) == "tamil"


def test_detects_tanglish_via_keyword_signal() -> None:
    analysis = detect_language("dataset epadi prepare pannalam?")
    assert analysis["language"] == "tanglish"
    assert analysis["tanglish_signal_words"] == ["epadi", "pannalam"]
    assert resolve_output_language(analysis) == "tamil"


def test_pure_latin_with_no_tanglish_words_is_english() -> None:
    analysis = detect_language("What is the current schema version for the database?")
    assert analysis["language"] == "english"


def test_mixed_dominance_uses_effective_tamil_ratio() -> None:
    # Low raw Tamil-script ratio but heavy Tanglish word content --
    # effective_tamil_ratio should push this to a Tamil resolution.
    analysis = detect_language("எப்படி dataset create pannalam, konjam help pannunga")
    assert analysis["language"] == "mixed"
    assert analysis["effective_tamil_ratio"] > analysis["tamil_ratio"]
    assert resolve_output_language(analysis) == "tamil"


def test_empty_string_defaults_to_english_without_crashing() -> None:
    analysis = detect_language("")
    assert analysis["language"] == "english"


# -- tanglish_normalizer ------------------------------------------------------

def test_normalizes_known_tanglish_words_to_tamil() -> None:
    result = normalize_tanglish("dataset epadi prepare pannalam?")
    assert "எப்படி" in result
    assert "பண்ணலாம்" in result
    assert "epadi" not in result.lower()


def test_normalizer_preserves_unmatched_words_and_punctuation() -> None:
    result = normalize_tanglish("Hello xyz123 epadi?")
    assert "Hello" in result
    assert "xyz123" in result
    assert "?" in result


def test_normalization_coverage_reports_unmatched_words() -> None:
    coverage = normalization_coverage("dataset epadi wobblesnort pannalam")
    assert coverage["matched_word_count"] == 3
    assert "wobblesnort" in coverage["unmatched_words"]


# -- knowledge_compressor -----------------------------------------------------

def test_dedupe_removes_case_and_whitespace_variants() -> None:
    out = dedupe_texts(["Hello  world", "hello world", "HELLO WORLD", "Something else"])
    assert out == ["Hello  world", "Something else"]


def test_compress_knowledge_collapses_repeated_words() -> None:
    out = compress_knowledge(["this this is is a a test"], max_chars=1000)
    assert out == ["this is a test"]


def test_compress_knowledge_respects_budget_by_dropping_lower_priority_items() -> None:
    texts = ["A" * 50, "B" * 50, "C" * 50]
    out = compress_knowledge(texts, max_chars=60)
    # first item survives intact, second gets truncated or dropped, third dropped
    assert out[0] == "A" * 50
    assert sum(len(t) for t in out) <= 60


def test_compress_knowledge_never_exceeds_budget_even_for_one_long_item() -> None:
    out = compress_knowledge(["word. " * 500], max_chars=100)
    assert sum(len(t) for t in out) <= 100


def test_compress_knowledge_empty_list_returns_empty() -> None:
    assert compress_knowledge([], max_chars=500) == []


# -- context_builder -----------------------------------------------------------

_MINIMAL_PLAN = {
    "validated_workflow": {"current_step": "Tokenizer Training", "next_steps": ["Bounded Pretraining"], "dependencies": []},
    "disclaimers": ["Admin-only guidance."],
}


def test_context_builder_always_includes_primary_within_budget() -> None:
    context = build_context(_MINIMAL_PLAN, primary_texts=["Primary A"], supporting_texts=[], total_budget_chars=500)
    assert context["primary"] == ["Primary A"]


def test_context_builder_drops_supporting_when_budget_exhausted_by_primary() -> None:
    context = build_context(
        _MINIMAL_PLAN, primary_texts=["A" * 500], supporting_texts=["Supporting B"], total_budget_chars=500,
    )
    assert context["supporting"] == []


def test_context_builder_includes_supporting_when_budget_allows() -> None:
    context = build_context(
        _MINIMAL_PLAN, primary_texts=["Primary A"], supporting_texts=["Supporting B"], total_budget_chars=500,
    )
    assert context["supporting"] == ["Supporting B"]


def test_context_builder_optional_only_used_after_primary_and_supporting() -> None:
    context = build_context(
        _MINIMAL_PLAN, primary_texts=["Primary A"], supporting_texts=["Supporting B"],
        optional_texts=["Optional C"], total_budget_chars=500,
    )
    assert context["optional"] == ["Optional C"]

    tight = build_context(
        _MINIMAL_PLAN, primary_texts=["A" * 480], supporting_texts=["B" * 480],
        optional_texts=["Optional C"], total_budget_chars=500,
    )
    assert tight["optional"] == []


def test_context_builder_extracts_workflow_and_rules() -> None:
    context = build_context(_MINIMAL_PLAN, primary_texts=[], supporting_texts=[], total_budget_chars=500)
    assert any("Tokenizer Training" in line for line in context["workflow_lines"])
    assert context["rules_lines"] == ["Admin-only guidance."]


# -- prompt_templates -----------------------------------------------------------

def test_domain_intent_selects_matching_template() -> None:
    assert select_template_category(intent="dataset", question_type="howto", question="x") == "dataset"
    assert select_template_category(intent="rag", question_type="definition", question="x") == "rag"


def test_coding_signal_used_when_intent_has_no_domain_match() -> None:
    category = select_template_category(
        intent="unknown", question_type="general", question="How do I fix this Python function bug?",
    )
    assert category == "coding"


def test_question_type_fallback_when_no_domain_or_coding_signal() -> None:
    assert select_template_category(intent="unknown", question_type="definition", question="What is a widget?") == "definition"
    assert select_template_category(intent="unknown", question_type="troubleshooting", question="Why is this failing?") == "troubleshooting"


def test_unrecognized_category_falls_back_to_default_text() -> None:
    assert template_text("not-a-real-category") == TEMPLATES["default"]


# -- prompt_builder --------------------------------------------------------------

def test_build_prompt_contains_all_required_sections() -> None:
    context = build_context(_MINIMAL_PLAN, primary_texts=["Item A"], supporting_texts=[], total_budget_chars=500)
    prompt = build_prompt(
        question="How do I create a dataset?", template_text=TEMPLATES["dataset"], context=context,
        output_language="english", confidence_band="high", intent="dataset",
    )
    for required in ("Role:", "Task:", "Knowledge:", "Workflow:", "Rules:", "Expected response language:", "Response format:", "Confidence:"):
        assert required in prompt


def test_build_prompt_repeats_language_directive_for_primacy_and_recency() -> None:
    context = build_context(_MINIMAL_PLAN, primary_texts=[], supporting_texts=[], total_budget_chars=500)
    prompt = build_prompt(
        question="Tamil question", template_text=TEMPLATES["default"], context=context,
        output_language="tamil", confidence_band="none", intent="unknown",
    )
    assert prompt.count("Respond ONLY in Tamil") == 2


def test_rebuild_adds_stronger_directive_and_keeps_answer_cue() -> None:
    context = build_context(_MINIMAL_PLAN, primary_texts=[], supporting_texts=[], total_budget_chars=500)
    prompt = build_prompt(
        question="q", template_text=TEMPLATES["default"], context=context,
        output_language="tamil", confidence_band="none", intent="unknown",
    )
    rebuilt = rebuild_with_stronger_language_directive(prompt, output_language="tamil")
    assert rebuilt.endswith("Answer:")
    assert "IMPORTANT" in rebuilt
    assert rebuilt.count("Respond ONLY in Tamil") == 3


# -- response_validator -----------------------------------------------------------

def test_validator_passes_when_language_matches() -> None:
    result = validate_response("This is an English answer.", expected_output_language="english", confidence_band="high")
    assert result["passed"] is True


def test_validator_flags_language_mismatch() -> None:
    result = validate_response("This is an English answer.", expected_output_language="tamil", confidence_band="high")
    assert result["passed"] is False
    assert any("language_mismatch" in issue for issue in result["issues"])


def test_validator_flags_self_claimed_restricted_action() -> None:
    result = validate_response(
        "I have started training the model now.", expected_output_language="english", confidence_band="high",
    )
    assert result["passed"] is False
    assert any("self_claimed_restricted_action" in issue for issue in result["issues"])


def test_validator_flags_overconfidence_when_confidence_is_low() -> None:
    result = validate_response(
        "This definitely always works and is guaranteed.", expected_output_language="english", confidence_band="none",
    )
    assert result["passed"] is False
    assert any("overconfident" in issue for issue in result["issues"])


def test_validator_allows_confident_language_when_confidence_is_high() -> None:
    result = validate_response(
        "This definitely works as described.", expected_output_language="english", confidence_band="high",
    )
    assert result["passed"] is True
