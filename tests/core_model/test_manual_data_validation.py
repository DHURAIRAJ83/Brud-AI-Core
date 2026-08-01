from core_model.manual_data.validation import validate_record_fields


def test_plain_text_requires_text_and_language():
    errors = validate_record_fields("plain_text", {})
    assert any("input_text" in e for e in errors)
    assert any("primary_language" in e for e in errors)


def test_plain_text_valid():
    errors = validate_record_fields("plain_text", {"tamil_text": "வணக்கம்", "primary_language": "ta"})
    assert errors == []


def test_conversation_requires_two_turns():
    errors = validate_record_fields(
        "conversation",
        {"primary_language": "ta", "turns": [{"role": "user", "content": "hi"}]},
    )
    assert any("at least two" in e for e in errors)


def test_conversation_rejects_empty_turn_and_bad_role():
    errors = validate_record_fields(
        "conversation",
        {
            "primary_language": "en",
            "turns": [
                {"role": "user", "content": "hi"},
                {"role": "alien", "content": ""},
            ],
        },
    )
    assert any("empty content" in e for e in errors)
    assert any("invalid role" in e for e in errors)


def test_conversation_valid():
    errors = validate_record_fields(
        "conversation",
        {
            "primary_language": "en",
            "turns": [
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "hello"},
            ],
        },
    )
    assert errors == []


def test_question_answer_requires_both():
    errors = validate_record_fields("question_answer", {"question_text": "q?"})
    assert any("answer_text" in e for e in errors)


def test_instruction_response_requires_output_language():
    errors = validate_record_fields(
        "instruction_response", {"instruction_text": "do x", "response_text": "done"}
    )
    assert any("output_language" in e for e in errors)


def test_dictionary_entry_requires_meanings():
    errors = validate_record_fields("dictionary_entry", {"word": "நல்லது", "primary_language": "ta"})
    assert any("meaning" in e for e in errors)


def test_dictionary_entry_valid():
    errors = validate_record_fields(
        "dictionary_entry",
        {"word": "நல்லது", "primary_language": "ta", "meanings": ["good"]},
    )
    assert errors == []


def test_translation_pair_requires_distinct_languages():
    errors = validate_record_fields(
        "translation_pair",
        {
            "input_text": "hello",
            "output_text": "வணக்கம்",
            "input_language": "en",
            "output_language": "en",
        },
    )
    assert any("distinct" in e for e in errors)


def test_translation_pair_valid():
    errors = validate_record_fields(
        "translation_pair",
        {
            "input_text": "hello",
            "output_text": "வணக்கம்",
            "input_language": "en",
            "output_language": "ta",
        },
    )
    assert errors == []


def test_tanglish_normalization_requires_both_texts():
    errors = validate_record_fields("tanglish_normalization", {"tanglish_text": "vanakkam"})
    assert any("tamil_text" in e for e in errors)


def test_knowledge_note_requires_classification():
    errors = validate_record_fields(
        "knowledge_note", {"title": "Procedure", "input_text": "steps..."}
    )
    assert any("fact_dependency" in e for e in errors)
    assert any("knowledge_risk" in e for e in errors)


def test_time_sensitive_requires_expiry():
    errors = validate_record_fields(
        "knowledge_note",
        {
            "title": "Fee schedule",
            "input_text": "current fees",
            "fact_dependency": "high",
            "knowledge_risk": "time_sensitive",
        },
    )
    assert any("review_expiry_at" in e for e in errors)


def test_time_sensitive_valid_with_expiry():
    errors = validate_record_fields(
        "knowledge_note",
        {
            "title": "Fee schedule",
            "input_text": "current fees",
            "fact_dependency": "high",
            "knowledge_risk": "time_sensitive",
            "review_expiry_at": "2027-01-01T00:00:00Z",
        },
    )
    assert errors == []
