"""MB-04C: pure-module unit tests for core_model/mini_brain/capability/.

Several cases are drawn directly from MB-04A's own real benchmark data
(10 questions against the real Qwen2.5-0.5B-Instruct model), used as
ground truth rather than synthetic examples.
"""

from core_model.mini_brain.capability.capability_selector import CATEGORIES, select_capability_category
from core_model.mini_brain.capability.generation_strategy import STRATEGIES, select_strategy
from core_model.mini_brain.capability.model_profiles import GENERIC_UNKNOWN_PROFILE, get_profile, list_profiles
from core_model.mini_brain.capability.output_length_controller import evaluate_output_length
from core_model.mini_brain.capability.retry_strategy import should_retry
from core_model.mini_brain.capability.stability_checker import check_stability

# Real MB-04A responses (Qwen2.5-0.5B-Instruct, real model)
REAL_DATASET_RESPONSE = (
    "Duplicate Detection works by checking if the dataset contains any records that "
    "have been approved for testing, and if so, then those records are considered "
    "duplicates. The system then uses these records to determine the final decision "
    "on whether the test is valid or not"
)
REAL_TAMIL_ECHOED_RESPONSE = "இந்த கேள்விக்கு தமிழில் மட்டுமே பதிலளிக்க வே"


# -- model_profiles ------------------------------------------------------

def test_qwen_profile_is_verified_with_real_measurements() -> None:
    profile = get_profile("Qwen2.5-0.5B-Instruct", "Q4_K_M")
    assert profile["verified"] is True
    assert profile["matched_key"] == "qwen2.5-0.5b-instruct"
    assert profile["measured_tokens_per_second"] is not None


def test_tinyllama_profile_is_explicitly_unverified() -> None:
    profile = get_profile("TinyLlama-1.1B-Chat", "Q4_K_M")
    assert profile["verified"] is False
    assert "never downloaded or run" in profile["source"]


def test_unknown_model_gets_generic_conservative_profile() -> None:
    profile = get_profile("SomeBrandNewModel-7B", "Q8_0")
    assert profile["verified"] is False
    assert profile["matched_key"] is None
    assert profile["display_name"] == GENERIC_UNKNOWN_PROFILE["display_name"]


def test_get_profile_handles_none_gracefully() -> None:
    profile = get_profile(None, None)
    assert profile["verified"] is False


def test_list_profiles_returns_both_known_models() -> None:
    profiles = list_profiles()
    assert "qwen2.5-0.5b-instruct" in profiles
    assert "tinyllama-1.1b-chat" in profiles


# -- capability_selector ---------------------------------------------------

def test_dataset_intent_selects_dataset_category() -> None:
    assert select_capability_category(intent="dataset", question="x", has_knowledge=True) == "dataset"


def test_coding_signal_used_when_no_domain_intent() -> None:
    category = select_capability_category(
        intent="unknown", question="How do I fix this Python function bug?", has_knowledge=False,
    )
    assert category == "coding"


def test_knowledge_question_when_knowledge_found_but_no_domain_intent() -> None:
    category = select_capability_category(intent="unknown", question="Tell me more please", has_knowledge=True)
    assert category == "knowledge_question"


def test_simple_question_fallback() -> None:
    category = select_capability_category(intent="unknown", question="hello", has_knowledge=False)
    assert category == "simple_question"


def test_all_declared_categories_are_reachable() -> None:
    # Every category in CATEGORIES should be producible by some input.
    reachable = {
        select_capability_category(intent="dataset", question="x", has_knowledge=True),
        select_capability_category(intent="training", question="x", has_knowledge=True),
        select_capability_category(intent="rag", question="x", has_knowledge=True),
        select_capability_category(intent="architecture", question="x", has_knowledge=True),
        select_capability_category(intent="workflow", question="x", has_knowledge=True),
        select_capability_category(intent="unknown", question="fix this python bug", has_knowledge=False),
        select_capability_category(intent="unknown", question="x", has_knowledge=True),
        select_capability_category(intent="unknown", question="x", has_knowledge=False),
    }
    assert reachable == set(CATEGORIES)


# -- generation_strategy -----------------------------------------------------

def test_question_type_takes_priority_over_category() -> None:
    strategy = select_strategy(category="dataset", question_type="definition")
    assert strategy["name"] == "definition"


def test_category_decides_when_question_type_is_general() -> None:
    strategy = select_strategy(category="coding", question_type="general")
    assert strategy["name"] == "code"


def test_all_ten_strategies_are_selectable() -> None:
    reachable = {
        select_strategy(category="c", question_type="definition")["name"],
        select_strategy(category="c", question_type="comparison")["name"],
        select_strategy(category="c", question_type="troubleshooting")["name"],
        select_strategy(category="c", question_type="procedural")["name"],
        select_strategy(category="coding", question_type="general")["name"],
        select_strategy(category="architecture", question_type="general")["name"],
        select_strategy(category="workflow", question_type="general")["name"],
        select_strategy(category="simple_question", question_type="general")["name"],
        select_strategy(category="knowledge_question", question_type="general")["name"],
        select_strategy(category="totally_unknown", question_type="general")["name"],
    }
    assert reachable == set(STRATEGIES.keys())


def test_every_strategy_has_a_max_tokens_and_directive() -> None:
    for name, strategy in STRATEGIES.items():
        assert strategy["max_tokens"] > 0
        assert strategy["directive"]


# -- output_length_controller ------------------------------------------------

def test_real_dataset_response_correctly_flagged_cut_off() -> None:
    result = evaluate_output_length(
        REAL_DATASET_RESPONSE, stop_reason="length", target_max_tokens=48, tokens_generated=48,
    )
    assert "cut_off" in result["issues"]


def test_natural_stop_with_proper_ending_not_flagged() -> None:
    result = evaluate_output_length(
        "This is a complete answer.", stop_reason="stop", target_max_tokens=48, tokens_generated=6,
    )
    assert result["issues"] == []


def test_small_token_overshoot_not_flagged_too_long() -> None:
    # Real observed llama.cpp behavior: 49 tokens generated against a
    # 48-token request -- a normal off-by-one, not a real problem.
    result = evaluate_output_length(
        "A short complete sentence here that ends properly.",
        stop_reason="stop", target_max_tokens=48, tokens_generated=49,
    )
    assert "too_long" not in result["issues"]


def test_large_overshoot_flagged_too_long() -> None:
    result = evaluate_output_length(
        "text", stop_reason="stop", target_max_tokens=48, tokens_generated=200,
    )
    assert "too_long" in result["issues"]


def test_empty_text_flagged_too_short() -> None:
    result = evaluate_output_length("", stop_reason="stop", target_max_tokens=48, tokens_generated=0)
    assert "too_short" in result["issues"]


def test_dangling_word_ending_flagged_unfinished() -> None:
    result = evaluate_output_length(
        "The process depends on the", stop_reason="stop", target_max_tokens=48, tokens_generated=6,
    )
    assert "unfinished" in result["issues"]


# -- retry_strategy --------------------------------------------------------

def test_blocked_response_never_retries() -> None:
    decision = should_retry(length_issues=["cut_off"], echo_severity="dominant", blocked=True, forbidden_claim_detected=False)
    assert decision["retry"] is False
    assert decision["reason"] == "blocked_response_never_retried"


def test_forbidden_claim_never_retries() -> None:
    decision = should_retry(length_issues=[], echo_severity="none", blocked=False, forbidden_claim_detected=True)
    assert decision["retry"] is False


def test_cut_off_triggers_retry_with_token_bump() -> None:
    decision = should_retry(length_issues=["cut_off"], echo_severity="none", blocked=False, forbidden_claim_detected=False)
    assert decision["retry"] is True
    assert decision["bump_tokens"] is True


def test_dominant_echo_triggers_retry_without_token_bump() -> None:
    decision = should_retry(length_issues=[], echo_severity="dominant", blocked=False, forbidden_claim_detected=False)
    assert decision["retry"] is True
    assert decision["bump_tokens"] is False


def test_clean_response_never_retries() -> None:
    decision = should_retry(length_issues=[], echo_severity="none", blocked=False, forbidden_claim_detected=False)
    assert decision["retry"] is False


# -- stability_checker --------------------------------------------------------

def test_stability_passes_for_similar_answers() -> None:
    result = check_stability(
        first_text="The dataset system uses hashing for duplicate detection.",
        retry_text="Duplicate detection in the dataset system uses hashing.",
        prompt_text="",
    )
    assert result["passed"] is True


def test_stability_flags_empty_retry() -> None:
    result = check_stability(first_text="A real answer here.", retry_text="", prompt_text="")
    assert "empty_output_on_retry" in result["issues"]


def test_stability_flags_low_overlap_as_possible_instability() -> None:
    result = check_stability(
        first_text="The dataset uses hashing for duplicate detection and validation checks.",
        retry_text="Completely different unrelated words about something else entirely today.",
        prompt_text="",
    )
    assert "low_overlap_possible_instability" in result["issues"]


def test_stability_flags_echo_persisting_on_retry() -> None:
    prompt = "Role: You are an assistant.\n\nTask: explain things.\n\nAnswer:"
    result = check_stability(first_text="First real answer.", retry_text=prompt, prompt_text=prompt)
    assert "echo_persisted_on_retry" in result["issues"]
