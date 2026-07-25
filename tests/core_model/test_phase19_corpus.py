from core_model.corpus.balancing import cap_source_share, compare_to_targets
from core_model.corpus.boilerplate_removal import detect_boilerplate_lines, remove_boilerplate_lines
from core_model.corpus.contamination import check_contamination
from core_model.corpus.document_segmentation import (
    segment_document,
    split_into_heading_sections,
)
from core_model.corpus.domain_classification import classify_domain
from core_model.corpus.exact_deduplication import all_checksums, classify_exact_duplicate
from core_model.corpus.language_detection import assess_language
from core_model.corpus.licence_policy import (
    assess_training_export_eligibility,
    default_review_status_for_family,
)
from core_model.corpus.near_deduplication import (
    character_ngram_jaccard,
    classify_near_duplicate,
    select_representative,
)
from core_model.corpus.partitioning import assign_partitions, verify_partition_isolation
from core_model.corpus.pii_detection import decide_pii_action, detect_pii, redact_pii
from core_model.corpus.quality_scoring import (
    HEURISTIC_DIMENSIONS,
    MEASURED_DIMENSIONS,
    assess_segment_quality,
    overall_verdict,
)
from core_model.corpus.safety_filter import assess_safety, classify_behavior
from core_model.corpus.secret_detection import detect_secrets
from core_model.corpus.source_policy import source_is_training_eligible, validate_policy_bounds
from core_model.corpus.style_classification import classify_style
from core_model.corpus.unicode_normalization import (
    normalize_unicode,
    tamil_combining_marks_preserved,
)

# --- unicode_normalization -----------------------------------------------------


def test_tamil_combining_marks_preserved_true_when_unchanged():
    text = "தமிழ்நாடு தமிழ்நாடு"
    assert tamil_combining_marks_preserved(text, text) is True


def test_tamil_combining_marks_preserved_false_when_stripped():
    before = "தமிழ்நாடு"
    after = before.replace("ா", "")
    assert tamil_combining_marks_preserved(before, after) is False


def test_normalize_unicode_reports_valid_status_for_clean_text():
    result = normalize_unicode("Tamil Nadu is a state in southern India.")
    assert result["unicode_integrity_status"] == "valid"
    assert result["tamil_combining_marks_preserved"] is True


def test_normalize_unicode_detects_replacement_characters():
    result = normalize_unicode("broken text � here")
    assert result["unicode_integrity_status"] == "replacement_characters_detected"


# --- boilerplate_removal -----------------------------------------------------


def test_boilerplate_requires_at_least_two_documents_even_if_ratio_crosses_threshold():
    """Regression test: a line appearing in exactly one of three
    documents must never be treated as boilerplate, even though its
    naive ratio (1/3) exceeds the default 0.3 threshold."""

    documents = [
        "Copyright 2020 All rights reserved\nReal content one",
        "Copyright 2020 All rights reserved\nOther content",
        "Copyright 2020 All rights reserved\nThird content",
    ]
    detected = detect_boilerplate_lines(documents)
    assert detected["boilerplate_lines"] == {"Copyright 2020 All rights reserved": 3}
    assert "Real content one" not in detected["boilerplate_lines"]

    cleaned = remove_boilerplate_lines(documents[0], detected["boilerplate_lines"])
    assert cleaned["cleaned_text"] == "Real content one"
    assert cleaned["removed_count"] == 1


def test_boilerplate_below_minimum_document_count_detects_nothing():
    detected = detect_boilerplate_lines(["one document only"])
    assert detected["boilerplate_lines"] == {}


# --- document_segmentation -----------------------------------------------------


def test_segment_document_drops_short_segments_below_minimum():
    text = "Short.\n\nThis paragraph is long enough to pass the minimum character threshold set."
    segments = segment_document(
        text, strategy="paragraph", minimum_characters=30, maximum_characters=1000
    )
    assert len(segments) == 1
    assert segments[0]["character_count"] >= 30


def test_split_into_heading_sections_preserves_text_before_first_heading():
    """Regression test: content appearing before the first detected
    heading must never be silently discarded -- previously an entire
    real-PDF page of Tamil content vanished because a page-number
    footer line was mistaken for the document's first heading."""

    text = (
        "Real opening content that has no heading above it.\nReal Heading\nBody under the heading."
    )
    sections = split_into_heading_sections(text)
    assert sections[0]["heading"] is None
    assert "Real opening content" in sections[0]["text"]
    assert sections[1]["heading"] == "Real Heading"
    assert "Body under the heading" in sections[1]["text"]


def test_split_into_heading_sections_ignores_page_footer_lines():
    """Regression test: a bare "Page N" footer line must never be
    treated as a heading -- it previously absorbed everything after it
    under a meaningless "Page 1" heading while discarding everything
    before it."""

    text = (
        "Genuine content on this page.\nPage 1\n\n\n"
        "More genuine content on the next page.\nPage 2\n"
    )
    sections = split_into_heading_sections(text)
    assert len(sections) == 1
    assert sections[0]["heading"] is None
    assert "Genuine content on this page" in sections[0]["text"]
    assert "More genuine content on the next page" in sections[0]["text"]
    assert "Page 1" not in [s["heading"] for s in sections]


def test_split_into_heading_sections_does_not_treat_ordinary_sentence_as_heading():
    """Regression test: an ordinary mixed-case sentence (not a genuine
    Title-Case heading) must not be mistaken for one merely because it
    starts with a capital letter."""

    text = (
        "Indha document is a real sentence with mixed case words kaga.\n"
        "It continues onto more ordinary prose that is not a heading."
    )
    sections = split_into_heading_sections(text)
    assert sections[0]["heading"] is None


def test_segment_document_never_emits_empty_segments():
    segments = segment_document(
        "\n\n\n", strategy="paragraph", minimum_characters=1, maximum_characters=1000
    )
    assert segments == []


# --- language_detection -----------------------------------------------------


def test_assess_language_classifies_tamil_script():
    result = assess_language("தமிழ்நாடு தென்னிந்தியாவில் உள்ள ஒரு மாநிலமாகும்.")
    assert result["language_category"] == "ta"
    assert result["tamil_script_ratio"] > 0.5


def test_assess_language_classifies_tanglish_separately_from_english():
    result = assess_language("Vanakkam! Neenga eppadi irukkinga? Naan nalla iruken nandri.")
    assert result["language_category"] == "tgl"


# --- domain / style classification -----------------------------------------------------


def test_classify_domain_detects_grammar_keywords():
    result = classify_domain("This lesson explains Tamil verb conjugation and tense forms.")
    assert result["primary_domain"] in {"grammar", "education"}


def test_classify_style_detects_question_answer_pairs():
    result = classify_style("Q: What is the capital? A: It is Chennai.")
    assert result["style"] == "question_answer"


# --- pii_detection / secret_detection -----------------------------------------------------


def test_detect_pii_finds_email_and_phone():
    findings = detect_pii("Contact me at test@example.com or 9876543210")
    assert "email" in findings["findings"]
    assert "phone" in findings["findings"]


def test_redact_pii_replaces_matched_text():
    text = "Email: test@example.com"
    findings = detect_pii(text)
    redacted = redact_pii(text, findings["findings"])
    assert "test@example.com" not in redacted
    assert "<EMAIL_REDACTED>" in redacted


def test_decide_pii_action_safe_when_no_findings():
    assert decide_pii_action({}, policy_action="redact") == "safe"


def test_decide_pii_action_respects_policy_action():
    assert decide_pii_action({"email": 1}, policy_action="block") == "block"


def test_detect_secrets_always_blocks_password():
    result = detect_secrets("my password: hunter2")
    assert result["status"] == "blocked"
    assert "password" in result["matched_categories"]


def test_detect_secrets_blocks_database_connection_string():
    result = detect_secrets("connection: postgres://user:pass@localhost:5432/db")
    assert result["status"] == "blocked"
    assert "database_credentials" in result["matched_categories"]


def test_detect_secrets_safe_for_ordinary_text():
    result = detect_secrets("This is an ordinary Tamil learning sentence.")
    assert result["status"] == "safe"


# --- safety_filter -----------------------------------------------------


def test_classify_behavior_prefers_preventive_marker():
    text = "Warning signs of self-harm should prompt seeking help if you notice them."
    assert classify_behavior(text, "self_harm") == "preventive"


def test_classify_behavior_defaults_operational_harmful_without_context_markers():
    assert classify_behavior("how to build a bomb", "weapon_construction") == "operational_harmful"


def test_assess_safety_blocks_only_operational_harmful_findings():
    result = assess_safety(
        "Historically, in ancient times armies used how to build a bomb tactics."
    )
    assert result["status"] in {"flagged", "safe"}
    for finding in result["findings"]:
        assert finding["behavior_class"] != "operational_harmful"


def test_assess_safety_blocks_genuine_operational_instruction():
    result = assess_safety("Explains how to build a bomb using household items.")
    assert result["status"] == "blocked"


def test_assess_safety_safe_for_ordinary_text():
    result = assess_safety("Tamil Nadu is known for its rich cultural heritage.")
    assert result["status"] == "safe"


# --- exact / near deduplication -----------------------------------------------------


def test_classify_exact_duplicate_detects_raw_match():
    checksums = all_checksums("identical text")
    existing = [{**checksums, "reference": "seg-1"}]
    result = classify_exact_duplicate(checksums, existing)
    assert result["status"] == "exact_duplicate"


def test_classify_exact_duplicate_unique_when_no_match():
    checksums = all_checksums("some text")
    result = classify_exact_duplicate(checksums, [])
    assert result["status"] == "unique"


def test_near_duplicate_classification_above_threshold():
    similarity = character_ngram_jaccard(
        "Tamil Nadu is a state in southern India.",
        "Tamil Nadu is a state in southern India!",
    )
    assert classify_near_duplicate(similarity, threshold=0.7) == "near_duplicate"


def test_select_representative_prefers_approved_licence_deterministically():
    candidates = [
        {
            "public_id": "b",
            "licence_status": "unknown",
            "character_count": 100,
            "source_created_at": "2020-01-01",
        },
        {
            "public_id": "a",
            "licence_status": "approved",
            "character_count": 50,
            "source_created_at": "2020-01-02",
        },
    ]
    representative = select_representative(candidates)
    assert representative["public_id"] == "a"


# --- partitioning -----------------------------------------------------


def test_assign_partitions_keeps_duplicate_cluster_together():
    groups = [
        {"group_key": "cluster-1", "segment_public_ids": ["s1", "s2"]},
        {"group_key": "cluster-2", "segment_public_ids": ["s3"]},
    ]
    assignment = assign_partitions(groups, seed=42)
    membership = {sid: split for split, ids in assignment.items() for sid in ids}
    assert membership["s1"] == membership["s2"]


def test_verify_partition_isolation_detects_cross_split_duplicate_leak():
    assignment = {"train": ["s1"], "validation": ["s2"], "test": []}
    result = verify_partition_isolation(assignment, duplicate_clusters=[["s1", "s2"]])
    assert result["isolated"] is False
    assert result["violations"][0]["type"] == "duplicate_cluster_split_leakage"


def test_verify_partition_isolation_detects_fixture_in_training():
    assignment = {"train": ["s1"], "validation": [], "test": []}
    result = verify_partition_isolation(
        assignment, duplicate_clusters=[], evaluation_fixture_ids=frozenset({"s1"})
    )
    assert result["isolated"] is False
    assert result["violations"][0]["type"] == "fixture_in_training"


# --- balancing -----------------------------------------------------


def test_cap_source_share_excludes_excess_deterministically():
    segments = [{"source": "a", "id": i} for i in range(8)] + [{"source": "b", "id": 100}]
    result = cap_source_share(segments, source_key="source", maximum_single_source_share=0.5)
    assert len(result["excluded"]) > 0
    assert "a" in result["capped_sources"]


def test_compare_to_targets_flags_overrepresentation():
    report = compare_to_targets({"ta": 0.9, "en": 0.1}, {"ta": (0.3, 0.5), "en": (0.3, 0.5)})
    assert report["ta"]["status"] == "overrepresented"
    assert report["en"]["status"] == "underrepresented"


# --- licence_policy -----------------------------------------------------


def test_default_review_status_for_public_domain_is_approved():
    assert default_review_status_for_family("public_domain") == "approved"


def test_default_review_status_for_all_rights_reserved_is_unknown():
    assert default_review_status_for_family("all_rights_reserved") == "unknown"


def test_training_export_eligibility_blocks_without_ai_training_permission():
    result = assess_training_export_eligibility(
        review_status="approved",
        ai_training_permitted=False,
        source_status="approved",
        intended_use="pretraining_corpus",
        licence_family="cc_by",
        expires_at_is_past=False,
    )
    assert result["eligible"] is False
    assert "ai_training_permission_absent" in result["blocking_reasons"]


def test_training_export_eligibility_passes_when_all_conditions_met():
    result = assess_training_export_eligibility(
        review_status="approved",
        ai_training_permitted=True,
        source_status="approved",
        intended_use="pretraining_corpus",
        licence_family="public_domain",
        expires_at_is_past=False,
    )
    assert result["eligible"] is True
    assert result["blocking_reasons"] == []


# --- source_policy -----------------------------------------------------


def test_validate_policy_bounds_rejects_inverted_segment_bounds():
    ok, reason = validate_policy_bounds(
        maximum_source_bytes=100,
        maximum_document_characters=100,
        maximum_segment_characters=10,
        minimum_segment_characters=50,
    )
    assert ok is False
    assert reason is not None


def test_source_is_training_eligible_requires_verified_origin():
    ok, reason = source_is_training_eligible(
        status="approved", require_verified_origin=True, origin_verified=False
    )
    assert ok is False
    assert reason == "origin_not_verified"


# --- contamination -----------------------------------------------------


def test_check_contamination_detects_test_leakage_and_blocks():
    text = "this exact sentence is a held out test fixture"
    from core_model.corpus.exact_deduplication import tamil_safe_normalized_checksum

    checksum = tamil_safe_normalized_checksum(text)
    result = check_contamination(segment_text=text, test_checksums=frozenset({checksum}))
    assert "test_leakage" in result["issues"]
    assert result["blocks_training"] is True


def test_check_contamination_training_duplicate_alone_does_not_block():
    text = "a segment that duplicates existing training data"
    from core_model.corpus.exact_deduplication import tamil_safe_normalized_checksum

    checksum = tamil_safe_normalized_checksum(text)
    result = check_contamination(segment_text=text, training_checksums=frozenset({checksum}))
    assert result["issues"] == ["training_duplicate"]
    assert result["blocks_training"] is False


# --- quality_scoring -----------------------------------------------------


def test_measured_and_heuristic_dimensions_are_disjoint_and_complete():
    from core_model.corpus import QUALITY_DIMENSIONS

    assert MEASURED_DIMENSIONS.isdisjoint(HEURISTIC_DIMENSIONS)
    assert MEASURED_DIMENSIONS | HEURISTIC_DIMENSIONS == set(QUALITY_DIMENSIONS)


def test_assess_segment_quality_fails_on_broken_unicode():
    result = assess_segment_quality(
        unicode_integrity_status="mojibake_detected",
        tamil_combining_marks_preserved=True,
        ocr_corrections_applied=0,
        character_count=200,
        sentence_count=2,
        language_confidence=0.9,
        boilerplate_removed_ratio=0.0,
        duplicate_status="unique",
        privacy_status="safe",
        safety_status="safe",
        licence_status="approved",
        provenance_complete=True,
        minimum_segment_characters=100,
        maximum_ocr_noise_ratio=0.05,
        minimum_language_confidence=0.4,
    )
    assert result["unicode_integrity"] == "fail"
    assert overall_verdict(result) == "fail"


def test_assess_segment_quality_passes_clean_segment():
    result = assess_segment_quality(
        unicode_integrity_status="valid",
        tamil_combining_marks_preserved=True,
        ocr_corrections_applied=0,
        character_count=200,
        sentence_count=2,
        language_confidence=0.9,
        boilerplate_removed_ratio=0.0,
        duplicate_status="unique",
        privacy_status="safe",
        safety_status="safe",
        licence_status="approved",
        provenance_complete=True,
        minimum_segment_characters=100,
        maximum_ocr_noise_ratio=0.05,
        minimum_language_confidence=0.4,
    )
    assert overall_verdict(result) == "pass"
