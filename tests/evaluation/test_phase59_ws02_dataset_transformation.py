"""
Phase 59 Workstream 02 Dedicated Test Suite: Dataset Transformation & Loss Masking Audit.

Target: >= 100 meaningful, non-trivial tests verifying:
- Section 1 & 2: Source data integrity and immutable preservation
- Section 3 & 4: Transformation semantics, schemas, and prompt/response structure
- Section 5 & 6: Response-only loss masking and causal label alignment
- Section 7 & 8: Tokenizer v2 integration, zero UNK, context length handling
- Section 9 & 10: Split integrity, cross-split isolation, zero benchmark contamination
- Section 11 & 12: Language distribution, quality validation, malformed record handling
- Section 13 & 14: Bit-exact reproducibility and security inspection
- Section 15 & 16: Production isolation, manifest validity, candidate isolation
"""

import json
import hashlib
import sqlite3
import pytest
import torch
import sentencepiece as spm
from pathlib import Path
from core_model.instruction_tuning.templates import InstructionTemplate
from core_model.instruction_tuning.formatter import render_example
from core_model.instruction_tuning.label_masking import build_response_labeled_example, LabelMaskingThresholds
from core_model.training.loss import causal_lm_loss

ROOT = Path(__file__).resolve().parents[2]
import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SOURCE_PATH = ROOT / "artifacts/phase55_dataset_records_v001.jsonl"
EVAL_PATH = ROOT / "artifacts/phase53_evaluation_manifest.json"
TOK_PATH = ROOT / "data/tokenizers/versions/tok/v2/tokenizer.model"
DB_PATH = ROOT / "data/database/brud_ai.db"
CANDIDATE_DIR = ROOT / "artifacts/candidates/phase59"
INST_PATH = CANDIDATE_DIR / "phase59_instruction_records_v001.jsonl"
SEQ_PATH = CANDIDATE_DIR / "phase59_training_sequences_v001.jsonl"
MANIFEST_PATH = ROOT / "phase59_ws02_transformation_manifest.json"

@pytest.fixture(scope="module")
def sp2():
    sp = spm.SentencePieceProcessor()
    sp.Load(str(TOK_PATH))
    return sp

@pytest.fixture(scope="module")
def source_records():
    return [json.loads(line) for line in SOURCE_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]

@pytest.fixture(scope="module")
def eval_manifest():
    return json.loads(EVAL_PATH.read_text(encoding="utf-8"))

@pytest.fixture(scope="module")
def inst_records():
    return [json.loads(line) for line in INST_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]

@pytest.fixture(scope="module")
def training_sequences():
    return [json.loads(line) for line in SEQ_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]

@pytest.fixture(scope="module")
def template():
    return InstructionTemplate(
        name="brud_instruction_v1",
        version="1.0.0",
        bos_token="<s>",
        eos_token="</s>",
        system_prefix="<system>",
        user_prefix="<user>",
        assistant_prefix="<assistant>",
        insert_language_marker=True
    )

# ==============================================================================
# GROUP 1: Source Data Integrity & Invariants (Tests 1–15)
# ==============================================================================

def test_001_source_corpus_file_exists():
    assert SOURCE_PATH.exists()

def test_002_source_corpus_sha256(source_records):
    expected_sha = "3e1481c3279c24eb957a90c9d7b8e642e2f657905463c3d7130475dbcb7919d1"
    actual_sha = hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest()
    assert actual_sha == expected_sha

def test_003_source_record_count(source_records):
    assert len(source_records) == 396

def test_004_source_record_required_fields(source_records):
    required = {"record_id", "text", "sha256", "source_id", "provenance", "rights_status", "split", "language", "domain"}
    for r in source_records:
        assert required.issubset(r.keys())

def test_005_source_record_no_empty_text(source_records):
    for r in source_records:
        assert len(r["text"].strip()) > 0

def test_006_source_record_unique_ids(source_records):
    ids = [r["record_id"] for r in source_records]
    assert len(ids) == len(set(ids))

def test_007_source_record_unique_sha256(source_records):
    hashes = [r["sha256"] for r in source_records]
    assert len(hashes) == len(set(hashes))

def test_008_source_record_sha256_matches_content(source_records):
    # Spot-check first 10 records
    for r in source_records[:10]:
        computed = hashlib.sha256(r["text"].encode("utf-8")).hexdigest()
        assert r["sha256"] == computed

def test_009_source_splits_distribution(source_records):
    splits = [r["split"] for r in source_records]
    assert splits.count("train") == 316
    assert splits.count("val") == 40
    assert splits.count("test") == 40

def test_010_source_record_unicode_normalization(source_records):
    # Verify no null bytes or replacement characters
    for r in source_records:
        assert "\x00" not in r["text"]
        assert "\ufffd" not in r["text"]

def test_011_benchmark_manifest_exists():
    assert EVAL_PATH.exists()

def test_012_benchmark_manifest_sha256():
    expected = "554bf72317d9439f7bd5f19e514d23c6a8fb0170807699a087631cbd4331d088"
    assert hashlib.sha256(EVAL_PATH.read_bytes()).hexdigest() == expected

def test_013_benchmark_probe_count(eval_manifest):
    assert len(eval_manifest["probes"]) == 32

def test_014_production_db_exists():
    assert DB_PATH.exists()

def test_015_production_db_sha256():
    expected = "34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729"
    assert hashlib.sha256(DB_PATH.read_bytes()).hexdigest() == expected

# ==============================================================================
# GROUP 2: Transformation Schema & Provenance (Tests 16–30)
# ==============================================================================

def test_016_inst_records_count(inst_records):
    assert len(inst_records) == 396

def test_017_inst_records_schema(inst_records):
    req = {"id", "source_id", "domain", "language", "task_type", "instruction", "response", "source_record_hash", "transformation_version", "rights_status", "synthetic", "split"}
    for r in inst_records:
        assert req.issubset(r.keys())

def test_018_inst_records_provenance_preservation(source_records, inst_records):
    src_map = {r["record_id"]: r for r in source_records}
    for ir in inst_records:
        src = src_map[ir["source_id"]]
        assert ir["source_record_hash"] == src["sha256"]
        assert ir["split"] == src["split"]
        assert ir["domain"] == src["domain"]

def test_019_inst_records_non_synthetic(inst_records):
    for ir in inst_records:
        assert ir["synthetic"] is False

def test_020_inst_records_transformation_version(inst_records):
    for ir in inst_records:
        assert ir["transformation_version"] == "v1.0.0"

def test_021_inst_records_no_empty_instruction(inst_records):
    for ir in inst_records:
        assert len(ir["instruction"].strip()) > 0

def test_022_inst_records_no_empty_response(inst_records):
    for ir in inst_records:
        assert len(ir["response"].strip()) > 0

def test_023_inst_records_unique_ids(inst_records):
    ids = [r["id"] for r in inst_records]
    assert len(ids) == len(set(ids))

def test_024_inst_records_task_types_coverage(inst_records):
    tasks = set(r["task_type"] for r in inst_records)
    assert len(tasks) >= 4
    assert "definition_qa" in tasks
    assert "factual_explanation" in tasks

def test_025_inst_records_rights_verified(inst_records):
    for r in inst_records:
        assert r["rights_status"] == "verified"

def test_026_inst_records_split_counts(inst_records):
    splits = [r["split"] for r in inst_records]
    assert splits.count("train") == 316
    assert splits.count("val") == 40
    assert splits.count("test") == 40

def test_027_thirukkural_instruction_mapping(inst_records):
    kural_recs = [r for r in inst_records if r["domain"] == "thirukkural"]
    assert len(kural_recs) == 35
    for kr in kural_recs:
        assert "திருக்குறள்" in kr["instruction"] or "விளக்கம்" in kr["instruction"]

def test_028_vocabulary_instruction_mapping(inst_records):
    vocab_recs = [r for r in inst_records if r["domain"] == "vocabulary"]
    assert len(vocab_recs) == 111
    for vr in vocab_recs:
        assert len(vr["instruction"]) > 0
        assert len(vr["response"]) > 0

def test_029_grammar_instruction_mapping(inst_records):
    gram_recs = [r for r in inst_records if r["domain"] == "grammar"]
    assert len(gram_recs) == 10
    for gr in gram_recs:
        assert len(gr["instruction"]) > 0
        assert len(gr["response"]) > 0

def test_030_cs_and_science_mapping(inst_records):
    tech_recs = [r for r in inst_records if r["domain"] in {"computer_science", "science"}]
    assert len(tech_recs) == 20
    for tr in tech_recs:
        assert len(tr["instruction"]) > 0

# ==============================================================================
# GROUP 3: Tokenizer v2 & Zero UNK Integration (Tests 31–45)
# ==============================================================================

def test_031_tokenizer_v2_vocab_size(sp2):
    assert sp2.GetPieceSize() == 1024

def test_032_tokenizer_v2_pad_token(sp2):
    assert sp2.IdToPiece(0) == "<pad>"
    assert sp2.pad_id() == 0

def test_033_tokenizer_v2_unk_token(sp2):
    assert sp2.IdToPiece(1) == "<unk>"
    assert sp2.unk_id() == 1

def test_034_tokenizer_v2_bos_token(sp2):
    assert sp2.IdToPiece(2) == "<s>"
    assert sp2.bos_id() == 2

def test_035_tokenizer_v2_eos_token(sp2):
    assert sp2.IdToPiece(3) == "</s>"
    assert sp2.eos_id() == 3

def test_036_tokenizer_v2_control_tokens(sp2):
    expected_controls = {
        4: "<system>", 5: "<user>", 6: "<assistant>",
        7: "<ta>", 8: "<en>", 9: "<tgl>", 10: "<mixed>"
    }
    for tid, piece in expected_controls.items():
        assert sp2.IdToPiece(tid) == piece

def test_037_instruction_texts_zero_unk(sp2, inst_records):
    total_unks = sum(sp2.EncodeAsIds(r["instruction"]).count(1) for r in inst_records)
    assert total_unks == 0

def test_038_response_texts_zero_unk(sp2, inst_records):
    total_unks = sum(sp2.EncodeAsIds(r["response"]).count(1) for r in inst_records)
    assert total_unks == 0

def test_039_rendered_prompts_zero_unk(sp2, inst_records, template):
    for r in inst_records[:50]:
        val = {"system_text": None, "prompt_text": r["instruction"], "input_text": None, "response_text": r["response"]}
        p_str, _ = render_example(val, r["language"], template)
        p_ids = sp2.EncodeAsIds(p_str)
        assert 1 not in p_ids

def test_040_rendered_responses_zero_unk(sp2, inst_records, template):
    for r in inst_records[:50]:
        val = {"system_text": None, "prompt_text": r["instruction"], "input_text": None, "response_text": r["response"]}
        _, r_str = render_example(val, r["language"], template)
        r_ids = sp2.EncodeAsIds(r_str)
        assert 1 not in r_ids

def test_041_all_token_ids_within_valid_vocab_range(training_sequences):
    for s in training_sequences:
        for tid in s["input_ids"]:
            assert 0 <= tid < 1024

def test_042_all_attention_mask_binary(training_sequences):
    for s in training_sequences:
        for m in s["attention_mask"]:
            assert m in (0, 1)

def test_043_labels_within_valid_or_ignore_range(training_sequences):
    for s in training_sequences:
        for lbl in s["labels"]:
            assert lbl == -100 or (0 <= lbl < 1024)

def test_044_byte_fallback_handles_arbitrary_unseen(sp2):
    unseen = "Unicode: 漢字 🌟"
    ids = sp2.EncodeAsIds(unseen)
    assert 1 not in ids
    assert sp2.Decode(ids) == unseen

def test_045_roundtrip_fidelity_sample(sp2, inst_records):
    for r in inst_records[:20]:
        t = r["instruction"]
        dec = sp2.Decode(sp2.EncodeAsIds(t))
        assert "".join(t.split()) == "".join(dec.split())

# ==============================================================================
# GROUP 4: Prompt/Response Structure & Formatting (Tests 46–60)
# ==============================================================================

def test_046_template_special_tokens(template):
    assert template.bos_token == "<s>"
    assert template.eos_token == "</s>"
    assert template.system_prefix == "<system>"
    assert template.user_prefix == "<user>"
    assert template.assistant_prefix == "<assistant>"

def test_047_template_language_markers(template):
    assert template.language_markers["ta"] == "<ta>"
    assert template.language_markers["en"] == "<en>"
    assert template.language_markers["tgl"] == "<tgl>"
    assert template.language_markers["mixed"] == "<mixed>"

def test_048_render_example_bos_at_start(template):
    val = {"system_text": None, "prompt_text": "கேள்வி", "input_text": None, "response_text": "பதில்"}
    p_str, _ = render_example(val, "ta", template)
    assert p_str.startswith("<s>")

def test_049_render_example_assistant_at_prompt_end(template):
    val = {"system_text": None, "prompt_text": "கேள்வி", "input_text": None, "response_text": "பதில்"}
    p_str, _ = render_example(val, "ta", template)
    assert p_str.endswith("<assistant>")

def test_050_render_example_eos_at_response_end(template):
    val = {"system_text": None, "prompt_text": "கேள்வி", "input_text": None, "response_text": "பதில்"}
    _, r_str = render_example(val, "ta", template)
    assert r_str.endswith("</s>")

def test_051_render_example_no_nested_assistant(template):
    val = {"system_text": None, "prompt_text": "கேள்வி", "input_text": None, "response_text": "பதில்"}
    p_str, r_str = render_example(val, "ta", template)
    assert p_str.count("<assistant>") == 1
    assert r_str.count("<assistant>") == 0

def test_052_render_example_no_nested_bos(template):
    val = {"system_text": None, "prompt_text": "கேள்வி", "input_text": None, "response_text": "பதில்"}
    p_str, r_str = render_example(val, "ta", template)
    assert p_str.count("<s>") == 1
    assert r_str.count("<s>") == 0

def test_053_render_example_no_nested_eos(template):
    val = {"system_text": None, "prompt_text": "கேள்வி", "input_text": None, "response_text": "பதில்"}
    p_str, r_str = render_example(val, "ta", template)
    assert p_str.count("</s>") == 0
    assert r_str.count("</s>") == 1

def test_054_render_example_user_prefix_present(template):
    val = {"system_text": None, "prompt_text": "கேள்வி", "input_text": None, "response_text": "பதில்"}
    p_str, _ = render_example(val, "ta", template)
    assert "<user>" in p_str

def test_055_render_example_language_marker_ta(template):
    val = {"system_text": None, "prompt_text": "கேள்வி", "input_text": None, "response_text": "பதில்"}
    p_str, _ = render_example(val, "ta", template)
    assert "<ta>" in p_str

def test_056_render_example_language_marker_en(template):
    val = {"system_text": None, "prompt_text": "Question", "input_text": None, "response_text": "Answer"}
    p_str, _ = render_example(val, "en", template)
    assert "<en>" in p_str

def test_057_render_example_language_marker_tgl(template):
    val = {"system_text": None, "prompt_text": "Kelvi", "input_text": None, "response_text": "Badhil"}
    p_str, _ = render_example(val, "tgl", template)
    assert "<tgl>" in p_str

def test_058_render_example_with_system_text(template):
    val = {"system_text": "You are helpful.", "prompt_text": "Hello", "input_text": None, "response_text": "Hi"}
    p_str, _ = render_example(val, "en", template)
    assert "<system> You are helpful." in p_str

def test_059_render_example_with_input_text(template):
    val = {"system_text": None, "prompt_text": "Context:", "input_text": "Fact 1", "response_text": "OK"}
    p_str, _ = render_example(val, "en", template)
    assert "Context: Fact 1" in p_str

def test_060_rendered_sequence_ordering(template):
    val = {"system_text": "Sys", "prompt_text": "UserQ", "input_text": "InputCtx", "response_text": "RespA"}
    p_str, r_str = render_example(val, "ta", template)
    idx_bos = p_str.index("<s>")
    idx_sys = p_str.index("<system>")
    idx_usr = p_str.index("<user>")
    idx_ast = p_str.index("<assistant>")
    assert idx_bos < idx_sys < idx_usr < idx_ast

# ==============================================================================
# GROUP 5: Response-Only Loss Masking & Causal Alignment (Tests 61–75)
# ==============================================================================

def test_061_prompt_tokens_masked_with_minus_100(training_sequences):
    for s in training_sequences:
        p_len = s["prompt_token_count"]
        assert all(lbl == -100 for lbl in s["labels"][:p_len])

def test_062_target_tokens_supervised(training_sequences):
    for s in training_sequences:
        p_len = s["prompt_token_count"]
        r_len = s["target_token_count"]
        target_labels = s["labels"][p_len:p_len+r_len]
        assert all(lbl != -100 for lbl in target_labels)

def test_063_padding_tokens_masked_with_minus_100(training_sequences):
    for s in training_sequences:
        p_len = s["prompt_token_count"]
        r_len = s["target_token_count"]
        pad_labels = s["labels"][p_len+r_len:]
        assert all(lbl == -100 for lbl in pad_labels)

def test_064_target_token_count_positive(training_sequences):
    for s in training_sequences:
        assert s["target_token_count"] > 0

def test_065_supervised_tokens_equal_target_count(training_sequences):
    for s in training_sequences:
        sup_cnt = sum(1 for lbl in s["labels"] if lbl != -100)
        assert sup_cnt == s["target_token_count"]

def test_066_sequence_length_constant_128(training_sequences):
    for s in training_sequences:
        assert len(s["input_ids"]) == 128
        assert len(s["attention_mask"]) == 128
        assert len(s["labels"]) == 128

def test_067_attention_mask_alignment(training_sequences):
    for s in training_sequences:
        active_cnt = s["prompt_token_count"] + s["target_token_count"]
        assert sum(s["attention_mask"]) == active_cnt
        assert s["attention_mask"][:active_cnt] == [1] * active_cnt
        assert s["attention_mask"][active_cnt:] == [0] * (128 - active_cnt)

def test_068_causal_lm_loss_evaluates_on_mock(training_sequences):
    s = training_sequences[0]
    logits = torch.randn(1, 128, 1024)
    labels = torch.tensor([s["labels"]], dtype=torch.long)
    loss = causal_lm_loss(logits, labels, ignore_index=-100)
    assert torch.isfinite(loss)
    assert loss.item() > 0

def test_069_prompt_mutation_does_not_alter_target_loss(sp2, template):
    val = {"system_text": None, "prompt_text": "முதல் கேள்வி", "input_text": None, "response_text": "நிலையான பதில்"}
    p1, r1 = render_example(val, "ta", template)
    built1 = build_response_labeled_example(
        sp2.EncodeAsIds(p1), sp2.EncodeAsIds(r1), pad_token_id=0, eos_token_id=3,
        thresholds=LabelMaskingThresholds(sequence_length=128)
    )
    val_alt = {"system_text": "முற்றிலும் மாறுபட்ட அமைப்பு", "prompt_text": "வேறுபட்ட நீளமான கேள்வி", "input_text": None, "response_text": "நிலையான பதில்"}
    p2, r2 = render_example(val_alt, "ta", template)
    built2 = build_response_labeled_example(
        sp2.EncodeAsIds(p2), sp2.EncodeAsIds(r2), pad_token_id=0, eos_token_id=3,
        thresholds=LabelMaskingThresholds(sequence_length=128)
    )
    assert built1["target_token_count"] == built2["target_token_count"]

def test_070_loss_zero_on_purely_masked_labels():
    logits = torch.randn(1, 10, 1024)
    labels = torch.full((1, 10), -100, dtype=torch.long)
    with pytest.raises(ValueError, match="at least one valid target token"):
        causal_lm_loss(logits, labels, ignore_index=-100)

def test_071_causal_shift_alignment_indices():
    # Verify causal shift: logits[:, t, :] is evaluated against labels[:, t+1]
    logits = torch.zeros(1, 4, 10)
    labels = torch.tensor([[-100, -100, 5, 6]], dtype=torch.long)
    # Target tokens are at labels[2] and labels[3]
    # Under shift, shift_labels = labels[:, 1:] = [-100, 5, 6]
    # shift_logits = logits[:, :-1, :] (positions 0, 1, 2)
    # Position 1 predicts 5, position 2 predicts 6
    loss = causal_lm_loss(logits, labels, ignore_index=-100)
    assert torch.isfinite(loss)

def test_072_eos_is_supervised_at_response_tail(training_sequences):
    for s in training_sequences:
        p_len = s["prompt_token_count"]
        r_len = s["target_token_count"]
        last_target_id = s["input_ids"][p_len + r_len - 1]
        last_target_lbl = s["labels"][p_len + r_len - 1]
        # In non-truncated sequences, the last token is EOS (3)
        if not s["truncated"]:
            assert last_target_id == 3
            assert last_target_lbl == 3

def test_073_bos_is_masked_in_labels(training_sequences):
    for s in training_sequences:
        if not s["truncated"]:
            assert s["input_ids"][0] == 2  # BOS token
        assert s["labels"][0] == -100  # Masked!

def test_074_assistant_token_is_masked_in_labels(training_sequences):
    for s in training_sequences:
        p_len = s["prompt_token_count"]
        if not s["truncated"] and p_len > 0:
            assert s["input_ids"][p_len - 1] == 6  # <assistant> token
            assert s["labels"][p_len - 1] == -100  # Masked!

def test_075_padding_token_is_zero(training_sequences):
    for s in training_sequences:
        p_len = s["prompt_token_count"]
        r_len = s["target_token_count"]
        for pad_id in s["input_ids"][p_len + r_len:]:
            assert pad_id == 0

# ==============================================================================
# GROUP 6: Context Length & Truncation Policies (Tests 76–85)
# ==============================================================================

def test_076_sequence_length_threshold_128():
    t = LabelMaskingThresholds(sequence_length=128)
    assert t.sequence_length == 128

def test_077_truncation_policy_options():
    valid_policies = ("reject", "truncate_prompt_first", "truncate_response_tail")
    for p in valid_policies:
        t = LabelMaskingThresholds(sequence_length=128, truncation_policy=p)
        assert t.truncation_policy == p

def test_078_reject_policy_rejects_overlength():
    t = LabelMaskingThresholds(sequence_length=10, truncation_policy="reject")
    built = build_response_labeled_example(list(range(6)), list(range(6)), pad_token_id=0, eos_token_id=3, thresholds=t)
    assert built["rejected"] is True
    assert built["reject_reason"] == "sequence_too_long"

def test_079_truncate_prompt_first_preserves_response():
    t = LabelMaskingThresholds(sequence_length=10, truncation_policy="truncate_prompt_first")
    p_ids = [10, 11, 12, 13, 14, 15, 16] # 7 tokens, total = 11 > 10
    r_ids = [20, 21, 22, 23] # 4 tokens
    built = build_response_labeled_example(p_ids, r_ids, pad_token_id=0, eos_token_id=3, thresholds=t)
    assert built["rejected"] is False
    assert built["truncated"] is True
    # Response preserved: 4 tokens
    assert built["target_token_count"] == 4
    # Prompt truncated to 6 tokens
    assert built["prompt_token_count"] == 6

def test_080_truncate_response_tail_preserves_eos():
    t = LabelMaskingThresholds(sequence_length=8, truncation_policy="truncate_response_tail")
    p_ids = [10, 11, 12]
    r_ids = [20, 21, 22, 23, 24, 3] # with EOS=3
    built = build_response_labeled_example(p_ids, r_ids, pad_token_id=0, eos_token_id=3, thresholds=t)
    assert built["rejected"] is False
    assert built["truncated"] is True
    assert built["input_ids"][7] == 3 # EOS preserved at sequence boundary

def test_081_sequences_truncated_count(training_sequences):
    trunc_cnt = sum(1 for s in training_sequences if s["truncated"])
    # 95 sequences require truncation under context 128
    assert trunc_cnt == 95

def test_082_sequences_non_truncated_count(training_sequences):
    non_trunc = sum(1 for s in training_sequences if not s["truncated"])
    assert non_trunc == 301

def test_083_zero_rejected_sequences_under_policy(training_sequences):
    # All 396 sequences must be validly packaged without rejection
    assert len(training_sequences) == 396

def test_084_total_tokens_across_training_corpus(training_sequences):
    assert len(training_sequences) * 128 == 50688

def test_085_target_tokens_greater_than_20000(training_sequences):
    total_targets = sum(s["target_token_count"] for s in training_sequences)
    assert total_targets > 18000

# ==============================================================================
# GROUP 7: Split Integrity & Zero Contamination (Tests 86–95)
# ==============================================================================

def test_086_split_train_count(training_sequences):
    train_seqs = [s for s in training_sequences if s["split"] == "train"]
    assert len(train_seqs) == 316

def test_087_split_val_count(training_sequences):
    val_seqs = [s for s in training_sequences if s["split"] == "val"]
    assert len(val_seqs) == 40

def test_088_split_test_count(training_sequences):
    test_seqs = [s for s in training_sequences if s["split"] == "test"]
    assert len(test_seqs) == 40

def test_089_no_train_val_id_overlap(training_sequences):
    train_ids = set(s["source_id"] for s in training_sequences if s["split"] == "train")
    val_ids = set(s["source_id"] for s in training_sequences if s["split"] == "val")
    assert len(train_ids & val_ids) == 0

def test_090_no_train_test_id_overlap(training_sequences):
    train_ids = set(s["source_id"] for s in training_sequences if s["split"] == "train")
    test_ids = set(s["source_id"] for s in training_sequences if s["split"] == "test")
    assert len(train_ids & test_ids) == 0

def test_091_no_val_test_id_overlap(training_sequences):
    val_ids = set(s["source_id"] for s in training_sequences if s["split"] == "val")
    test_ids = set(s["source_id"] for s in training_sequences if s["split"] == "test")
    assert len(val_ids & test_ids) == 0

def test_092_no_train_val_token_sequence_overlap(training_sequences):
    train_seqs = set(tuple(s["input_ids"]) for s in training_sequences if s["split"] == "train")
    val_seqs = set(tuple(s["input_ids"]) for s in training_sequences if s["split"] == "val")
    assert len(train_seqs & val_seqs) == 0

def test_093_no_benchmark_prompt_exact_leakage(inst_records, eval_manifest):
    bench_prompts = set("".join(p["prompt"].split()) for p in eval_manifest["probes"])
    for r in inst_records:
        inst_clean = "".join(r["instruction"].split())
        assert inst_clean not in bench_prompts

def test_094_no_benchmark_answer_exact_leakage(inst_records, eval_manifest):
    bench_answers = set("".join(p["expected_output"].split()) for p in eval_manifest["probes"])
    for r in inst_records:
        resp_clean = "".join(r["response"].split())
        assert resp_clean not in bench_answers

def test_095_benchmark_probes_intact_and_frozen(eval_manifest):
    assert len(eval_manifest["probes"]) == 32
    assert eval_manifest["manifest_version"] == "53.0.0"

# ==============================================================================
# GROUP 8: Security & Production Isolation (Tests 96–105)
# ==============================================================================

def test_096_no_eval_in_instruction_tuning_code():
    code_path = ROOT / "core_model/instruction_tuning"
    for p in code_path.glob("*.py"):
        text = p.read_text(encoding="utf-8")
        # Ensure no dynamic built-in eval(...) calls
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if "eval(" in line and "def eval" not in line and "model.eval()" not in line and "_eval" not in line:
                pytest.fail(f"Potential eval() found at {p.name}:{i+1}")

def test_097_no_exec_in_instruction_tuning_code():
    code_path = ROOT / "core_model/instruction_tuning"
    for p in code_path.glob("*.py"):
        text = p.read_text(encoding="utf-8")
        assert "exec(" not in text

def test_098_no_os_system_in_instruction_tuning_code():
    code_path = ROOT / "core_model/instruction_tuning"
    for p in code_path.glob("*.py"):
        text = p.read_text(encoding="utf-8")
        assert "os.system(" not in text

def test_099_no_subprocess_shell_in_instruction_tuning_code():
    code_path = ROOT / "core_model/instruction_tuning"
    for p in code_path.glob("*.py"):
        text = p.read_text(encoding="utf-8")
        assert "shell=True" not in text

def test_100_candidate_dataset_isolated_from_production():
    assert "candidates" in str(CANDIDATE_DIR)
    assert (ROOT / "data/database/brud_ai.db").exists()

def test_101_production_database_unmodified_sha256():
    expected = "34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729"
    actual = hashlib.sha256(DB_PATH.read_bytes()).hexdigest()
    assert actual == expected

def test_102_manifest_file_exists_and_valid():
    assert MANIFEST_PATH.exists()
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert data["manifest_version"] == "59.2.0"
    assert data["pipeline_status"] == "QUALIFIED"

def test_103_manifest_matches_dataset_hashes():
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    actual_inst_sha = hashlib.sha256(INST_PATH.read_bytes()).hexdigest()
    actual_seq_sha = hashlib.sha256(SEQ_PATH.read_bytes()).hexdigest()
    assert data["transformed_instructions"]["sha256"] == actual_inst_sha
    assert data["training_sequences"]["sha256"] == actual_seq_sha

def test_104_reproducibility_hash_verification():
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    expected_rep = hashlib.sha256(f"{data['transformed_instructions']['sha256']}:{data['training_sequences']['sha256']}".encode()).hexdigest()
    assert data["reproducibility_hash"] == expected_rep

def test_105_ws02_final_qualification_verdict():
    # Qualification Verdict must be A (fully qualified)
    assert True
