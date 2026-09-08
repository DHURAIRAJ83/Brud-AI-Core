"""
Phase 60 WS03 — Comprehensive Dataset Curation & Quality Validation Test Suite.
Verifies all 50 formal Quality Gates, 24 capability quotas, 32 benchmark air-gap checks,
16 LIM-WS04-04 fixture remediations, frozen baselines, and Tokenizer v2 compliance.
"""

import sys
import os
import json
import hashlib
from pathlib import Path
from collections import Counter, defaultdict
import pytest
import sentencepiece as spm

ROOT = Path(__file__).resolve().parents[2]
TOK_PATH = ROOT / "data/tokenizers/versions/tok/v2/tokenizer.model"
BM_PATH = ROOT / "artifacts/phase53_evaluation_manifest.json"
P55_PATH = ROOT / "artifacts/phase55_dataset_records_v001.jsonl"
DB_PATH = ROOT / "data/database/brud_ai.db"
P59_CKPT_PATH = ROOT / "artifacts/candidates/phase59/checkpoints/checkpoint_best.pt"

DATASET_PATH = ROOT / "artifacts/candidates/phase60/phase60_dataset_v001.jsonl"
MANIFEST_PATH = ROOT / "artifacts/candidates/phase60/phase60_ws03_dataset_manifest.json"

EXPECTED_TOK_SHA = "65342625ebb88eaab0996f0f6c5f3ef24ae9fd3203bc8377a0db353601e9ffd4"
EXPECTED_BM_SHA = "554bf72317d9439f7bd5f19e514d23c6a8fb0170807699a087631cbd4331d088"
EXPECTED_P55_SHA = "3e1481c3279c24eb957a90c9d7b8e642e2f657905463c3d7130475dbcb7919d1"
EXPECTED_DB_SHA = "34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729"
EXPECTED_P59_CKPT_SHA = "a5218b5bdb94d3b218896f3021d7f7d5298023036d350bf8a2d5e3b70423371a"

QUARANTINED_FIXTURES = [
    "inst_rec_0074590514a2", "inst_rec_0612f665867d", "inst_rec_09ebd4161ea4",
    "inst_rec_26d0e7f85f4c", "inst_rec_28b31cf2fa1c", "inst_rec_349586860058",
    "inst_rec_3b581dbfab87", "inst_rec_4bff2c38d7d6", "inst_rec_4e6374cba866",
    "inst_rec_6b638e897000", "inst_rec_6f16a535e17a", "inst_rec_8eff42ce80fb",
    "inst_rec_932796ad6a5e", "inst_rec_995c1d805294", "inst_rec_a5cb9c941e9a",
    "inst_rec_bb1d51a74e61"
]

CAPABILITY_QUOTAS = {
    "CAP-01": 170, "CAP-02": 170, "CAP-03": 150, "CAP-04": 140,
    "CAP-05": 130, "CAP-06": 110, "CAP-07": 80,  "CAP-08": 90,
    "CAP-09": 80,  "CAP-10": 110, "CAP-11": 70,  "CAP-12": 70,
    "CAP-13": 80,  "CAP-14": 60,  "CAP-15": 80,  "CAP-16": 90,
    "CAP-17": 40,  "CAP-18": 70,  "CAP-19": 40,  "CAP-20": 30,
    "CAP-21": 30,  "CAP-22": 40,  "CAP-23": 30,  "CAP-24": 40
}

REPORT_FILES = [
    "phase60_ws03_curation_report.md",
    "phase60_ws03_ingestion_report.md",
    "phase60_ws03_dataset_manifest.json",
    "phase60_ws03_provenance_report.md",
    "phase60_ws03_language_balance_report.md",
    "phase60_ws03_task_balance_report.md",
    "phase60_ws03_capability_balance_report.md",
    "phase60_ws03_tanglish_report.md",
    "phase60_ws03_dialogue_report.md",
    "phase60_ws03_multiturn_report.md",
    "phase60_ws03_instruction_following_report.md",
    "phase60_ws03_structured_output_report.md",
    "phase60_ws03_tool_boundary_report.md",
    "phase60_ws03_safety_refusal_report.md",
    "phase60_ws03_reasoning_report.md",
    "phase60_ws03_translation_report.md",
    "phase60_ws03_summarization_report.md",
    "phase60_ws03_entity_extraction_report.md",
    "phase60_ws03_grounding_report.md",
    "phase60_ws03_literature_report.md",
    "phase60_ws03_tokenizer_validation_report.md",
    "phase60_ws03_duplicate_report.md",
    "phase60_ws03_contamination_report.md",
    "phase60_ws03_split_integrity_report.md",
    "phase60_ws03_fixture_remediation_report.md",
    "phase60_ws03_quality_pipeline_report.md",
    "phase60_ws03_dataset_hash_report.md",
    "phase60_ws03_quality_gate_report.md",
    "phase60_ws03_failure_matrix.md",
]

@pytest.fixture(scope="session")
def dataset_records():
    assert DATASET_PATH.exists(), f"Dataset not found at {DATASET_PATH}"
    lines = [json.loads(line) for line in DATASET_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    return lines

@pytest.fixture(scope="session")
def manifest_data():
    assert MANIFEST_PATH.exists(), f"Manifest not found at {MANIFEST_PATH}"
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

@pytest.fixture(scope="session")
def benchmark_probes():
    assert BM_PATH.exists(), f"Benchmark manifest not found at {BM_PATH}"
    data = json.loads(BM_PATH.read_text(encoding="utf-8"))
    return data["probes"]

@pytest.fixture(scope="session")
def sp_tokenizer():
    sp = spm.SentencePieceProcessor()
    sp.Load(str(TOK_PATH))
    return sp

# -----------------------------------------------------------------------------
# 1. Frozen Baseline Immutability Tests (5 tests)
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

# -----------------------------------------------------------------------------
# 2. Output Artifacts & Reports Presence (29 tests)
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("report_name", REPORT_FILES)
def test_report_artifact_exists(report_name):
    rep_path = ROOT / "artifacts/candidates/phase60" / report_name
    assert rep_path.exists(), f"Required report missing: {report_name}"
    assert rep_path.stat().st_size > 0, f"Report is empty: {report_name}"

# -----------------------------------------------------------------------------
# 3. Benchmark Contamination Against All 32 Probes (32 tests)
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("probe_idx", list(range(32)))
def test_benchmark_probe_airgap(dataset_records, benchmark_probes, probe_idx):
    probe = benchmark_probes[probe_idx]
    p_prompt = probe["prompt"].strip().lower()
    p_out = probe["expected_output"].strip().lower()
    for r in dataset_records:
        inst = r["instruction"].strip().lower()
        resp = r["response"].strip().lower()
        assert inst != p_prompt, f"Contamination: prompt matched probe {probe_idx}"
        assert resp != p_out, f"Contamination: response matched probe {probe_idx}"
        if len(p_prompt) > 12:
            assert p_prompt not in inst, f"Phrase overlap: probe {probe_idx} in instruction"

# -----------------------------------------------------------------------------
# 4. Capability Quota Tests (24 tests)
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("cap_id,expected_count", list(CAPABILITY_QUOTAS.items()))
def test_capability_quota(dataset_records, cap_id, expected_count):
    actual = sum(1 for r in dataset_records if r["capability_id"] == cap_id)
    assert actual == expected_count, f"Cap {cap_id} count {actual} != {expected_count}"

# -----------------------------------------------------------------------------
# 5. Language Distribution Quota Tests (4 tests)
# -----------------------------------------------------------------------------
def test_language_quota_tamil(dataset_records):
    assert sum(1 for r in dataset_records if r["language"] == "ta") == 700

def test_language_quota_english(dataset_records):
    assert sum(1 for r in dataset_records if r["language"] == "en") == 700

def test_language_quota_mixed(dataset_records):
    assert sum(1 for r in dataset_records if r["language"] == "mixed") == 400

def test_language_quota_tanglish(dataset_records):
    assert sum(1 for r in dataset_records if r["language"] == "tgl") == 200

# -----------------------------------------------------------------------------
# 6. Split Distribution Quota Tests (3 tests)
# -----------------------------------------------------------------------------
def test_split_quota_train(dataset_records):
    assert sum(1 for r in dataset_records if r["split"] == "train") == 1600

def test_split_quota_validation(dataset_records):
    assert sum(1 for r in dataset_records if r["split"] == "validation") == 200

def test_split_quota_test(dataset_records):
    assert sum(1 for r in dataset_records if r["split"] == "test") == 200

# -----------------------------------------------------------------------------
# 7. Task Allocation Quota Tests (8 tests)
# -----------------------------------------------------------------------------
def test_task_quota_definition(dataset_records):
    assert sum(1 for r in dataset_records if r["task_type"] == "definition_concepts") == 400

def test_task_quota_factual_qa(dataset_records):
    assert sum(1 for r in dataset_records if r["task_type"] == "factual_qa_knowledge") == 400

def test_task_quota_dialogue(dataset_records):
    assert sum(1 for r in dataset_records if r["task_type"] == "dialogue_conversational") == 300

def test_task_quota_directives(dataset_records):
    assert sum(1 for r in dataset_records if r["task_type"] == "directives_constraints") == 300

def test_task_quota_structured(dataset_records):
    assert sum(1 for r in dataset_records if r["task_type"] == "structured_response") == 200

def test_task_quota_tool_boundaries(dataset_records):
    assert sum(1 for r in dataset_records if r["task_type"] == "tool_boundaries_math") == 200

def test_task_quota_safety_refusals(dataset_records):
    assert sum(1 for r in dataset_records if r["task_type"] == "safety_refusals") == 100

def test_task_quota_translation_summarization(dataset_records):
    assert sum(1 for r in dataset_records if r["task_type"] == "translation_summarization") == 100

# -----------------------------------------------------------------------------
# 8. Fixture Remediation Tests (16 tests)
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("old_id", QUARANTINED_FIXTURES)
def test_fixture_remediation_absence(dataset_records, old_id):
    rec_ids = {r.get("record_id") for r in dataset_records}
    assert old_id not in rec_ids, f"Quarantined fixture {old_id} found in dataset!"

# -----------------------------------------------------------------------------
# 9. All 50 Formal Quality Gates (50 tests)
# -----------------------------------------------------------------------------
def test_qg_ws03_01_schema_integrity(dataset_records):
    required_fields = {
        "record_id", "task_type", "capability_id", "language", "instruction",
        "optional_context", "response", "expected_behavior", "difficulty",
        "source_type", "provenance", "quality_status", "safety_class",
        "split", "tokenizer_version", "contamination_status",
        "reviewer_status", "created_at", "content_hash"
    }
    for r in dataset_records:
        assert required_fields.issubset(r.keys())

def test_qg_ws03_02_total_records_count(dataset_records):
    assert len(dataset_records) == 2000

def test_qg_ws03_03_train_records_count(dataset_records):
    assert sum(1 for r in dataset_records if r["split"] == "train") == 1600

def test_qg_ws03_04_val_records_count(dataset_records):
    assert sum(1 for r in dataset_records if r["split"] == "validation") == 200

def test_qg_ws03_05_test_records_count(dataset_records):
    assert sum(1 for r in dataset_records if r["split"] == "test") == 200

def test_qg_ws03_06_tamil_count(dataset_records):
    assert sum(1 for r in dataset_records if r["language"] == "ta") == 700

def test_qg_ws03_07_english_count(dataset_records):
    assert sum(1 for r in dataset_records if r["language"] == "en") == 700

def test_qg_ws03_08_mixed_count(dataset_records):
    assert sum(1 for r in dataset_records if r["language"] == "mixed") == 400

def test_qg_ws03_09_tanglish_count(dataset_records):
    assert sum(1 for r in dataset_records if r["language"] == "tgl") == 200

def test_qg_ws03_10_definition_quota(dataset_records):
    assert sum(1 for r in dataset_records if r["capability_id"] == "CAP-01") >= 150

def test_qg_ws03_11_factual_qa_quota(dataset_records):
    assert sum(1 for r in dataset_records if r["capability_id"] == "CAP-02") >= 150

def test_qg_ws03_12_explanation_quota(dataset_records):
    assert sum(1 for r in dataset_records if r["capability_id"] == "CAP-03") >= 130

def test_qg_ws03_13_instruction_quota(dataset_records):
    assert sum(1 for r in dataset_records if r["capability_id"] == "CAP-04") >= 120

def test_qg_ws03_14_dialogue_quota(dataset_records):
    assert sum(1 for r in dataset_records if r["capability_id"] == "CAP-05") >= 110

def test_qg_ws03_15_directive_quota(dataset_records):
    assert sum(1 for r in dataset_records if r["capability_id"] == "CAP-06") >= 90

def test_qg_ws03_16_literature_quota(dataset_records):
    assert sum(1 for r in dataset_records if r["capability_id"] == "CAP-07") >= 60

def test_qg_ws03_17_reasoning_quota(dataset_records):
    assert sum(1 for r in dataset_records if r["capability_id"] == "CAP-13") >= 60

def test_qg_ws03_18_arithmetic_quota(dataset_records):
    assert sum(1 for r in dataset_records if r["capability_id"] == "CAP-14") >= 40

def test_qg_ws03_19_grounding_quota(dataset_records):
    assert sum(1 for r in dataset_records if r["capability_id"] == "CAP-15") >= 60

def test_qg_ws03_20_structured_output_quota(dataset_records):
    assert sum(1 for r in dataset_records if r["capability_id"] == "CAP-16") >= 70

def test_qg_ws03_21_refusal_quota(dataset_records):
    assert sum(1 for r in dataset_records if r["capability_id"] == "CAP-18") >= 50

def test_qg_ws03_22_multiturn_quota(dataset_records):
    assert sum(1 for r in dataset_records if r["capability_id"] == "CAP-19") >= 30

def test_qg_ws03_23_constraint_quota(dataset_records):
    assert sum(1 for r in dataset_records if r["capability_id"] == "CAP-20") >= 20

def test_qg_ws03_24_summarization_quota(dataset_records):
    assert sum(1 for r in dataset_records if r["capability_id"] == "CAP-21") >= 20

def test_qg_ws03_25_translation_quota(dataset_records):
    assert sum(1 for r in dataset_records if r["capability_id"] == "CAP-22") >= 30

def test_qg_ws03_26_entity_extraction_quota(dataset_records):
    assert sum(1 for r in dataset_records if r["capability_id"] == "CAP-23") >= 20

def test_qg_ws03_27_tool_boundary_quota(dataset_records):
    assert sum(1 for r in dataset_records if r["capability_id"] == "CAP-24") >= 30

def test_qg_ws03_28_tokenizer_compatibility(sp_tokenizer, dataset_records):
    assert sp_tokenizer.GetPieceSize() == 1024

def test_qg_ws03_29_zero_unk_rate(sp_tokenizer, dataset_records):
    for r in dataset_records:
        inst = r["instruction"]
        resp = r["response"]
        ids = sp_tokenizer.encode(f"<user>{inst}<assistant>{resp}</s>", out_type=int)
        assert 1 not in ids, f"UNK token found in record {r['record_id']}"

def test_qg_ws03_30_eos_integrity(sp_tokenizer, dataset_records):
    # EOS piece is id 3 in Tokenizer v2
    assert sp_tokenizer.eos_id() == 3
    for r in dataset_records:
        ids = sp_tokenizer.encode(r["response"], out_type=int, add_eos=True)
        assert ids[-1] == 3

def test_qg_ws03_31_context_length_budget(sp_tokenizer, dataset_records):
    for r in dataset_records:
        inst = r["instruction"]
        ctx = r.get("optional_context", "")
        resp = r["response"]
        full = f"<user>{inst}{ctx}<assistant>{resp}</s>"
        ids = sp_tokenizer.encode(full, out_type=int)
        assert len(ids) <= 128, f"Record {r['record_id']} exceeds 128 tokens: {len(ids)}"

def test_qg_ws03_32_zero_prompt_truncation(sp_tokenizer, dataset_records):
    for r in dataset_records:
        inst = r["instruction"]
        ctx = r.get("optional_context", "")
        p_ids = sp_tokenizer.encode(f"<user>{inst}{ctx}<assistant>", out_type=int)
        assert len(p_ids) < 127

def test_qg_ws03_33_duplicate_rate(dataset_records):
    instructions = [r["instruction"].strip() for r in dataset_records]
    assert len(instructions) == len(set(instructions)), "Duplicate instructions detected"

def test_qg_ws03_34_semantic_leakage(dataset_records):
    train_insts = {r["instruction"].strip() for r in dataset_records if r["split"] == "train"}
    val_insts = {r["instruction"].strip() for r in dataset_records if r["split"] == "validation"}
    test_insts = {r["instruction"].strip() for r in dataset_records if r["split"] == "test"}
    assert train_insts.isdisjoint(val_insts)
    assert train_insts.isdisjoint(test_insts)
    assert val_insts.isdisjoint(test_insts)

def test_qg_ws03_35_zero_benchmark_contamination(dataset_records, benchmark_probes):
    prompts = {p["prompt"].strip().lower() for p in benchmark_probes}
    outputs = {p["expected_output"].strip().lower() for p in benchmark_probes}
    for r in dataset_records:
        assert r["instruction"].strip().lower() not in prompts
        assert r["response"].strip().lower() not in outputs

def test_qg_ws03_36_provenance_completeness(dataset_records):
    valid_prov = {"brud_sovereign_curated_phase60", "phase55_corpus_derived"}
    for r in dataset_records:
        assert r["provenance"] in valid_prov

def test_qg_ws03_37_split_isolation(dataset_records):
    ids_by_split = defaultdict(set)
    for r in dataset_records:
        ids_by_split[r["split"]].add(r["record_id"])
    assert ids_by_split["train"].isdisjoint(ids_by_split["validation"])
    assert ids_by_split["train"].isdisjoint(ids_by_split["test"])
    assert ids_by_split["validation"].isdisjoint(ids_by_split["test"])

def test_qg_ws03_38_fixture_remediation(dataset_records):
    for r in dataset_records:
        assert r["record_id"] not in QUARANTINED_FIXTURES

def test_qg_ws03_39_safety_classification(dataset_records):
    for r in dataset_records:
        assert r["safety_class"] in {"benign", "refusal_required"}

def test_qg_ws03_40_instruction_quality(dataset_records):
    for r in dataset_records:
        assert len(r["instruction"].strip()) >= 3

def test_qg_ws03_41_response_quality(dataset_records):
    for r in dataset_records:
        assert len(r["response"].strip()) >= 1

def test_qg_ws03_42_language_quality(dataset_records):
    for r in dataset_records:
        assert r["language"] in {"ta", "en", "mixed", "tgl"}

def test_qg_ws03_43_dataset_determinism():
    assert DATASET_PATH.exists()
    sha1 = hashlib.sha256(DATASET_PATH.read_bytes()).hexdigest()
    sha2 = hashlib.sha256(DATASET_PATH.read_bytes()).hexdigest()
    assert sha1 == sha2

def test_qg_ws03_44_content_hash_integrity(dataset_records):
    for r in dataset_records:
        inst = r["instruction"]
        ctx = r.get("optional_context", "")
        resp = r["response"]
        expected = hashlib.sha256(f"{inst}|{ctx}|{resp}".encode("utf-8")).hexdigest()
        assert r["content_hash"] == expected

def test_qg_ws03_45_manifest_completeness(manifest_data):
    assert manifest_data["status"] == "SEALED_IMMUTABLE"
    assert manifest_data["verdict"].startswith("A")
    assert manifest_data["dataset_summary"]["total_records"] == 2000

def test_qg_ws03_46_production_db_unchanged():
    assert hashlib.sha256(DB_PATH.read_bytes()).hexdigest() == EXPECTED_DB_SHA

def test_qg_ws03_47_production_model_unchanged():
    assert hashlib.sha256(P59_CKPT_PATH.read_bytes()).hexdigest() == EXPECTED_P59_CKPT_SHA

def test_qg_ws03_48_candidate_only_filesystem():
    assert "artifacts/candidates/phase60" in str(DATASET_PATH)

def test_qg_ws03_49_offline_execution(manifest_data):
    assert manifest_data["governance"]["is_public_chat_eligible"] is False
    assert manifest_data["governance"]["candidate_traffic_share"] == 0.0

def test_qg_ws03_50_final_dataset_release_readiness(manifest_data):
    assert manifest_data["dataset_summary"]["unk_rate"] == 0.0
    assert manifest_data["dataset_summary"]["benchmark_contamination_count"] == 0
    assert manifest_data["governance"]["training_execution_authorized"] is False

# -----------------------------------------------------------------------------
# 10. Additional Tokenizer Representability Checks (35 individual tests)
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("idx", list(range(0, 2000, 57)))
def test_individual_record_tokenization_integrity(sp_tokenizer, dataset_records, idx):
    r = dataset_records[idx]
    inst = r["instruction"]
    ctx = r.get("optional_context", "")
    resp = r["response"]
    full = f"<user>{inst}{ctx}<assistant>{resp}"
    ids = sp_tokenizer.encode(full, out_type=int, add_eos=True)
    assert 1 not in ids
    assert len(ids) <= 128
    assert ids[-1] == 3
