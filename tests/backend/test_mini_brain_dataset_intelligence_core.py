"""MB-05: pure-module unit tests for core_model/mini_brain/dataset_intelligence/."""

from core_model.mini_brain.dataset_intelligence.dataset_analyzer import analyze_dataset
from core_model.mini_brain.dataset_intelligence.domain_classifier import CATEGORIES, classify_domain
from core_model.mini_brain.dataset_intelligence.duplicate_analyzer import analyze_duplicates
from core_model.mini_brain.dataset_intelligence.language_analyzer import analyze_language
from core_model.mini_brain.dataset_intelligence.quality_analyzer import analyze_quality
from core_model.mini_brain.dataset_intelligence.rag_readiness import assess_rag_readiness
from core_model.mini_brain.dataset_intelligence.recommendation_engine import generate_recommendations
from core_model.mini_brain.dataset_intelligence.score_engine import compute_scores
from core_model.mini_brain.dataset_intelligence.sft_readiness import assess_sft_readiness
from core_model.mini_brain.dataset_intelligence.token_estimator import estimate_dataset_tokens, estimate_tokens
from core_model.mini_brain.dataset_intelligence.training_readiness import assess_training_readiness

SOURCE = {"public_id": "src1", "name": "Tamil Instructions", "source_type": "manual", "language": "ta", "status": "active", "licence_status": "verified"}


def _record(i, *, record_type="instruction", language="ta", instruction=None, output_text=None, metadata=None, content_hash=None, source_public_id="src1"):
    return {
        "public_id": f"r{i}", "source_public_id": source_public_id, "record_type": record_type, "language": language,
        "instruction": instruction, "input_text": None, "output_text": output_text,
        "metadata": metadata or {}, "content_hash": content_hash or f"hash{i}",
    }


def _good_tamil_records(n=60):
    return [
        _record(
            i,
            instruction=f"தமிழில் dataset {i} உருவாக்குவது எப்படி?",
            output_text=f"இது பதில் எண் {i} — dataset உருவாக்க பல படிகள் உள்ளன, தரவு சேகரிப்பு மற்றும் சரிபார்ப்பு தேவை.",
            metadata={"topic": "dataset"},
        )
        for i in range(n)
    ]


# -- dataset_analyzer -------------------------------------------------------

def test_analyze_dataset_counts_and_populated_fields() -> None:
    records = [_record(0, output_text="hi"), _record(1, instruction=None, output_text=None)]
    result = analyze_dataset(source=SOURCE, records=records)
    assert result["record_count"] == 2
    assert result["populated_fields"]["output_text"]["populated"] == 1
    assert result["populated_fields"]["output_text"]["empty"] == 1
    assert result["source"]["file_type"] == "manual"


def test_analyze_dataset_metadata_keys_observed() -> None:
    records = [_record(0, metadata={"topic": "x", "difficulty": "easy"}), _record(1, metadata={"topic": "y"})]
    result = analyze_dataset(source=SOURCE, records=records)
    assert result["metadata_keys_observed"] == ["difficulty", "topic"]


def test_analyze_dataset_empty_records() -> None:
    result = analyze_dataset(source=SOURCE, records=[])
    assert result["record_count"] == 0


# -- quality_analyzer ---------------------------------------------------------

def test_quality_analyzer_flags_empty_content() -> None:
    records = [_record(0, instruction=None, output_text=None), _record(1, output_text="A real answer here.")]
    result = analyze_quality(source_public_id="src1", records=records)
    assert result["empty_content_records"] == 1
    assert "empty_content" in result["issue_counts"]


def test_quality_analyzer_all_clean() -> None:
    records = _good_tamil_records(5)
    result = analyze_quality(source_public_id="src1", records=records)
    assert result["clean_ratio"] == 1.0


def test_quality_analyzer_flags_broken_reference() -> None:
    records = [_record(0, source_public_id="other-source", output_text="A real answer here.")]
    result = analyze_quality(source_public_id="src1", records=records)
    assert result["broken_reference_records"] == 1


# -- language_analyzer -------------------------------------------------------

def test_language_analyzer_distribution_sums_to_total() -> None:
    records = _good_tamil_records(10) + [
        _record(100 + i, language="en", instruction="How do I create a dataset?", output_text="Follow these steps to create a dataset properly.")
        for i in range(5)
    ]
    result = analyze_language(records)
    assert sum(result["distribution_counts"].values()) == 15
    assert result["distribution_counts"]["tamil"] == 10
    assert result["distribution_counts"]["english"] == 5


def test_language_analyzer_includes_token_estimation() -> None:
    result = analyze_language(_good_tamil_records(3))
    assert "token_estimation" in result
    assert result["token_estimation"]["estimated_total_tokens"] > 0


# -- domain_classifier -----------------------------------------------------

def test_domain_classifier_topic_keyword_wins() -> None:
    records = [
        _record(i, language="en", instruction="Explain this algorithm", output_text="A function with a time complexity of O(n log n) using a data structure.")
        for i in range(10)
    ]
    result = classify_domain(records=records, language_percentages={"tamil": 0, "english": 100, "tanglish": 0, "mixed": 0, "unknown": 0}, record_type_counts={"instruction": 10})
    assert result["category"] == "Programming"


def test_domain_classifier_record_type_dominance() -> None:
    records = [_record(i, record_type="chat", language="en", output_text="hello there friend") for i in range(10)]
    result = classify_domain(records=records, language_percentages={"tamil": 0, "english": 100, "tanglish": 0, "mixed": 0, "unknown": 0}, record_type_counts={"chat": 10})
    assert result["category"] == "Conversation"


def test_domain_classifier_language_dominance_fallback() -> None:
    records = [_record(i, output_text="just plain text here") for i in range(10)]
    result = classify_domain(records=records, language_percentages={"tamil": 95.0, "english": 5.0, "tanglish": 0, "mixed": 0, "unknown": 0}, record_type_counts={})
    assert result["category"] == "Tamil"


def test_domain_classifier_general_fallback() -> None:
    records = [_record(i, output_text="just plain text here") for i in range(10)]
    result = classify_domain(records=records, language_percentages={"tamil": 40.0, "english": 40.0, "tanglish": 10.0, "mixed": 5.0, "unknown": 5.0}, record_type_counts={})
    assert result["category"] in CATEGORIES


def test_domain_classifier_empty_records() -> None:
    result = classify_domain(records=[], language_percentages={}, record_type_counts={})
    assert result["category"] == "General"


# -- duplicate_analyzer ------------------------------------------------------

def test_duplicate_analyzer_finds_exact_content_hash_duplicates() -> None:
    records = [_record(0, content_hash="same"), _record(1, content_hash="same"), _record(2, content_hash="different")]
    result = analyze_duplicates(source=SOURCE, records=records)
    assert result["duplicate_record_count"] == 2
    assert len(result["duplicate_record_groups"]) == 1


def test_duplicate_analyzer_finds_duplicate_instructions() -> None:
    records = [
        _record(0, instruction="Same instruction text", output_text="a"),
        _record(1, instruction="Same instruction text", output_text="b"),
        _record(2, instruction="Different instruction", output_text="c"),
    ]
    result = analyze_duplicates(source=SOURCE, records=records)
    assert len(result["duplicate_instruction_groups"]) == 1


def test_duplicate_analyzer_no_duplicates() -> None:
    records = _good_tamil_records(5)
    result = analyze_duplicates(source=SOURCE, records=records)
    assert result["duplicate_record_count"] == 0


# -- token_estimator ----------------------------------------------------------

def test_estimate_tokens_uses_language_specific_ratio() -> None:
    text = "a" * 100
    assert estimate_tokens(text, language="ta") > estimate_tokens(text, language="en")


def test_estimate_tokens_empty_text() -> None:
    assert estimate_tokens("") == 0


def test_estimate_dataset_tokens_aggregates() -> None:
    result = estimate_dataset_tokens(_good_tamil_records(5))
    assert result["total_records"] == 5
    assert result["estimated_total_tokens"] > 0
    assert "NOT a real tokenizer" in result["methodology"]


# -- training_readiness -------------------------------------------------------

def test_training_readiness_not_ready_too_few_records() -> None:
    quality = {"clean_ratio": 1.0}
    duplicates = {"duplicate_record_count": 0}
    result = assess_training_readiness(record_count=10, quality=quality, duplicates=duplicates)
    assert result["status"] == "Not Ready"


def test_training_readiness_ready() -> None:
    quality = {"clean_ratio": 0.95}
    duplicates = {"duplicate_record_count": 1}
    result = assess_training_readiness(record_count=100, quality=quality, duplicates=duplicates)
    assert result["status"] == "Ready"
    assert len(result["reasons"]) > 0


def test_training_readiness_needs_improvement() -> None:
    quality = {"clean_ratio": 0.7}
    duplicates = {"duplicate_record_count": 0}
    result = assess_training_readiness(record_count=100, quality=quality, duplicates=duplicates)
    assert result["status"] == "Needs Improvement"


# -- rag_readiness -----------------------------------------------------------

def test_rag_readiness_not_ready_bad_chunk_sizes() -> None:
    quality = {"clean_ratio": 0.9}
    duplicates = {"duplicate_record_count": 0}
    language = {"declared_language_mismatches": 0}
    records = [_record(i, output_text="short") for i in range(10)]
    result = assess_rag_readiness(records=records, quality=quality, duplicates=duplicates, language=language)
    assert result["status"] == "Not Ready"
    assert "100%" in result["missing_titles"]


def test_rag_readiness_ready_with_good_chunk_sizes() -> None:
    quality = {"clean_ratio": 0.95}
    duplicates = {"duplicate_record_count": 0}
    language = {"declared_language_mismatches": 0}
    text = "This is a reasonably long piece of content. " * 10
    records = [_record(i, output_text=text, metadata={"source": "docs"}) for i in range(10)]
    result = assess_rag_readiness(records=records, quality=quality, duplicates=duplicates, language=language)
    assert result["status"] == "Ready"


# -- sft_readiness -------------------------------------------------------------

def test_sft_readiness_not_ready_missing_instructions() -> None:
    quality = {"clean_ratio": 0.9, "flagged_record_details": []}
    records = [_record(i, instruction=None, output_text="answer here") for i in range(10)]
    result = assess_sft_readiness(records=records, quality=quality)
    assert result["status"] == "Not Ready"


def test_sft_readiness_ready() -> None:
    quality = {"clean_ratio": 0.95, "flagged_record_details": []}
    records = _good_tamil_records(20)
    result = assess_sft_readiness(records=records, quality=quality)
    assert result["status"] == "Ready"


# -- score_engine ---------------------------------------------------------------

def test_compute_scores_overall_is_unweighted_mean() -> None:
    dataset = analyze_dataset(source=SOURCE, records=_good_tamil_records(10))
    quality = analyze_quality(source_public_id="src1", records=_good_tamil_records(10))
    language = analyze_language(_good_tamil_records(10))
    training = assess_training_readiness(record_count=10, quality=quality, duplicates={"duplicate_record_count": 0})
    rag = assess_rag_readiness(records=_good_tamil_records(10), quality=quality, duplicates={"duplicate_record_count": 0}, language=language)
    sft = assess_sft_readiness(records=_good_tamil_records(10), quality=quality)
    scores = compute_scores(dataset=dataset, quality=quality, language=language, training=training, rag=rag, sft=sft)

    component_scores = [scores[k]["score"] for k in ("structure", "quality", "language", "training", "rag", "sft", "documentation", "metadata")]
    expected_overall = round(sum(component_scores) / len(component_scores))
    assert scores["overall"]["score"] == expected_overall


def test_every_score_has_formula_calculation_and_reason() -> None:
    dataset = analyze_dataset(source=SOURCE, records=_good_tamil_records(5))
    quality = analyze_quality(source_public_id="src1", records=_good_tamil_records(5))
    language = analyze_language(_good_tamil_records(5))
    training = assess_training_readiness(record_count=5, quality=quality, duplicates={"duplicate_record_count": 0})
    rag = assess_rag_readiness(records=_good_tamil_records(5), quality=quality, duplicates={"duplicate_record_count": 0}, language=language)
    sft = assess_sft_readiness(records=_good_tamil_records(5), quality=quality)
    scores = compute_scores(dataset=dataset, quality=quality, language=language, training=training, rag=rag, sft=sft)
    for name, entry in scores.items():
        assert "formula" in entry and entry["formula"]
        assert "calculation" in entry and entry["calculation"]
        assert "reason" in entry and entry["reason"]
        assert 0 <= entry["score"] <= 100


# -- recommendation_engine ---------------------------------------------------

def test_recommendations_include_why_for_each() -> None:
    dataset = analyze_dataset(source=SOURCE, records=[_record(0, instruction=None, output_text=None)])
    quality = analyze_quality(source_public_id="src1", records=[_record(0, instruction=None, output_text=None)])
    language = analyze_language([_record(0, instruction=None, output_text=None)])
    duplicates = analyze_duplicates(source=SOURCE, records=[_record(0, instruction=None, output_text=None)])
    domain = classify_domain(records=[], language_percentages={}, record_type_counts={})
    training = assess_training_readiness(record_count=1, quality=quality, duplicates=duplicates)
    rag = assess_rag_readiness(records=[_record(0, instruction=None, output_text=None)], quality=quality, duplicates=duplicates, language=language)
    sft = assess_sft_readiness(records=[_record(0, instruction=None, output_text=None)], quality=quality)

    recs = generate_recommendations(dataset=dataset, quality=quality, language=language, duplicates=duplicates, domain=domain, training=training, rag=rag, sft=sft)
    assert len(recs) > 0
    for rec in recs:
        assert rec["reason"]
        assert rec["priority"] in ("high", "medium", "low")


def test_no_recommendations_for_a_clean_ready_dataset() -> None:
    records = _good_tamil_records(60)
    dataset = analyze_dataset(source=SOURCE, records=records)
    quality = analyze_quality(source_public_id="src1", records=records)
    language = analyze_language(records)
    duplicates = analyze_duplicates(source=SOURCE, records=records)
    domain = classify_domain(records=records, language_percentages=language["distribution_percentages"], record_type_counts=dataset["by_record_type"])
    training = assess_training_readiness(record_count=60, quality=quality, duplicates=duplicates)
    rag = assess_rag_readiness(records=records, quality=quality, duplicates=duplicates, language=language)
    sft = assess_sft_readiness(records=records, quality=quality)
    recs = generate_recommendations(dataset=dataset, quality=quality, language=language, duplicates=duplicates, domain=domain, training=training, rag=rag, sft=sft)
    # documentation may still fire (few metadata keys) -- but no cleaning/training-blocker recs
    categories = {r["category"] for r in recs}
    assert "cleaning" not in categories
