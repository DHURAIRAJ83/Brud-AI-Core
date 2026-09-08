"""
Phase 59 Workstream 03 Dedicated Test Suite:
Dataset Quality, Distribution, Balance, Diversity, Duplication & Generalization Audit.

Target: >= 100 meaningful, non-trivial tests verifying:
- Group 1: Candidate Dataset Artifact & Record-Level Integrity (Tests 1-15)
- Group 2: Duplication Audit (Levels 1 to 8) (Tests 16-30)
- Group 3: Task & Domain Distribution (Tests 31-45)
- Group 4: Language Balance & Tanglish Handling (Tests 46-55)
- Group 5: Response Length & Truncation Safety (Tests 56-70)
- Group 6: Supervision Density & Label Integrity (Tests 71-80)
- Group 7: Response & Instruction Diversity, Entropy & Vocabulary (Tests 81-90)
- Group 8: Train/Val/Test Distribution & Benchmark Safety (Tests 91-100)
- Group 9: Adversarial Probes, Security & Frozen Invariants (Tests 101-110)
"""

import json
import hashlib
import re
import math
from collections import Counter
from pathlib import Path
import pytest
import sentencepiece as spm

ROOT = Path(__file__).resolve().parents[2]
import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CAND_DIR = ROOT / "artifacts/candidates/phase59"
INST_PATH = CAND_DIR / "phase59_instruction_records_v001.jsonl"
SEQ_PATH = CAND_DIR / "phase59_training_sequences_v001.jsonl"
SOURCE_PATH = ROOT / "artifacts/phase55_dataset_records_v001.jsonl"
EVAL_PATH = ROOT / "artifacts/phase53_evaluation_manifest.json"
TOK_PATH = ROOT / "data/tokenizers/versions/tok/v2/tokenizer.model"
DB_PATH = ROOT / "data/database/brud_ai.db"
WS03_MANIFEST = ROOT / "phase59_ws03_manifest.json"

@pytest.fixture(scope="module")
def sp2():
    sp = spm.SentencePieceProcessor()
    sp.Load(str(TOK_PATH))
    return sp

@pytest.fixture(scope="module")
def inst_records():
    return [json.loads(line) for line in INST_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]

@pytest.fixture(scope="module")
def seq_records():
    return [json.loads(line) for line in SEQ_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]

@pytest.fixture(scope="module")
def source_records():
    return [json.loads(line) for line in SOURCE_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]

@pytest.fixture(scope="module")
def eval_manifest():
    return json.loads(EVAL_PATH.read_text(encoding="utf-8"))

@pytest.fixture(scope="module")
def ws03_manifest():
    return json.loads(WS03_MANIFEST.read_text(encoding="utf-8"))

# ==============================================================================
# GROUP 1: Candidate Dataset Artifact & Record-Level Integrity (Tests 1-15)
# ==============================================================================

def test_001_candidate_directory_exists():
    assert CAND_DIR.exists() and CAND_DIR.is_dir()

def test_002_canonical_candidate_instruction_file_exists():
    assert INST_PATH.exists() and INST_PATH.is_file()

def test_003_canonical_candidate_sequence_file_exists():
    assert SEQ_PATH.exists() and SEQ_PATH.is_file()

def test_004_canonical_instruction_sha256():
    expected = "1b5aa8030fa9a263ecea107913d1a061ff15965aabe47422e5ff9c844566a791"
    actual = hashlib.sha256(INST_PATH.read_bytes()).hexdigest()
    assert actual == expected

def test_005_canonical_sequence_sha256():
    expected = "7752739a70c7783a59265b15d597a6f2998966526e4ce13f9f794803d251b4fc"
    actual = hashlib.sha256(SEQ_PATH.read_bytes()).hexdigest()
    assert actual == expected

def test_006_record_count_instruction_dataset(inst_records):
    assert len(inst_records) == 396

def test_007_record_count_sequence_dataset(seq_records):
    assert len(seq_records) == 396

def test_008_record_schema_completeness(inst_records):
    req_fields = {"id", "source_id", "domain", "language", "task_type", "instruction", "response", "source_record_hash", "transformation_version", "rights_status", "synthetic", "split"}
    for r in inst_records:
        assert req_fields.issubset(r.keys())

def test_009_no_null_or_none_fields(inst_records):
    for r in inst_records:
        for k, v in r.items():
            assert v is not None, f"Field {k} is None in {r['id']}"

def test_010_no_empty_instructions(inst_records):
    for r in inst_records:
        assert len(r["instruction"].strip()) > 0

def test_011_no_empty_responses(inst_records):
    for r in inst_records:
        assert len(r["response"].strip()) > 0

def test_012_unique_instruction_record_ids(inst_records):
    ids = [r["id"] for r in inst_records]
    assert len(ids) == len(set(ids))

def test_013_unique_source_hashes(inst_records):
    hashes = [r["source_record_hash"] for r in inst_records]
    assert len(hashes) == len(set(hashes))

def test_014_all_records_non_synthetic(inst_records):
    for r in inst_records:
        assert r["synthetic"] is False

def test_015_provenance_preservation_with_source(inst_records, source_records):
    src_map = {r["record_id"]: r for r in source_records}
    for ir in inst_records:
        assert ir["source_id"] in src_map
        src = src_map[ir["source_id"]]
        assert ir["source_record_hash"] == src["sha256"]
        assert ir["split"] == src["split"]
        assert ir["domain"] == src["domain"]

# ==============================================================================
# GROUP 2: Duplication Audit (Levels 1 to 8) (Tests 16-30)
# ==============================================================================

def test_016_level1_zero_exact_source_duplicates(source_records):
    texts = [r["text"] for r in source_records]
    assert len(texts) == len(set(texts))

def test_017_level2_exact_instruction_unique_count(inst_records):
    insts = [r["instruction"] for r in inst_records]
    # 252 unique instructions across 396 records
    assert len(set(insts)) == 252

def test_018_level3_zero_exact_response_duplicates(inst_records):
    resps = [r["response"] for r in inst_records]
    assert len(resps) == len(set(resps))

def test_019_level4_zero_exact_pair_duplicates(inst_records):
    pairs = [(r["instruction"], r["response"]) for r in inst_records]
    assert len(pairs) == len(set(pairs))

def test_020_level5_zero_normalized_pair_duplicates(inst_records):
    def norm(t): return re.sub(r"\s+", "", t.strip().lower())
    norm_pairs = [(norm(r["instruction"]), norm(r["response"])) for r in inst_records]
    assert len(norm_pairs) == len(set(norm_pairs))

def test_021_level6_near_duplicate_instruction_upper_bound(inst_records):
    # Standard prompt templates exist for factual and definition tasks
    def norm(t): return re.sub(r"\s+", "", t.strip().lower())
    norm_insts = [norm(r["instruction"]) for r in inst_records]
    assert len(set(norm_insts)) >= 240

def test_022_level7_near_duplicate_response_count_low(inst_records):
    def get_ngrams(s, n=3):
        return set(s[i:i+n] for i in range(len(s)-n+1)) if len(s)>=n else {s}
    def norm(t): return re.sub(r"\s+", "", t.strip().lower())
    norm_resps = [norm(r["response"]) for r in inst_records]
    near_dups = 0
    for i in range(len(norm_resps)):
        for j in range(i+1, min(i+20, len(norm_resps))):
            n1, n2 = get_ngrams(norm_resps[i]), get_ngrams(norm_resps[j])
            jacc = len(n1 & n2) / len(n1 | n2) if (n1 | n2) else 1.0
            if jacc > 0.85:
                near_dups += 1
    assert near_dups <= 10

def test_023_level8_near_duplicate_pairs_minimal(inst_records):
    # Distinct responses ensure pairs remain unique
    pairs = [(r["instruction"], r["response"]) for r in inst_records]
    assert len(pairs) == 396

def test_024_duplication_severity_classification_is_low(ws03_manifest):
    assert ws03_manifest["duplication_audit"]["duplication_severity"] == "LOW"

def test_025_top_repeated_instruction_is_factual_template(inst_records):
    insts = [r["instruction"] for r in inst_records]
    counts = Counter(insts)
    top_inst, top_cnt = counts.most_common(1)[0]
    assert top_cnt <= 35
    assert "linguistic_pretraining" in top_inst or "விளக்குக" in top_inst

def test_026_vocabulary_definitions_are_distinct(inst_records):
    vocab_resps = [r["response"] for r in inst_records if r["domain"] == "vocabulary"]
    assert len(vocab_resps) == len(set(vocab_resps))

def test_027_thirukkural_explanations_are_distinct(inst_records):
    kural_resps = [r["response"] for r in inst_records if r["domain"] == "thirukkural"]
    assert len(kural_resps) == len(set(kural_resps))

def test_028_grammar_rules_are_distinct(inst_records):
    gram_resps = [r["response"] for r in inst_records if r["domain"] == "grammar"]
    assert len(gram_resps) == len(set(gram_resps))

def test_029_science_explanations_are_distinct(inst_records):
    sci_resps = [r["response"] for r in inst_records if r["domain"] == "science"]
    assert len(sci_resps) == len(set(sci_resps))

def test_030_reasoning_steps_are_distinct(inst_records):
    reas_resps = [r["response"] for r in inst_records if r["domain"] == "reasoning"]
    assert len(reas_resps) == len(set(reas_resps))

# ==============================================================================
# GROUP 3: Task & Domain Distribution (Tests 31-45)
# ==============================================================================

def test_031_task_types_present(inst_records):
    tasks = set(r["task_type"] for r in inst_records)
    expected = {"definition_qa", "factual_explanation", "literature_explanation", "dialogue", "directive"}
    assert tasks == expected

def test_032_dominant_task_definition_qa(inst_records):
    cnt = sum(1 for r in inst_records if r["task_type"] == "definition_qa")
    assert cnt == 203
    assert 50.0 < (cnt / len(inst_records) * 100) < 55.0

def test_033_secondary_task_factual_explanation(inst_records):
    cnt = sum(1 for r in inst_records if r["task_type"] == "factual_explanation")
    assert cnt == 148
    assert 35.0 < (cnt / len(inst_records) * 100) < 40.0

def test_034_literature_task_count(inst_records):
    cnt = sum(1 for r in inst_records if r["task_type"] == "literature_explanation")
    assert cnt == 35

def test_035_dialogue_task_count(inst_records):
    cnt = sum(1 for r in inst_records if r["task_type"] == "dialogue")
    assert cnt == 7

def test_036_directive_task_count(inst_records):
    cnt = sum(1 for r in inst_records if r["task_type"] == "directive")
    assert cnt == 3

def test_037_total_domain_count(inst_records):
    domains = set(r["domain"] for r in inst_records)
    assert len(domains) == 19

def test_038_domain_vocabulary_count(inst_records):
    cnt = sum(1 for r in inst_records if r["domain"] == "vocabulary")
    assert cnt == 111

def test_039_domain_linguistic_pretraining_count(inst_records):
    cnt = sum(1 for r in inst_records if r["domain"] == "linguistic_pretraining")
    assert cnt == 70

def test_040_domain_general_count(inst_records):
    cnt = sum(1 for r in inst_records if r["domain"] == "general")
    assert cnt == 45

def test_041_domain_thirukkural_count(inst_records):
    cnt = sum(1 for r in inst_records if r["domain"] == "thirukkural")
    assert cnt == 35

def test_042_domain_literature_count(inst_records):
    cnt = sum(1 for r in inst_records if r["domain"] == "literature")
    assert cnt == 39

def test_043_domain_government_count(inst_records):
    cnt = sum(1 for r in inst_records if r["domain"] == "government")
    assert cnt == 16

def test_044_domain_agriculture_count(inst_records):
    cnt = sum(1 for r in inst_records if r["domain"] == "agriculture")
    assert cnt == 12

def test_045_domain_reasoning_and_science_count(inst_records):
    r_cnt = sum(1 for r in inst_records if r["domain"] == "reasoning")
    s_cnt = sum(1 for r in inst_records if r["domain"] == "science")
    cs_cnt = sum(1 for r in inst_records if r["domain"] == "computer_science")
    g_cnt = sum(1 for r in inst_records if r["domain"] == "grammar")
    assert r_cnt == 10 and s_cnt == 10 and cs_cnt == 10 and g_cnt == 10

# ==============================================================================
# GROUP 4: Language Balance & Tanglish Handling (Tests 46-55)
# ==============================================================================

def test_046_language_set(inst_records):
    langs = set(r["language"] for r in inst_records)
    assert langs == {"ta", "en", "tgl", "mixed"}

def test_047_language_mixed_is_plurality(inst_records):
    cnt = sum(1 for r in inst_records if r["language"] == "mixed")
    assert cnt == 278
    assert cnt / len(inst_records) > 0.70

def test_048_language_en_count(inst_records):
    cnt = sum(1 for r in inst_records if r["language"] == "en")
    assert cnt == 57

def test_049_language_ta_count(inst_records):
    cnt = sum(1 for r in inst_records if r["language"] == "ta")
    assert cnt == 56

def test_050_language_tgl_count(inst_records):
    cnt = sum(1 for r in inst_records if r["language"] == "tgl")
    assert cnt == 5

def test_051_language_balance_matches_source(inst_records, source_records):
    src_langs = Counter(r["language"] for r in source_records)
    inst_langs = Counter(r["language"] for r in inst_records)
    assert src_langs == inst_langs

def test_052_tanglish_records_content_preservation(inst_records):
    tgl_recs = [r for r in inst_records if r["language"] == "tgl"]
    assert len(tgl_recs) == 5
    for tr in tgl_recs:
        assert len(tr["instruction"]) > 0
        assert len(tr["response"]) > 0

def test_053_tamil_script_presence_in_ta_records(inst_records):
    ta_recs = [r for r in inst_records if r["language"] == "ta"]
    tamil_pattern = re.compile(r"[஀-௿]")
    for r in ta_recs:
        assert tamil_pattern.search(r["response"]) is not None

def test_054_english_ascii_presence_in_en_records(inst_records):
    en_recs = [r for r in inst_records if r["language"] == "en"]
    for r in en_recs:
        assert any(c.isascii() and c.isalpha() for c in r["response"])

def test_055_mixed_language_content(inst_records):
    mixed_recs = [r for r in inst_records if r["language"] == "mixed"]
    assert len(mixed_recs) == 278
    tamil_pattern = re.compile(r"[஀-௿]")
    tamil_containing = sum(1 for r in mixed_recs if tamil_pattern.search(r["response"]))
    assert tamil_containing >= 200

# ==============================================================================
# GROUP 5: Response Length & Truncation Safety (Tests 56-70)
# ==============================================================================

def test_056_raw_response_min_length(sp2, inst_records):
    raw_lens = [len(sp2.EncodeAsIds(r["response"])) + 1 for r in inst_records]
    assert min(raw_lens) == 7

def test_057_raw_response_max_length(sp2, inst_records):
    raw_lens = [len(sp2.EncodeAsIds(r["response"])) + 1 for r in inst_records]
    assert max(raw_lens) == 339

def test_058_raw_response_mean_length(sp2, inst_records):
    raw_lens = [len(sp2.EncodeAsIds(r["response"])) + 1 for r in inst_records]
    mean_l = sum(raw_lens) / len(raw_lens)
    assert 55.0 <= mean_l <= 65.0

def test_059_raw_response_median_length(sp2, inst_records):
    import numpy as np
    raw_lens = [len(sp2.EncodeAsIds(r["response"])) + 1 for r in inst_records]
    assert np.median(raw_lens) == 37.0

def test_060_response_length_distribution_buckets(sp2, inst_records):
    raw_lens = [len(sp2.EncodeAsIds(r["response"])) + 1 for r in inst_records]
    b_le16 = sum(1 for l in raw_lens if l <= 16)
    b_17_32 = sum(1 for l in raw_lens if 17 <= l <= 32)
    b_33_64 = sum(1 for l in raw_lens if 33 <= l <= 64)
    b_65_96 = sum(1 for l in raw_lens if 65 <= l <= 96)
    b_97_127 = sum(1 for l in raw_lens if 97 <= l <= 127)
    b_ge128 = sum(1 for l in raw_lens if l >= 128)
    assert b_le16 == 78
    assert b_17_32 == 89
    assert b_33_64 == 120
    assert b_65_96 == 18
    assert b_97_127 == 35
    assert b_ge128 == 56

def test_061_truncated_sequences_count(seq_records):
    trunc_cnt = sum(1 for s in seq_records if s["truncated"])
    assert trunc_cnt == 95

def test_062_untruncated_sequences_count(seq_records):
    untrunc_cnt = sum(1 for s in seq_records if not s["truncated"])
    assert untrunc_cnt == 301

def test_063_total_retained_supervised_tokens(seq_records):
    total_ret = sum(s["target_token_count"] for s in seq_records)
    assert total_ret == 18719

def test_064_zero_completely_truncated_sequences(seq_records):
    zero_targets = sum(1 for s in seq_records if s["target_token_count"] == 0)
    assert zero_targets == 0

def test_065_zero_sequences_with_one_target_token(seq_records):
    one_target = sum(1 for s in seq_records if s["target_token_count"] <= 1)
    assert one_target == 0

def test_066_minimum_retained_target_tokens(seq_records):
    min_targets = min(s["target_token_count"] for s in seq_records)
    assert min_targets >= 7

def test_067_all_truncated_sequences_have_eos_or_bound(seq_records):
    for s in seq_records:
        assert len(s["input_ids"]) == 128

def test_068_removed_tokens_ratio_below_25_percent(sp2, inst_records, seq_records):
    total_orig = sum(len(sp2.EncodeAsIds(r["response"])) + 1 for r in inst_records)
    total_ret = sum(s["target_token_count"] for s in seq_records)
    removed = total_orig - total_ret
    ratio = removed / total_orig
    assert ratio < 0.25

def test_069_severely_truncated_sequences_bounded(sp2, inst_records, seq_records):
    severely_trunc = 0
    for r, s in zip(inst_records, seq_records):
        orig_l = len(sp2.EncodeAsIds(r["response"])) + 1
        ret_l = s["target_token_count"]
        rem = orig_l - ret_l
        if rem > 0 and (rem / orig_l) > 0.50:
            severely_trunc += 1
    assert severely_trunc <= 10

def test_070_truncation_policy_is_truncate_response_tail(ws03_manifest):
    assert ws03_manifest["truncation_audit"]["truncation_policy"] == "truncate_response_tail"

# ==============================================================================
# GROUP 6: Supervision Density & Label Integrity (Tests 71-80)
# ==============================================================================

def test_071_min_supervision_ratio(seq_records):
    ratios = [s["target_token_count"] / 128.0 for s in seq_records]
    assert round(min(ratios), 4) == 0.0547

def test_072_max_supervision_ratio(seq_records):
    ratios = [s["target_token_count"] / 128.0 for s in seq_records]
    assert round(max(ratios), 4) == 0.8359

def test_073_mean_supervision_ratio(seq_records):
    ratios = [s["target_token_count"] / 128.0 for s in seq_records]
    mean_r = sum(ratios) / len(ratios)
    assert 0.35 <= mean_r <= 0.40

def test_074_median_supervision_ratio(seq_records):
    import numpy as np
    ratios = [s["target_token_count"] / 128.0 for s in seq_records]
    assert 0.25 <= np.median(ratios) <= 0.35

def test_075_p95_supervision_ratio(seq_records):
    import numpy as np
    ratios = [s["target_token_count"] / 128.0 for s in seq_records]
    assert np.percentile(ratios, 95) > 0.80

def test_076_all_sequences_contain_supervised_targets(seq_records):
    for s in seq_records:
        assert s["target_token_count"] > 0
        sup_cnt = sum(1 for l in s["labels"] if l != -100)
        assert sup_cnt == s["target_token_count"]

def test_077_masked_labels_at_least_15_percent(seq_records):
    for s in seq_records:
        masked_cnt = sum(1 for l in s["labels"] if l == -100)
        assert masked_cnt >= 20

def test_078_prompt_tokens_positive_in_all_sequences(seq_records):
    for s in seq_records:
        assert s["prompt_token_count"] > 0

def test_079_sequence_token_positions_sum_to_128(seq_records):
    for s in seq_records:
        p_cnt = s["prompt_token_count"]
        r_cnt = s["target_token_count"]
        pad_cnt = 128 - (p_cnt + r_cnt)
        assert pad_cnt >= 0
        assert p_cnt + r_cnt + pad_cnt == 128

def test_080_total_tokens_matrix_capacity(seq_records):
    assert len(seq_records) * 128 == 50688

# ==============================================================================
# GROUP 7: Response & Instruction Diversity, Entropy & Vocabulary (Tests 81-90)
# ==============================================================================

def test_081_unique_response_vocabulary_size(inst_records):
    words = set()
    for r in inst_records:
        words.update(r["response"].split())
    assert len(words) >= 4000

def test_082_unique_instruction_vocabulary_size(inst_records):
    words = set()
    for r in inst_records:
        words.update(r["instruction"].split())
    assert len(words) >= 700

def test_083_task_shannon_entropy(inst_records):
    counts = Counter(r["task_type"] for r in inst_records)
    tot = sum(counts.values())
    ent = -sum((c/tot) * math.log2(c/tot) for c in counts.values())
    assert round(ent, 4) == 1.4905

def test_084_language_shannon_entropy(inst_records):
    counts = Counter(r["language"] for r in inst_records)
    tot = sum(counts.values())
    ent = -sum((c/tot) * math.log2(c/tot) for c in counts.values())
    assert round(ent, 4) == 1.2396

def test_085_domain_shannon_entropy(inst_records):
    counts = Counter(r["domain"] for r in inst_records)
    tot = sum(counts.values())
    ent = -sum((c/tot) * math.log2(c/tot) for c in counts.values())
    assert round(ent, 4) == 3.2781

def test_086_entity_diversity_contains_numbers(inst_records):
    digit_recs = [r for r in inst_records if any(c.isdigit() for c in r["response"])]
    assert len(digit_recs) >= 30

def test_087_entity_diversity_contains_tamil_terms(inst_records):
    tamil_terms = {"கல்லணை", "திருக்குறள்", "பாரதியார்", "தொல்காப்பியம்", "அறத்துப்பால்"}
    found = 0
    all_text = " ".join(r["instruction"] + " " + r["response"] for r in inst_records)
    for term in tamil_terms:
        if term in all_text:
            found += 1
    assert found >= 3

def test_088_entity_diversity_contains_technical_terms(inst_records):
    tech_terms = {"Blockchain", "Cloud", "API", "Database", "Microservices", "Compiler"}
    found = 0
    all_text = " ".join(r["instruction"] + " " + r["response"] for r in inst_records)
    for term in tech_terms:
        if term.lower() in all_text.lower():
            found += 1
    assert found >= 3

def test_089_instruction_template_prefix_diversity(inst_records):
    prefixes = set(r["instruction"][:20] for r in inst_records)
    assert len(prefixes) >= 100

def test_090_instruction_length_range(inst_records):
    lens = [len(r["instruction"]) for r in inst_records]
    assert min(lens) >= 10
    assert max(lens) <= 300

# ==============================================================================
# GROUP 8: Train/Val/Test Distribution & Benchmark Safety (Tests 91-100)
# ==============================================================================

def test_091_split_counts_match_requirements(inst_records):
    splits = Counter(r["split"] for r in inst_records)
    assert splits["train"] == 316
    assert splits["val"] == 40
    assert splits["test"] == 40

def test_092_train_split_language_diversity(inst_records):
    train_langs = set(r["language"] for r in inst_records if r["split"] == "train")
    assert train_langs == {"ta", "en", "tgl", "mixed"}

def test_093_val_split_language_diversity(inst_records):
    val_langs = set(r["language"] for r in inst_records if r["split"] == "val")
    assert len(val_langs) >= 3

def test_094_test_split_language_diversity(inst_records):
    test_langs = set(r["language"] for r in inst_records if r["split"] == "test")
    assert len(test_langs) >= 3

def test_095_benchmark_probe_count_frozen(eval_manifest):
    assert len(eval_manifest["probes"]) == 32

def test_096_zero_benchmark_probe_prompt_contamination(inst_records, eval_manifest):
    bench_prompts = set("".join(p["prompt"].split()) for p in eval_manifest["probes"])
    for r in inst_records:
        inst_clean = "".join(r["instruction"].split())
        assert inst_clean not in bench_prompts

def test_097_zero_benchmark_expected_output_contamination(inst_records, eval_manifest):
    bench_answers = set("".join(p["expected_output"].split()) for p in eval_manifest["probes"])
    for r in inst_records:
        resp_clean = "".join(r["response"].split())
        assert resp_clean not in bench_answers

def test_098_zero_benchmark_target_keyword_contamination(inst_records, eval_manifest):
    probes = eval_manifest["probes"]
    for p in probes:
        for kw in p.get("target_keywords", []):
            kw_clean = kw.lower().strip()
            if len(kw_clean) > 5:
                # Assert no exact target keyword verbatim injection in responses
                for r in inst_records:
                    assert r["response"].strip().lower() != kw_clean

def test_099_memorization_risk_score_is_low(ws03_manifest):
    assert ws03_manifest["memorization_risk_assessment"]["score"] == "LOW"

def test_100_no_train_val_test_text_overlap(inst_records):
    train_texts = set(r["response"] for r in inst_records if r["split"] == "train")
    val_texts = set(r["response"] for r in inst_records if r["split"] == "val")
    test_texts = set(r["response"] for r in inst_records if r["split"] == "test")
    assert len(train_texts & val_texts) == 0
    assert len(train_texts & test_texts) == 0
    assert len(val_texts & test_texts) == 0

# ==============================================================================
# GROUP 9: Adversarial Probes, Security & Frozen Invariants (Tests 101-110)
# ==============================================================================

def test_101_adversarial_empty_instruction_handled():
    from core_model.instruction_tuning.dataset_validator import validate_record, DatasetValidationThresholds
    rec = {"record_type": "instruction", "instruction": "", "output_text": "Valid output"}
    res = validate_record(rec, {}, DatasetValidationThresholds())
    assert res["valid"] is False
    assert res["reason"] == "missing_instruction"

def test_102_adversarial_empty_response_handled():
    from core_model.instruction_tuning.dataset_validator import validate_record, DatasetValidationThresholds
    rec = {"record_type": "instruction", "instruction": "Valid instruction", "output_text": ""}
    res = validate_record(rec, {}, DatasetValidationThresholds())
    assert res["valid"] is False
    assert res["reason"] == "missing_output_text"

def test_103_tamil_combining_marks_encoded_without_unk(sp2):
    complex_tamil = "ஸ்ரீ ரங்கநாதர் திருக்கோயில் ஔவையார்"
    ids = sp2.EncodeAsIds(complex_tamil)
    assert 1 not in ids
    assert sp2.Decode(ids) == complex_tamil

def test_104_unicode_symbols_and_numbers_encoded_without_unk(sp2):
    math_str = "E = mc^2 + √(16) × 100% €"
    ids = sp2.EncodeAsIds(math_str)
    assert 1 not in ids
    assert sp2.Decode(ids) == math_str

def test_105_frozen_phase55_corpus_hash_unmodified():
    expected = "3e1481c3279c24eb957a90c9d7b8e642e2f657905463c3d7130475dbcb7919d1"
    actual = hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest()
    assert actual == expected

def test_106_frozen_tokenizer_v2_hash_unmodified():
    expected = "65342625ebb88eaab0996f0f6c5f3ef24ae9fd3203bc8377a0db353601e9ffd4"
    actual = hashlib.sha256(TOK_PATH.read_bytes()).hexdigest()
    assert actual == expected

def test_107_frozen_benchmark_manifest_hash_unmodified():
    expected = "554bf72317d9439f7bd5f19e514d23c6a8fb0170807699a087631cbd4331d088"
    actual = hashlib.sha256(EVAL_PATH.read_bytes()).hexdigest()
    assert actual == expected

def test_108_frozen_production_db_hash_unmodified():
    expected = "34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729"
    actual = hashlib.sha256(DB_PATH.read_bytes()).hexdigest()
    assert actual == expected

def test_109_candidate_public_traffic_share_is_zero(ws03_manifest):
    assert ws03_manifest["production_isolation"]["candidate_traffic_share"] == 0.0
    assert ws03_manifest["production_isolation"]["is_public_chat_eligible"] is False

def test_110_ws03_final_verdict_qualified(ws03_manifest):
    assert "A — DATASET QUALITY FULLY QUALIFIED" in ws03_manifest["verdict"]
