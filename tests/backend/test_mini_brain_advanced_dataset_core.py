"""MB-05.1: pure-module unit tests for core_model/mini_brain/dataset_advanced/."""

from core_model.mini_brain.dataset_advanced.advanced_dataset_score import compute_advanced_scores
from core_model.mini_brain.dataset_advanced.curriculum_analyzer import analyze_curriculum
from core_model.mini_brain.dataset_advanced.dataset_bias_analyzer import analyze_bias
from core_model.mini_brain.dataset_advanced.dataset_conflict_analyzer import detect_conflicts
from core_model.mini_brain.dataset_advanced.dataset_coverage_analyzer import analyze_coverage
from core_model.mini_brain.dataset_advanced.dataset_difficulty_analyzer import analyze_difficulty, difficulty_for_text
from core_model.mini_brain.dataset_advanced.dataset_graph_builder import build_graph
from core_model.mini_brain.dataset_advanced.dataset_priority_engine import rank_priorities
from core_model.mini_brain.dataset_advanced.dataset_risk_analyzer import analyze_risk
from core_model.mini_brain.dataset_advanced.knowledge_gap_analyzer import analyze_knowledge_gaps


def _r(i, *, instruction=None, output_text=None, record_type="instruction", metadata=None):
    return {"public_id": f"r{i}", "record_type": record_type, "language": "en", "instruction": instruction, "input_text": None, "output_text": output_text, "metadata": metadata or {}}


# -- dataset_conflict_analyzer -----------------------------------------------

def test_conflict_detected_for_same_question_different_answers() -> None:
    records = [
        _r(0, instruction="What is Python used for?", output_text="Scripting and web backends."),
        _r(1, instruction="What is Python used for?", output_text="Only for console games."),
    ]
    result = detect_conflicts(records)
    assert result["conflict_count"] == 1
    assert len(result["conflict_groups"][0]["distinct_answers"]) == 2


def test_no_conflict_for_same_question_same_answer() -> None:
    records = [
        _r(0, instruction="What is Python?", output_text="A programming language."),
        _r(1, instruction="What is Python?", output_text="A programming language."),
    ]
    result = detect_conflicts(records)
    assert result["conflict_count"] == 0


def test_no_conflict_for_different_questions() -> None:
    records = [_r(0, instruction="Q1", output_text="A1"), _r(1, instruction="Q2", output_text="A2")]
    result = detect_conflicts(records)
    assert result["conflict_count"] == 0


# -- dataset_bias_analyzer -----------------------------------------------------

def test_heavy_bias_detected_for_dominant_language() -> None:
    result = analyze_bias(records=[], language_counts={"english": 95, "tamil": 5}, record_type_counts={}, domain_topic_scores={})
    assert result["language_balance"]["verdict"] == "Heavy Bias"


def test_balanced_verdict_for_even_distribution() -> None:
    result = analyze_bias(records=[], language_counts={"english": 50, "tamil": 50}, record_type_counts={}, domain_topic_scores={})
    assert result["language_balance"]["verdict"] == "Balanced"


def test_slight_bias_verdict() -> None:
    result = analyze_bias(records=[], language_counts={"english": 65, "tamil": 35}, record_type_counts={}, domain_topic_scores={})
    assert result["language_balance"]["verdict"] == "Slight Bias"


def test_category_balance_from_metadata() -> None:
    records = [_r(i, metadata={"topic": "math"}) for i in range(10)]
    result = analyze_bias(records=records, language_counts={}, record_type_counts={}, domain_topic_scores={})
    assert result["category_balance"]["verdict"] == "Heavy Bias"
    assert result["category_balance"]["dominant"] == "math"


# -- dataset_coverage_analyzer ------------------------------------------------

def test_coverage_marks_subtopic_covered_with_enough_hits() -> None:
    records = [_r(i, instruction="Tell me about python", output_text="pip install requests") for i in range(5)]
    result = analyze_coverage(records)
    assert result["Programming"]["subtopics"]["Python"]["status"] == "Covered"


def test_coverage_marks_subtopic_missing_with_zero_hits() -> None:
    records = [_r(i, instruction="unrelated content here", output_text="nothing technical") for i in range(5)]
    result = analyze_coverage(records)
    assert result["Programming"]["subtopics"]["Rust"]["status"] == "Missing"


def test_coverage_weak_with_one_or_two_hits() -> None:
    records = [_r(0, instruction="rust cargo build basics", output_text="ok")]
    result = analyze_coverage(records)
    assert result["Programming"]["subtopics"]["Rust"]["status"] == "Weak"


# -- dataset_difficulty_analyzer -----------------------------------------------

def test_difficulty_easy_for_short_simple_text() -> None:
    assert difficulty_for_text("This is short.") == "Easy"


def test_difficulty_very_hard_for_long_advanced_text() -> None:
    text = (
        "This is an extensive discussion of asymptotic eigenvalue analysis in stochastic "
        "differential equations, exploring homomorphism properties across concurrency models "
        "with detailed thermodynamics-inspired quantum recursion frameworks and combinatorial "
        "topology considerations that span many words to exceed the length threshold for this "
        "particular difficulty classification rule used throughout this deterministic module."
    )
    assert difficulty_for_text(text) == "Very Hard"


def test_difficulty_empty_text_is_easy() -> None:
    assert difficulty_for_text("") == "Easy"


def test_analyze_difficulty_distribution_sums_to_total() -> None:
    records = [_r(i, output_text="short text") for i in range(5)]
    result = analyze_difficulty(records)
    assert sum(result["distribution"].values()) == 5


# -- curriculum_analyzer -----------------------------------------------------

def test_curriculum_good_sequence_with_easy_and_hard() -> None:
    coverage = {"Programming": {"subtopics": {"Python": {"status": "Covered", "record_hits": 2, "matched_record_ids": ["r0", "r1"]}}, "coverage_percent": 100.0}}
    difficulty_by_id = {"r0": "Easy", "r1": "Hard"}
    result = analyze_curriculum(coverage=coverage, difficulty_by_id=difficulty_by_id)
    assert result["topics"][0]["verdict"] == "Good Sequence"


def test_curriculum_missing_prerequisite_when_only_hard() -> None:
    coverage = {"Programming": {"subtopics": {"Python": {"status": "Covered", "record_hits": 1, "matched_record_ids": ["r0"]}}, "coverage_percent": 100.0}}
    difficulty_by_id = {"r0": "Very Hard"}
    result = analyze_curriculum(coverage=coverage, difficulty_by_id=difficulty_by_id)
    assert result["topics"][0]["verdict"] == "Missing Prerequisite"


def test_curriculum_skips_missing_subtopics() -> None:
    coverage = {"Programming": {"subtopics": {"Rust": {"status": "Missing", "record_hits": 0, "matched_record_ids": []}}, "coverage_percent": 0.0}}
    result = analyze_curriculum(coverage=coverage, difficulty_by_id={})
    assert result["topics"] == []


# -- knowledge_gap_analyzer ----------------------------------------------------

def test_knowledge_gap_detects_missing_topics() -> None:
    records = [_r(0, instruction="python programming", output_text="code stuff")]
    result = analyze_knowledge_gaps(records)
    topics = {gap["topic"] for gap in result["missing_topics"]}
    assert "Astronomy" in topics
    assert "Geometry" in topics


def test_knowledge_gap_covered_topic_excluded_from_missing() -> None:
    records = [_r(0, instruction="explain astronomy and the solar system", output_text="planets orbit stars")]
    result = analyze_knowledge_gaps(records)
    missing_topics = {gap["topic"] for gap in result["missing_topics"]}
    assert "Astronomy" not in missing_topics


# -- dataset_risk_analyzer ---------------------------------------------------

def test_risk_detects_email_and_api_key() -> None:
    records = [_r(0, instruction="contact info", output_text="email me at test@example.com, api_key=sk-verysecretvalue1234567890")]
    result = analyze_risk(records)
    assert result["risk_item_count"] >= 1
    categories = {item["category"] for item in result["risk_items"]}
    assert "email_address" in categories or "api_key" in categories


def test_risk_zero_for_clean_records() -> None:
    records = [_r(0, instruction="What is a dataset?", output_text="A collection of structured records.")]
    result = analyze_risk(records)
    assert result["risk_item_count"] == 0
    assert result["risk_score"] == 0.0


# -- dataset_graph_builder ----------------------------------------------------

def test_graph_builds_nodes_and_edges_from_coverage() -> None:
    coverage = {"Programming": {"subtopics": {"Python": {"status": "Covered", "record_hits": 1, "matched_record_ids": ["r0"]}}, "coverage_percent": 100.0}}
    records_by_id = {"r0": {"instruction": "What is Python?", "output_text": "A language."}}
    result = build_graph(coverage=coverage, records_by_id=records_by_id)
    assert result["node_count"] > 0
    types = {node["type"] for node in result["nodes"]}
    assert types == {"topic", "subtopic", "lesson", "question", "answer"}


def test_graph_skips_missing_subtopics() -> None:
    coverage = {"Programming": {"subtopics": {"Rust": {"status": "Missing", "record_hits": 0, "matched_record_ids": []}}, "coverage_percent": 0.0}}
    result = build_graph(coverage=coverage, records_by_id={})
    subtopic_nodes = [n for n in result["nodes"] if n["type"] == "subtopic"]
    assert subtopic_nodes == []


# -- dataset_priority_engine -------------------------------------------------

def test_priority_ranks_critical_risk_first() -> None:
    conflicts = {"conflict_count": 0, "conflict_score": 0.0, "reason": "none"}
    bias = {}
    curriculum = {"topics": []}
    knowledge_gaps = {"missing_topics": []}
    risk = {"risk_item_count": 1, "risk_items": [{"severity": "critical"}], "reason": "found a secret"}
    result = rank_priorities(conflicts=conflicts, bias=bias, curriculum=curriculum, knowledge_gaps=knowledge_gaps, risk=risk)
    assert result[0]["priority"] == "Critical"


def test_priority_sorted_by_severity_order() -> None:
    conflicts = {"conflict_count": 1, "conflict_score": 0.5, "reason": "conflict found"}
    bias = {"language_balance": {"verdict": "Heavy Bias", "reason": "skewed"}}
    curriculum = {"topics": []}
    knowledge_gaps = {"missing_topics": [{"topic": "Geometry", "reason": "0 hits"}]}
    risk = {"risk_item_count": 0, "risk_items": [], "reason": "none"}
    result = rank_priorities(conflicts=conflicts, bias=bias, curriculum=curriculum, knowledge_gaps=knowledge_gaps, risk=risk)
    priorities_seen = [item["priority"] for item in result]
    assert priorities_seen == sorted(priorities_seen, key=lambda p: {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}[p])


# -- advanced_dataset_score --------------------------------------------------

def _empty_inputs():
    return dict(
        conflicts={"conflict_score": 0.0}, bias={}, coverage={}, difficulty={"distribution": {}},
        curriculum={"topics": []}, knowledge_gaps={"coverage_ratio": 1.0}, risk={"risk_score": 0.0},
    )


def test_every_advanced_score_has_formula_calculation_reason() -> None:
    scores = compute_advanced_scores(**_empty_inputs())
    for name, entry in scores.items():
        assert entry["formula"]
        assert entry["calculation"]
        assert entry["reason"]
        assert 0 <= entry["score"] <= 100


def test_overall_is_unweighted_mean_of_eight_components() -> None:
    scores = compute_advanced_scores(**_empty_inputs())
    component_scores = [scores[k]["score"] for k in ("coverage", "consistency", "conflict", "bias", "difficulty", "curriculum", "knowledge_gap", "risk")]
    assert scores["overall"]["score"] == round(sum(component_scores) / len(component_scores))


def test_high_risk_lowers_risk_score() -> None:
    inputs = _empty_inputs()
    inputs["risk"] = {"risk_score": 1.0}
    scores = compute_advanced_scores(**inputs)
    assert scores["risk"]["score"] == 0
