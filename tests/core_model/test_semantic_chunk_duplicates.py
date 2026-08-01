from core_model.semantic_chunk.duplicates import (
    chunk_content_hash,
    detect_dictionary_conflict,
    detect_qa_conflict,
    detect_translation_conflict,
    find_exact_chunk_duplicate,
    find_locator_duplicate,
    structured_record_content_hash,
)


def test_chunk_content_hash_is_stable_across_whitespace_variance():
    a = chunk_content_hash("Hello   world", "en")
    b = chunk_content_hash("Hello world", "en")
    assert a == b


def test_chunk_content_hash_differs_for_different_text():
    a = chunk_content_hash("Hello world", "en")
    b = chunk_content_hash("Goodbye world", "en")
    assert a != b


def test_find_exact_chunk_duplicate():
    existing = {"chunk-1": "hash-a", "chunk-2": "hash-b"}
    assert find_exact_chunk_duplicate("hash-b", existing) == "chunk-2"
    assert find_exact_chunk_duplicate("hash-c", existing) is None


def test_find_locator_duplicate_matches_same_page_and_offsets():
    existing = [{"public_id": "chunk-1", "page_number": 3, "offset_start": 10, "offset_end": 50}]
    duplicate_locator = {"page_number": 3, "offset_start": 10, "offset_end": 50}
    assert find_locator_duplicate(duplicate_locator, existing) == "chunk-1"
    different_locator = {"page_number": 3, "offset_start": 10, "offset_end": 60}
    assert find_locator_duplicate(different_locator, existing) is None


def test_structured_record_content_hash_uses_type_specific_fields():
    revision = {"question": "What is Tamil?", "answer": "A Dravidian language."}
    hash_a = structured_record_content_hash("question_answer", revision)
    hash_b = structured_record_content_hash("question_answer", {**revision, "answer": "Different."})
    assert hash_a != hash_b


def test_dictionary_same_word_same_meaning_is_duplicate_sense():
    existing = [{"public_id": "d-1", "word": "vanakkam", "meanings": ["hello", "greeting"]}]
    result = detect_dictionary_conflict("vanakkam", ["hello", "greeting"], existing)
    assert result["type"] == "duplicate_sense"


def test_dictionary_same_word_different_meaning_is_alternate_sense():
    existing = [{"public_id": "d-1", "word": "vanakkam", "meanings": ["hello"]}]
    result = detect_dictionary_conflict("vanakkam", ["a form of respectful greeting"], existing)
    assert result["type"] == "alternate_sense"


def test_dictionary_different_word_is_not_a_conflict():
    existing = [{"public_id": "d-1", "word": "vanakkam", "meanings": ["hello"]}]
    assert detect_dictionary_conflict("nandri", ["thank you"], existing) is None


def test_qa_same_question_different_answer_is_conflicting_answer():
    existing = [{"public_id": "q-1", "question": "What is Tamil?", "answer": "A language."}]
    result = detect_qa_conflict("What is Tamil?", "A script.", existing)
    assert result["type"] == "conflicting_answer"


def test_qa_same_question_same_answer_is_duplicate():
    existing = [{"public_id": "q-1", "question": "What is Tamil?", "answer": "A language."}]
    result = detect_qa_conflict("What is Tamil?", "A language.", existing)
    assert result["type"] == "duplicate_answer"


def test_translation_same_source_different_target_is_inconsistent():
    existing = [{"public_id": "t-1", "source_text": "vanakkam", "target_text": "hello"}]
    result = detect_translation_conflict("vanakkam", "greetings", existing)
    assert result["type"] == "inconsistent_translation"
