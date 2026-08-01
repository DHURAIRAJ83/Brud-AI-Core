from core_model.manual_data.quality import assess_quality


def _record(**overrides):
    base = {
        "record_type": "plain_text",
        "status": "draft",
        "source_id": 1,
        "creation_method": "human_created",
        "fact_dependency": "none",
        "knowledge_risk": "language_only",
        "primary_language": "ta",
    }
    base.update(overrides)
    return base


def test_good_language_data_recommends_approved():
    record = _record()
    fields = {"tamil_text": "வணக்கம்", "primary_language": "ta"}
    reviews = [
        {
            "review_type": "language",
            "review_status": "approved",
            "naturalness_score": 95,
            "meaning_score": 95,
        }
    ]
    result = assess_quality(record=record, fields=fields, reviews=reviews)
    assert result["overall_score"] >= 85
    assert result["blocking_issues"] == []
    assert result["recommended_status"] == "approved"


def test_missing_source_blocks():
    record = _record(source_id=None)
    fields = {"tamil_text": "வணக்கம்", "primary_language": "ta"}
    result = assess_quality(record=record, fields=fields)
    assert "MISSING_SOURCE" in result["blocking_issues"]
    assert result["recommended_status"] == "draft"


def test_high_risk_unverified_blocks():
    record = _record(knowledge_risk="high_risk", fact_dependency="high")
    fields = {"title": "Medical note", "input_text": "..."}
    result = assess_quality(record=record, fields=fields)
    assert "HIGH_RISK_UNVERIFIED" in result["blocking_issues"]
    assert result["recommended_status"] == "needs_source_verification"


def test_high_risk_with_strong_verification_does_not_block():
    record = _record(knowledge_risk="high_risk", fact_dependency="high")
    fields = {"title": "Medical note", "input_text": "..."}
    verifications = [{"verification_status": "verified"}]
    result = assess_quality(record=record, fields=fields, verifications=verifications)
    assert "HIGH_RISK_UNVERIFIED" not in result["blocking_issues"]


def test_ai_assisted_unreviewed_blocks():
    record = _record(creation_method="ai_assisted")
    fields = {"question_text": "q", "answer_text": "a"}
    result = assess_quality(record=record, fields=fields)
    assert "AI_ASSISTED_UNREVIEWED" in result["blocking_issues"]


def test_ai_assisted_with_approved_review_does_not_block():
    record = _record(creation_method="ai_assisted")
    fields = {"question_text": "q", "answer_text": "a"}
    reviews = [{"review_type": "general", "review_status": "approved"}]
    result = assess_quality(record=record, fields=fields, reviews=reviews)
    assert "AI_ASSISTED_UNREVIEWED" not in result["blocking_issues"]


def test_invalid_translation_pair_blocks():
    record = _record(record_type="translation_pair")
    fields = {
        "input_text": "hi",
        "output_text": "vanakkam",
        "input_language": "en",
        "output_language": "en",
    }
    result = assess_quality(record=record, fields=fields)
    assert "INVALID_LANGUAGE_PAIR" in result["blocking_issues"]
    assert "TRANSLATION_UNVERIFIED" in result["blocking_issues"]


def test_translation_pair_with_review_not_unverified():
    record = _record(record_type="translation_pair")
    fields = {
        "input_text": "hi",
        "output_text": "vanakkam",
        "input_language": "en",
        "output_language": "ta",
    }
    reviews = [{"review_type": "translation", "review_status": "approved"}]
    result = assess_quality(record=record, fields=fields, reviews=reviews)
    assert "TRANSLATION_UNVERIFIED" not in result["blocking_issues"]
    assert "INVALID_LANGUAGE_PAIR" not in result["blocking_issues"]


def test_incomplete_dictionary_record_blocks_empty_field():
    record = _record(record_type="dictionary_entry")
    fields = {"word": "நல்லது"}
    result = assess_quality(record=record, fields=fields)
    assert "EMPTY_REQUIRED_FIELD" in result["blocking_issues"]


def test_duplicate_record_warns_and_lowers_uniqueness():
    record = _record()
    fields = {"tamil_text": "வணக்கம்", "primary_language": "ta"}
    result = assess_quality(record=record, fields=fields, duplicate_status="exact_duplicate")
    assert "exact_duplicate_content_detected" in result["warnings"]
    assert result["dimension_scores"]["uniqueness"] == 0.0


def test_rejected_verification_is_factual_conflict():
    record = _record()
    fields = {"tamil_text": "வணக்கம்", "primary_language": "ta"}
    verifications = [{"verification_status": "rejected"}]
    result = assess_quality(record=record, fields=fields, verifications=verifications)
    assert "FACTUAL_CONFLICT" in result["blocking_issues"]


def test_high_score_cannot_hide_blocking_issue():
    record = _record(source_id=None)
    fields = {"tamil_text": "வணக்கம்", "primary_language": "ta"}
    reviews = [
        {
            "review_type": "language",
            "review_status": "approved",
            "naturalness_score": 100,
            "meaning_score": 100,
        }
    ]
    result = assess_quality(record=record, fields=fields, reviews=reviews)
    assert result["overall_score"] >= 85
    assert "MISSING_SOURCE" in result["blocking_issues"]
    assert result["recommended_status"] != "approved"


def test_usage_decision_not_allowed_adds_rights_block():
    record = _record()
    fields = {"tamil_text": "வணக்கம்", "primary_language": "ta"}
    usage_decision = {"allowed": False}
    result = assess_quality(record=record, fields=fields, usage_decision=usage_decision)
    assert "RIGHTS_BLOCK_TRAINING" in result["blocking_issues"]
