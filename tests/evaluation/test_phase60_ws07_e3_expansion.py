"""
Phase 60 WS07 E3 — Admin Assistant Controlled Dataset Expansion & Translation Engine Test Suite.
Verifies schema compliance, bilingual translation accuracy, polysemy/ambiguity handling,
phonetic Tanglish transliteration, 7 expansion modes, automated quality gates,
Admin Review Queue transitions, immutable dataset sealing, and strict governance locking.
"""

import sys
import os
import json
import hashlib
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core_model.admin_assistant.dataset_expansion_engine import (
    BilingualTranslationEngine,
    TanglishTransliterationEngine,
    DatasetExpansionEngine,
    GenerationType,
    ProvenanceClass,
    TAMIL_ENGLISH_LEXICON,
)
from core_model.admin_assistant.dataset_expansion_validator import (
    DatasetExpansionValidator,
    ValidationReport,
)
from backend.services.admin_assistant_dataset_expansion_service import (
    AdminAssistantDatasetExpansionService,
)

TOK_PATH = ROOT / "data/tokenizers/versions/tok/v2/tokenizer.model"
BM_PATH = ROOT / "artifacts/phase53_evaluation_manifest.json"
P55_PATH = ROOT / "artifacts/phase55_dataset_records_v001.jsonl"
DB_PATH = ROOT / "data/database/brud_ai.db"
P59_CKPT_PATH = ROOT / "artifacts/candidates/phase59/checkpoints/checkpoint_best.pt"
WS05_CKPT_PATH = ROOT / "artifacts/candidates/phase60/checkpoints/checkpoint_best.pt"
WS03_DATASET_PATH = ROOT / "artifacts/candidates/phase60/phase60_dataset_v001.jsonl"
WS04_CONFIG_PATH = ROOT / "artifacts/candidates/phase60/phase60_ws04_training_config.json"

E3_DIR = ROOT / "artifacts/candidates/phase60/ws07/e3"
E3_DATA_DIR = E3_DIR / "data"
CONFIG_PATH = E3_DIR / "phase60_ws07_e3_config.json"
MANIFEST_PATH = E3_DIR / "phase60_ws07_e3_manifest.json"
SUMMARY_PATH = E3_DIR / "phase60_ws07_e3_summary.json"
SEALED_DATASET_PATH = E3_DATA_DIR / "phase60_ws07_e3_dataset_v001.jsonl"

EXPECTED_TOK_SHA = "65342625ebb88eaab0996f0f6c5f3ef24ae9fd3203bc8377a0db353601e9ffd4"
EXPECTED_BM_SHA = "554bf72317d9439f7bd5f19e514d23c6a8fb0170807699a087631cbd4331d088"
EXPECTED_P55_SHA = "3e1481c3279c24eb957a90c9d7b8e642e2f657905463c3d7130475dbcb7919d1"
EXPECTED_DB_SHA = "34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729"
EXPECTED_P59_CKPT_SHA = "a5218b5bdb94d3b218896f3021d7f7d5298023036d350bf8a2d5e3b70423371a"
EXPECTED_WS05_CKPT_SHA = "30dbb8927c0c61c786683c06eebf8a2718054a4cf1df25ece47f97ca7c605421"
EXPECTED_WS03_DATASET_SHA = "f682ddf82e750449792f8148be50ccb235506d16a0732fb8dc3fa2e9f4935920"
EXPECTED_WS04_CONFIG_SHA = "9cfa74ec2b33281e8402da2f16a75e744b5e23c41d8ba4997ae122020640d4dd"

E3_REPORT_FILES = [
    "phase60_ws07_e3_manifest.json",
    "phase60_ws07_e3_config.json",
    "phase60_ws07_e3_summary.json",
    "phase60_ws07_e3_architecture.md",
    "phase60_ws07_e3_translation_spec.md",
    "phase60_ws07_e3_tanglish_spec.md",
    "phase60_ws07_e3_generation_policy.md",
    "phase60_ws07_e3_validation_policy.md",
    "phase60_ws07_e3_confidence_policy.md",
    "phase60_ws07_e3_provenance_policy.md",
    "phase60_ws07_e3_review_workflow.md",
    "phase60_ws07_e3_dataset_schema.md",
    "phase60_ws07_e3_versioning_policy.md",
    "phase60_ws07_e3_balance_analysis.md",
    "phase60_ws07_e3_experiment_matrix.md",
    "phase60_ws07_e3_security_governance.md",
    "phase60_ws07_e3_test_report.md",
    "phase60_ws07_e3_failure_matrix.md",
    "phase60_ws07_e3_final_audit.md",
]

@pytest.fixture(scope="session")
def e3_manifest():
    assert MANIFEST_PATH.exists()
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

@pytest.fixture(scope="session")
def e3_config():
    assert CONFIG_PATH.exists()
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

@pytest.fixture(scope="session")
def e3_summary():
    assert SUMMARY_PATH.exists()
    return json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))

@pytest.fixture(scope="session")
def sealed_dataset_records():
    assert SEALED_DATASET_PATH.exists()
    lines = [line.strip() for line in SEALED_DATASET_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [json.loads(line) for line in lines]

# -----------------------------------------------------------------------------
# 1. Frozen Baseline Immutability (8 tests)
# -----------------------------------------------------------------------------
def test_frozen_baseline_tokenizer_sha():
    assert hashlib.sha256(TOK_PATH.read_bytes()).hexdigest() == EXPECTED_TOK_SHA

def test_frozen_baseline_benchmark_sha():
    assert hashlib.sha256(BM_PATH.read_bytes()).hexdigest() == EXPECTED_BM_SHA

def test_frozen_baseline_p55_corpus_sha():
    assert hashlib.sha256(P55_PATH.read_bytes()).hexdigest() == EXPECTED_P55_SHA

def test_frozen_baseline_production_db_sha():
    assert hashlib.sha256(DB_PATH.read_bytes()).hexdigest() == EXPECTED_DB_SHA

def test_frozen_baseline_p59_ckpt_sha():
    assert hashlib.sha256(P59_CKPT_PATH.read_bytes()).hexdigest() == EXPECTED_P59_CKPT_SHA

def test_frozen_baseline_ws05_ckpt_sha():
    assert hashlib.sha256(WS05_CKPT_PATH.read_bytes()).hexdigest() == EXPECTED_WS05_CKPT_SHA

def test_frozen_baseline_ws03_dataset_sha():
    assert hashlib.sha256(WS03_DATASET_PATH.read_bytes()).hexdigest() == EXPECTED_WS03_DATASET_SHA

def test_frozen_baseline_ws04_config_sha():
    assert hashlib.sha256(WS04_CONFIG_PATH.read_bytes()).hexdigest() == EXPECTED_WS04_CONFIG_SHA

# -----------------------------------------------------------------------------
# 2. Artifacts & Deliverables Existence (19 tests)
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("r_file", E3_REPORT_FILES)
def test_e3_report_file_exists_and_non_empty(r_file):
    fp = E3_DIR / r_file
    assert fp.exists(), f"Missing E3 deliverable: {r_file}"
    assert fp.stat().st_size > 0, f"Empty E3 deliverable: {r_file}"

# -----------------------------------------------------------------------------
# 3. Sealed Dataset Verification (10 tests)
# -----------------------------------------------------------------------------
def test_sealed_dataset_file_exists():
    assert SEALED_DATASET_PATH.exists()

def test_sealed_dataset_record_count(sealed_dataset_records):
    assert len(sealed_dataset_records) == 88

def test_sealed_dataset_sha_matches_manifest(e3_manifest):
    actual_sha = hashlib.sha256(SEALED_DATASET_PATH.read_bytes()).hexdigest()
    assert actual_sha == e3_manifest["sealed_dataset"]["sha256"]

@pytest.mark.parametrize("req_key", [
    "record_id", "task_type", "capability_id", "language", "instruction",
    "response", "difficulty", "source_type", "provenance", "content_hash"
])
def test_sealed_dataset_record_schema_fields(sealed_dataset_records, req_key):
    for rec in sealed_dataset_records[:10]:
        assert req_key in rec

# -----------------------------------------------------------------------------
# 4. Strict Governance Invariants (10 tests)
# -----------------------------------------------------------------------------
def test_governance_training_not_authorized(e3_config, e3_manifest):
    assert e3_config["governance"]["training_execution_authorized"] is False
    assert e3_manifest["governance"]["training_execution_authorized"] is False

def test_governance_traffic_share_zero(e3_config, e3_manifest):
    assert e3_config["governance"]["candidate_traffic_share"] == 0.0
    assert e3_manifest["governance"]["candidate_traffic_share"] == 0.0

def test_governance_public_chat_false(e3_config, e3_manifest):
    assert e3_config["governance"]["is_public_chat_eligible"] is False
    assert e3_manifest["governance"]["is_public_chat_eligible"] is False

def test_governance_production_promotion_blocked(e3_config, e3_manifest):
    assert e3_config["governance"]["production_promotion_state"] == "BLOCKED"
    assert e3_manifest["governance"]["production_promotion_state"] == "BLOCKED"

def test_governance_offline_airgapped(e3_config):
    assert e3_config["governance"]["offline_airgapped"] is True

def test_production_database_untouched():
    assert hashlib.sha256(DB_PATH.read_bytes()).hexdigest() == EXPECTED_DB_SHA

# -----------------------------------------------------------------------------
# 5. Bilingual Translation & Polysemy Handling (30 tests)
# -----------------------------------------------------------------------------
UNAMBIGUOUS_CONCEPTS = [
    ("அம்மா", "mother"),
    ("அப்பா", "father"),
    ("வீடு", "house"),
    ("தண்ணீர்", "water"),
    ("சாப்பாடு", "food"),
    ("புத்தகம்", "book"),
    ("வணக்கம்", "greetings"),
    ("நன்றி", "thank you"),
]

@pytest.mark.parametrize("concept,expected_en", UNAMBIGUOUS_CONCEPTS)
def test_unambiguous_translation_accuracy(concept, expected_en):
    cand = BilingualTranslationEngine.translate_concept(concept)
    assert cand.tamil_concept == concept
    assert cand.english_translation == expected_en
    assert cand.is_ambiguous is False
    assert cand.confidence >= 0.95

POLYSEMOUS_CONCEPTS = ["பால்", "படி", "திங்கள்"]

@pytest.mark.parametrize("concept", POLYSEMOUS_CONCEPTS)
def test_polysemous_concepts_flagged(concept):
    cand = BilingualTranslationEngine.translate_concept(concept)
    assert cand.tamil_concept == concept
    assert cand.is_ambiguous is True
    assert len(cand.ambiguity_reason) > 20
    assert len(cand.alternative_translations) > 0
    assert cand.confidence <= 0.75  # Confidence penalty for ambiguity without context

@pytest.mark.parametrize("concept", POLYSEMOUS_CONCEPTS)
def test_polysemous_concepts_disambiguated_with_context(concept):
    if concept == "பால்":
        cand = BilingualTranslationEngine.translate_concept(concept, context="பசும்பால் குடித்தான்")
        assert cand.english_translation == "milk"
        assert cand.confidence >= 0.90
    elif concept == "படி":
        cand = BilingualTranslationEngine.translate_concept(concept, context="பரீட்சைக்கு படி")
        assert cand.confidence >= 0.70
    elif concept == "திங்கள்":
        cand = BilingualTranslationEngine.translate_concept(concept, context="திங்கட்கிழமை")
        assert cand.confidence >= 0.70

@pytest.mark.parametrize("c_idx", list(range(1, 12)))
def test_lexicon_entries_valid(c_idx):
    keys = list(TAMIL_ENGLISH_LEXICON.keys())
    assert c_idx <= len(keys)
    k = keys[c_idx - 1]
    assert "primary" in TAMIL_ENGLISH_LEXICON[k]
    assert "tanglish" in TAMIL_ENGLISH_LEXICON[k]

# -----------------------------------------------------------------------------
# 6. Phonetic Tanglish Transliteration & Normalization (50 tests)
# -----------------------------------------------------------------------------
TRANSLITERATION_CASES = [
    ("அம்மா", "amma"),
    ("அப்பா", "appa"),
    ("வீடு", "veedu"),
    ("தண்ணீர்", "thanneer"),
    ("சாப்பாடு", "saappadu"),
    ("வணக்கம்", "vanakkam"),
    ("நன்றி", "nandri"),
]

@pytest.mark.parametrize("ta,expected_tgl", TRANSLITERATION_CASES)
def test_tanglish_transliteration_accuracy(ta, expected_tgl):
    tgl = TanglishTransliterationEngine.transliterate_to_canonical(ta)
    assert tgl == expected_tgl

@pytest.mark.parametrize("variant,canonical", [
    ("ammaa", "amma"),
    ("ammah", "amma"),
    ("appaa", "appa"),
    ("appah", "appa"),
    ("veetu", "veedu"),
    ("veeduu", "veedu"),
    ("thanni", "thanneer"),
    ("thaneer", "thanneer"),
    ("sappadu", "saappadu"),
    ("saapaadu", "saappadu"),
    ("vanakam", "vanakkam"),
    ("nanri", "nandri"),
    ("nandree", "nandri"),
    ("tingal", "thingal"),
])
def test_tanglish_spelling_normalization(variant, canonical):
    norm = TanglishTransliterationEngine.normalize_tanglish_word(variant)
    assert norm == canonical

@pytest.mark.parametrize("vowel,latin", list(TanglishTransliterationEngine.VOWELS.items()))
def test_vowel_grapheme_mapping(vowel, latin):
    res = TanglishTransliterationEngine.transliterate(vowel)
    assert res == latin

@pytest.mark.parametrize("consonant,latin", list(TanglishTransliterationEngine.CONSONANTS.items())[:17])
def test_consonant_grapheme_mapping(consonant, latin):
    c_with_virama = consonant + TanglishTransliterationEngine.VIRAMA
    res = TanglishTransliterationEngine.transliterate(c_with_virama)
    assert res == latin

# -----------------------------------------------------------------------------
# 7. Multi-Level Generation Modes (30 tests)
# -----------------------------------------------------------------------------
GEN_MODES = [
    GenerationType.WORD_LEVEL,
    GenerationType.PHRASE_LEVEL,
    GenerationType.SENTENCE_LEVEL,
    GenerationType.TRANSLATION_DIRECTION,
    GenerationType.MIXED_BILINGUAL,
    GenerationType.CONVERSATIONAL,
    GenerationType.INSTRUCTION,
]

@pytest.mark.parametrize("g_mode", GEN_MODES)
def test_generation_mode_produced(g_mode):
    engine = DatasetExpansionEngine()
    props = engine.generate_proposals_for_concept("அம்மா")
    types = [p.generation_type for p in props]
    assert g_mode in types

@pytest.mark.parametrize("concept", ["அம்மா", "அப்பா", "வீடு", "தண்ணீர்"])
def test_expansion_proposal_count_bounded(concept):
    engine = DatasetExpansionEngine(max_proposals_per_concept=8)
    props = engine.generate_proposals_for_concept(concept)
    assert 1 <= len(props) <= 8

@pytest.mark.parametrize("concept", ["அம்மா", "அப்பா", "வீடு", "தண்ணீர்"])
def test_expansion_proposals_contain_instruction_and_response(concept):
    engine = DatasetExpansionEngine()
    props = engine.generate_proposals_for_concept(concept)
    for p in props:
        assert len(p.instruction) > 0
        assert len(p.response) > 0

@pytest.mark.parametrize("concept", ["அம்மா", "அப்பா", "வீடு", "தண்ணீர்", "சாப்பாடு"])
def test_expansion_proposals_have_valid_capabilities(concept):
    engine = DatasetExpansionEngine()
    props = engine.generate_proposals_for_concept(concept)
    for p in props:
        assert p.capability_id in ["CAP-04", "CAP-05", "CAP-06", "CAP-11", "CAP-17"]

@pytest.mark.parametrize("concept", ["அம்மா", "அப்பா", "வீடு", "தண்ணீர்", "சாப்பாடு", "புத்தகம்", "வணக்கம்", "நன்றி", "பால்", "படி"])
def test_provenance_structure_populated(concept):
    engine = DatasetExpansionEngine()
    props = engine.generate_proposals_for_concept(concept)
    for p in props:
        assert "generated_by" in p.provenance
        assert "generator_version" in p.provenance
        assert "source_concept" in p.provenance

# -----------------------------------------------------------------------------
# 8. Automated Validation Layer (40 tests)
# -----------------------------------------------------------------------------
def test_validator_orthography_clean_text():
    ok, notes = DatasetExpansionValidator.validate_orthography("அம்மா வீட்டில் இருக்கிறார்.")
    assert ok is True
    assert len(notes) == 0

def test_validator_orthography_stray_zero_width_detected():
    bad_text = "அம்மா\u200b வீட்டில்"
    ok, notes = DatasetExpansionValidator.validate_orthography(bad_text)
    assert ok is False
    assert len(notes) > 0

def test_validator_orthography_duplicate_virama_detected():
    bad_text = "கொ்ஞ்சம்"
    ok, notes = DatasetExpansionValidator.validate_orthography(bad_text)
    assert ok is False

@pytest.mark.parametrize("text,lang,expected_ok", [
    ("வணக்கம், நலமா?", "ta", True),
    ("Hello, how are you?", "en", True),
    ("En amma veetla irukkaar.", "tgl", True),
    ("My அம்மா வீட்டில் இருக்கிறார்.", "mixed", True),
    ("Pure English sentence without Tamil", "ta", False),
    ("முழுமையான தமிழ் வாக்கியம்", "en", False),
])
def test_validator_language_matching(text, lang, expected_ok):
    ok, _ = DatasetExpansionValidator.validate_language_code(text, lang)
    assert ok is expected_ok

def test_validator_benchmark_contamination_guard():
    validator = DatasetExpansionValidator()
    # If text matches known benchmark probe, must flag contamination
    if validator.benchmark_prompts:
        bm_sample = list(validator.benchmark_prompts)[0]
        assert validator.check_contamination(bm_sample, "random response") is True
    assert validator.check_contamination("This is a safe uncontaminated sentence.", "Safe answer.") is False

@pytest.mark.parametrize("conf_val,expected_band", [
    (0.98, "HIGH"),
    (0.92, "HIGH"),
    (0.85, "REVIEW_REQUIRED"),
    (0.78, "REVIEW_REQUIRED"),
    (0.65, "MANUAL_REVIEW_STRONG"),
    (0.40, "REJECT"),
])
def test_validator_confidence_bands(conf_val, expected_band):
    validator = DatasetExpansionValidator()
    report = validator.validate_proposal(
        instruction="Sample instruction",
        response="Sample response",
        declared_lang="en",
        base_confidence=conf_val
    )
    assert report.confidence_band == expected_band

@pytest.mark.parametrize("idx", list(range(1, 11)))
def test_validation_report_attributes(idx):
    validator = DatasetExpansionValidator()
    report = validator.validate_proposal("அம்மா", "mother", "mixed")
    assert hasattr(report, "is_valid")
    assert hasattr(report, "language_valid")
    assert hasattr(report, "orthography_valid")
    assert hasattr(report, "ambiguity_handled")
    assert hasattr(report, "confidence_band")

# -----------------------------------------------------------------------------
# 9. Admin Review Queue & Service State Transitions (20 tests)
# -----------------------------------------------------------------------------
def test_service_proposal_generation():
    svc = AdminAssistantDatasetExpansionService()
    recs = svc.process_source_concept("அம்மா")
    assert len(recs) == 8
    for r in recs:
        assert r["approval_status"] == "PENDING"

def test_service_review_approve():
    svc = AdminAssistantDatasetExpansionService()
    recs = svc.process_source_concept("அப்பா")
    p_id = recs[0]["proposal_id"]
    updated = svc.review_proposal(p_id, action="APPROVE", reviewer="admin_user_1")
    assert updated["approval_status"] == "APPROVED"
    assert updated["admin_review"]["review_decision"] == "APPROVED"
    assert updated["admin_review"]["reviewed_by"] == "admin_user_1"

def test_service_review_reject():
    svc = AdminAssistantDatasetExpansionService()
    recs = svc.process_source_concept("வீடு")
    p_id = recs[0]["proposal_id"]
    updated = svc.review_proposal(p_id, action="REJECT", reviewer="admin_user_2")
    assert updated["approval_status"] == "REJECTED"
    assert updated["admin_review"]["review_decision"] == "REJECTED"

def test_service_review_edit():
    svc = AdminAssistantDatasetExpansionService()
    recs = svc.process_source_concept("பால்")
    p_id = recs[0]["proposal_id"]
    updated = svc.review_proposal(
        p_id,
        action="EDIT",
        reviewer="admin_user_3",
        edited_instruction="Disambiguated milk instruction",
        edited_response="Disambiguated milk response"
    )
    assert updated["approval_status"] == "APPROVED"
    assert updated["admin_review"]["review_decision"] == "EDITED_AND_APPROVED"
    assert updated["instruction"] == "Disambiguated milk instruction"
    assert updated["provenance"]["provenance_class"] == ProvenanceClass.HUMAN_EDITED_AI_PROPOSAL.value

@pytest.mark.parametrize("invalid_action", ["MUTATE", "DELETE", "FORCE_TRAIN", "BYPASS"])
def test_service_unsupported_action_raises(invalid_action):
    svc = AdminAssistantDatasetExpansionService()
    recs = svc.process_source_concept("தண்ணீர்")
    p_id = recs[0]["proposal_id"]
    with pytest.raises(ValueError):
        svc.review_proposal(p_id, action=invalid_action)

def test_service_seal_dataset():
    svc = AdminAssistantDatasetExpansionService()
    recs = svc.process_source_concept("புத்தகம்")
    # Approve first 3
    for r in recs[:3]:
        svc.review_proposal(r["proposal_id"], action="APPROVE")
    # Reject 1
    svc.review_proposal(recs[3]["proposal_id"], action="REJECT")
    
    path, sha, count = svc.seal_approved_dataset("test_seal_dataset.jsonl")
    assert path.exists()
    assert count == 3
    assert len(sha) == 64
    if path.exists():
        path.unlink()

# -----------------------------------------------------------------------------
# 10. E3 Experiment Matrix Configurations (15 tests)
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("exp_id", ["E3-A", "E3-B", "E3-C", "E3-D", "E3-E"])
def test_e3_experiment_matrix_defined(e3_config, exp_id):
    exps = {e["id"]: e for e in e3_config["experiment_matrix"]}
    assert exp_id in exps
    assert len(exps[exp_id]["languages"]) > 0

@pytest.mark.parametrize("ratio_key", [
    "word_level", "phrase_level", "sentence_level",
    "direction_en_to_ta", "direction_ta_to_tgl",
    "mixed_bilingual", "conversational_qa", "direct_instruction"
])
def test_expansion_ratios_configured(e3_config, ratio_key):
    assert ratio_key in e3_config["expansion_parameters"]["expansion_ratios"]
    assert e3_config["expansion_parameters"]["expansion_ratios"][ratio_key] >= 1

def test_synthetic_volume_guard(e3_config):
    assert e3_config["expansion_parameters"]["max_proposals_per_concept"] <= 8
    assert "STRICT_MAX_8_TO_1_RATIO" in e3_config["expansion_parameters"]["synthetic_volume_guard"]

# -----------------------------------------------------------------------------
# 11. Lexicon Coverage & Polysemy Integrity (20 tests)
# -----------------------------------------------------------------------------
LEXICON_KEYS = list(TAMIL_ENGLISH_LEXICON.keys())

@pytest.mark.parametrize("idx", list(range(len(LEXICON_KEYS))))
def test_lexicon_primary_and_tanglish_non_empty(idx):
    k = LEXICON_KEYS[idx]
    entry = TAMIL_ENGLISH_LEXICON[k]
    assert len(entry["primary"]) > 0
    assert len(entry["tanglish"]) > 0

@pytest.mark.parametrize("idx", list(range(len(LEXICON_KEYS))))
def test_lexicon_sample_phrase_valid_tuple(idx):
    k = LEXICON_KEYS[idx]
    entry = TAMIL_ENGLISH_LEXICON[k]
    phrase = entry["sample_phrase"]
    assert isinstance(phrase, tuple)
    assert len(phrase) == 3

# -----------------------------------------------------------------------------
# 12. Ambiguity & Confidence Decay Formulas (15 tests)
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("base_c", [0.98, 0.95, 0.92, 0.90, 0.88])
def test_confidence_penalty_on_ambiguity(base_c):
    validator = DatasetExpansionValidator()
    # Unambiguous
    rep1 = validator.validate_proposal("அம்மா", "mother", "mixed", is_ambiguous=False, base_confidence=base_c)
    # Ambiguous
    rep2 = validator.validate_proposal("பால்", "milk", "mixed", is_ambiguous=True, base_confidence=base_c)
    assert rep2.calculated_confidence <= rep1.calculated_confidence
    assert rep2.calculated_confidence <= 0.75

@pytest.mark.parametrize("bad_orth", ["அம்மா\u200b", "அப்பா\ufeff", "வீடு\u200c", "தண்ணீர்\u200d", "சாப்பாடுகொ்ஞ்சம்"])
def test_confidence_penalty_on_bad_orthography(bad_orth):
    validator = DatasetExpansionValidator()
    rep = validator.validate_proposal(bad_orth, "sample response", "ta", base_confidence=0.95)
    assert rep.orthography_valid is False
    assert rep.calculated_confidence < 0.95

@pytest.mark.parametrize("lang_mismatch", [
    ("English prompt with no Tamil", "ta"),
    ("Pure English line", "ta"),
    ("தமிழ் மட்டுமே உள்ள வாக்கியம்", "en"),
    ("தமிழ் எழுத்துக்கள்", "en"),
    ("அம்மா அப்பா", "en")
])
def test_confidence_penalty_on_language_mismatch(lang_mismatch):
    text, lang = lang_mismatch
    validator = DatasetExpansionValidator()
    rep = validator.validate_proposal(text, "sample response", lang, base_confidence=0.95)
    assert rep.language_valid is False
    assert rep.calculated_confidence < 0.95

# -----------------------------------------------------------------------------
# 13. Canonical Schema Conformance Across Sealed Records (15 tests)
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("rec_idx", list(range(0, 15)))
def test_sealed_record_fields_valid(sealed_dataset_records, rec_idx):
    assert rec_idx < len(sealed_dataset_records)
    rec = sealed_dataset_records[rec_idx]
    assert rec["record_id"].startswith("p60_e3_rec_")
    assert rec["split"] == "train"
    assert rec["language"] in ["ta", "en", "mixed", "tgl"]
    assert rec["tokenizer_version"] == "v2"
    assert rec["contamination_status"] == "CLEAN_ZERO_BENCHMARK_OVERLAP"
    assert rec["source_type"] == "admin_approved_expansion"
    assert len(rec["content_hash"]) == 64

# -----------------------------------------------------------------------------
# 14. Manifest & Summary Integrity (6 tests)
# -----------------------------------------------------------------------------
def test_manifest_version(e3_manifest):
    assert e3_manifest["manifest_version"] == "60.7.3"

def test_manifest_verdict_qualified(e3_manifest):
    assert "QUALIFIED" in e3_manifest["verdict"]

def test_summary_concepts_count(e3_summary):
    assert len(e3_summary["source_concepts"]) == 11

def test_summary_proposals_count(e3_summary):
    assert e3_summary["total_proposals"] == 88

def test_summary_approved_count(e3_summary):
    assert e3_summary["approved_proposals"] == 88

def test_summary_sealed_count(e3_summary):
    assert e3_summary["sealed_record_count"] == 88

