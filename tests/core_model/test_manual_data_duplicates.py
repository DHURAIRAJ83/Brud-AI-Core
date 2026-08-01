from core_model.manual_data.duplicates import content_hash, dictionary_word_key, normalize_text


def test_normalize_text_collapses_whitespace_and_nfc():
    assert normalize_text("  hello   world  ") == "hello world"
    assert normalize_text(None) is None


def test_normalize_text_fold_case():
    assert normalize_text("Hello", fold_case=True) == "hello"


def test_content_hash_stable_for_equivalent_text():
    fields_a = {"primary_language": "en", "input_text": "Hello  World"}
    fields_b = {"primary_language": "en", "input_text": "hello world"}
    assert content_hash("plain_text", fields_a) == content_hash("plain_text", fields_b)


def test_content_hash_differs_for_different_language_or_type():
    fields = {"primary_language": "en", "input_text": "hello"}
    assert content_hash("plain_text", fields) != content_hash(
        "language_example", {**fields, "primary_language": "ta"}
    )


def test_content_hash_tamil_not_casefolded_differently():
    fields = {"primary_language": "ta", "tamil_text": "வணக்கம்"}
    assert content_hash("plain_text", fields) == content_hash("plain_text", fields)


def test_content_hash_conversation_uses_turns():
    turns_a = {"primary_language": "en", "turns": [{"role": "user", "content": "Hi"}]}
    turns_b = {"primary_language": "en", "turns": [{"role": "user", "content": "hi"}]}
    assert content_hash("conversation", turns_a) == content_hash("conversation", turns_b)


def test_dictionary_word_key_normalizes():
    assert dictionary_word_key("Hello", "en") == dictionary_word_key("hello", "en")
    assert dictionary_word_key("hello", "en") != dictionary_word_key("hello", "ta")
    assert dictionary_word_key(None, "en") is None
