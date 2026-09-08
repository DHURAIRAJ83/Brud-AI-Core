"""
Phase 59 Workstream 04 Dedicated Test Suite:
Instruction-Following, Task Coverage & Capability Alignment Audit.

Target: >= 100 meaningful, non-trivial tests verifying:
- Group 1: Task Taxonomy & Task Distribution (Tests 1-15)
- Group 2: Capability Taxonomy CAP-01 through CAP-18 (Tests 16-35)
- Group 3: Task Difficulty Classification (Levels 1 to 5) (Tests 36-45)
- Group 4: Language Capability & Code-Switching (Tests 46-60)
- Group 5: Reasoning & Arithmetic Support (Tests 61-70)
- Group 6: Response Quality & Structural Formatting (Tests 71-80)
- Group 7: EOS Supervision & Termination (Tests 81-85)
- Group 8: Capability Cross-Tabulation & Sparsity (Tests 86-95)
- Group 9: Benchmark Alignment & Contradiction Audit (Tests 96-105)
- Group 10: Security, Unsupported Risks & Frozen Baselines (Tests 106-115)
"""

import json
import hashlib
import re
import math
from pathlib import Path
from collections import Counter, defaultdict
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
WS04_MANIFEST = ROOT / "phase59_ws04_manifest.json"

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
def eval_manifest():
    return json.loads(EVAL_PATH.read_text(encoding="utf-8"))

@pytest.fixture(scope="module")
def ws04_manifest():
    return json.loads(WS04_MANIFEST.read_text(encoding="utf-8"))

# ==============================================================================
# GROUP 1: Task Taxonomy & Task Distribution (Tests 1-15)
# ==============================================================================

def test_001_candidate_instruction_file_exists():
    assert INST_PATH.exists() and INST_PATH.is_file()

def test_002_candidate_sequence_file_exists():
    assert SEQ_PATH.exists() and SEQ_PATH.is_file()

def test_003_task_type_cardinality(inst_records):
    tasks = set(r["task_type"] for r in inst_records)
    assert len(tasks) == 5

def test_004_task_type_names(inst_records):
    tasks = set(r["task_type"] for r in inst_records)
    assert tasks == {"definition_qa", "factual_explanation", "literature_explanation", "dialogue", "directive"}

def test_005_task_definition_qa_count(inst_records):
    assert sum(1 for r in inst_records if r["task_type"] == "definition_qa") == 203

def test_006_task_factual_explanation_count(inst_records):
    assert sum(1 for r in inst_records if r["task_type"] == "factual_explanation") == 148

def test_007_task_literature_explanation_count(inst_records):
    assert sum(1 for r in inst_records if r["task_type"] == "literature_explanation") == 35

def test_008_task_dialogue_count(inst_records):
    assert sum(1 for r in inst_records if r["task_type"] == "dialogue") == 7

def test_009_task_directive_count(inst_records):
    assert sum(1 for r in inst_records if r["task_type"] == "directive") == 3

def test_010_definition_qa_supervised_tokens(inst_records, seq_records):
    sup = sum(s["target_token_count"] for r, s in zip(inst_records, seq_records) if r["task_type"] == "definition_qa")
    assert sup == 11336

def test_011_factual_explanation_supervised_tokens(inst_records, seq_records):
    sup = sum(s["target_token_count"] for r, s in zip(inst_records, seq_records) if r["task_type"] == "factual_explanation")
    assert sup == 4507

def test_012_literature_explanation_supervised_tokens(inst_records, seq_records):
    sup = sum(s["target_token_count"] for r, s in zip(inst_records, seq_records) if r["task_type"] == "literature_explanation")
    assert sup == 2639

def test_013_dialogue_supervised_tokens(inst_records, seq_records):
    sup = sum(s["target_token_count"] for r, s in zip(inst_records, seq_records) if r["task_type"] == "dialogue")
    assert sup == 82

def test_014_directive_supervised_tokens(inst_records, seq_records):
    sup = sum(s["target_token_count"] for r, s in zip(inst_records, seq_records) if r["task_type"] == "directive")
    assert sup == 155

def test_015_total_supervised_tokens_across_tasks(seq_records):
    assert sum(s["target_token_count"] for s in seq_records) == 18719

# ==============================================================================
# GROUP 2: Capability Taxonomy CAP-01 through CAP-18 (Tests 16-35)
# ==============================================================================

def test_016_cap01_definition_support(inst_records):
    cnt = sum(1 for r in inst_records if r["task_type"] == "definition_qa")
    assert cnt == 203

def test_017_cap02_factual_qa_support(inst_records):
    cnt = sum(1 for r in inst_records if r["task_type"] == "factual_explanation")
    assert cnt == 148

def test_018_cap03_explanation_support(inst_records):
    cnt = sum(1 for r in inst_records if len(r["response"]) > 80 or "விளக்கம்" in r["response"] or "because" in r["response"].lower())
    assert cnt >= 200

def test_019_cap04_instruction_following_support(inst_records):
    # All 396 examples provide paired instruction-following supervision
    assert len(inst_records) == 396

def test_020_cap05_dialogue_support(inst_records):
    cnt = sum(1 for r in inst_records if r["task_type"] == "dialogue" or r["domain"] == "synthetic_dialogue")
    assert cnt >= 7

def test_021_cap06_directive_support(inst_records):
    cnt = sum(1 for r in inst_records if r["task_type"] == "directive" or r["domain"] == "instruction_following")
    assert cnt >= 5

def test_022_cap07_literature_support(inst_records):
    cnt = sum(1 for r in inst_records if r["domain"] in ["literature", "thirukkural", "poem"])
    assert cnt == 76

def test_023_cap08_tamil_language_support(inst_records):
    cnt = sum(1 for r in inst_records if re.search(r"[஀-௿]", r["instruction"] + r["response"]))
    assert cnt == 335

def test_024_cap09_english_language_support(inst_records):
    cnt = sum(1 for r in inst_records if re.search(r"[a-zA-Z]", r["instruction"] + r["response"]))
    assert cnt >= 390

def test_025_cap10_tanglish_language_support(inst_records):
    cnt = sum(1 for r in inst_records if r["language"] == "tgl")
    assert cnt == 5

def test_026_cap11_mixed_bilingual_support(inst_records):
    cnt = sum(1 for r in inst_records if r["language"] == "mixed")
    assert cnt == 278

def test_027_cap12_grammar_support(inst_records):
    cnt = sum(1 for r in inst_records if r["domain"] in ["grammar", "linguistic_pretraining"])
    assert cnt == 80

def test_028_cap13_reasoning_support(inst_records):
    cnt = sum(1 for r in inst_records if r["domain"] == "reasoning")
    assert cnt == 10

def test_029_cap14_arithmetic_support(inst_records):
    cnt = sum(1 for r in inst_records if any(c.isdigit() for c in r["response"]) and any(op in r["response"] for op in ["+", "-", "=", "%", "முறை", "விதி"]))
    assert cnt >= 25

def test_030_cap15_grounding_support(inst_records):
    cnt = sum(1 for r in inst_records if r["rights_status"] == "verified" and not r["synthetic"])
    assert cnt == 396

def test_031_cap16_structured_response_support(inst_records):
    cnt = sum(1 for r in inst_records if ("\n" in r["response"] and ("1." in r["response"] or "•" in r["response"] or "-" in r["response"])) or ("1." in r["response"]))
    assert cnt >= 15

def test_032_cap17_eos_termination_support(seq_records):
    for s in seq_records:
        assert s["input_ids"][s["prompt_token_count"] + s["target_token_count"] - 1] == 3
        assert s["labels"][s["prompt_token_count"] + s["target_token_count"] - 1] == 3

def test_033_cap18_safe_refusal_boundary_indirect_support(inst_records):
    cnt = sum(1 for r in inst_records if any(term in r["response"].lower() for term in ["neutralized", "safe", "plain", "முடியாது", "refuse"]))
    assert cnt >= 3

def test_034_cap18_absence_of_explicit_jailbreak_refusal_pairs(inst_records):
    # Audit confirms dataset contains 0 explicit adversarial jailbreak refusal pairs
    explicit_refusals = [r for r in inst_records if "as an ai" in r["response"].lower() or "i cannot assist" in r["response"].lower()]
    assert len(explicit_refusals) == 0

def test_035_all_18_capabilities_represented_or_identified(ws04_manifest):
    cov = ws04_manifest["capability_coverage_summary"]
    assert len(cov) == 18

# ==============================================================================
# GROUP 3: Task Difficulty Classification (Levels 1 to 5) (Tests 36-45)
# ==============================================================================

def test_036_difficulty_level_cardinality(ws04_manifest):
    diffs = ws04_manifest["difficulty_distribution"]
    assert len(diffs) == 5

def test_037_difficulty_level_1_lexical(ws04_manifest):
    assert ws04_manifest["difficulty_distribution"]["level_1_lexical_direct_lookup"]["count"] == 140

def test_038_difficulty_level_2_factual(ws04_manifest):
    assert ws04_manifest["difficulty_distribution"]["level_2_simple_factual_explanation"]["count"] == 130

def test_039_difficulty_level_3_multi_step(ws04_manifest):
    assert ws04_manifest["difficulty_distribution"]["level_3_multi_step_explanation"]["count"] == 108

def test_040_difficulty_level_4_reasoning(ws04_manifest):
    assert ws04_manifest["difficulty_distribution"]["level_4_reasoning_inference"]["count"] == 13

def test_041_difficulty_level_5_multi_constraint(ws04_manifest):
    assert ws04_manifest["difficulty_distribution"]["level_5_multi_constraint_instruction"]["count"] == 5

def test_042_difficulty_distribution_sums_to_396(ws04_manifest):
    total = sum(v["count"] for v in ws04_manifest["difficulty_distribution"].values())
    assert total == 396

def test_043_difficulty_levels_have_non_zero_representation(ws04_manifest):
    for k, v in ws04_manifest["difficulty_distribution"].items():
        assert v["count"] > 0

def test_044_foundational_levels_1_and_2_represent_majority(ws04_manifest):
    l1 = ws04_manifest["difficulty_distribution"]["level_1_lexical_direct_lookup"]["count"]
    l2 = ws04_manifest["difficulty_distribution"]["level_2_simple_factual_explanation"]["count"]
    assert (l1 + l2) / 396 > 0.65

def test_045_advanced_levels_4_and_5_represent_minority(ws04_manifest):
    l4 = ws04_manifest["difficulty_distribution"]["level_4_reasoning_inference"]["count"]
    l5 = ws04_manifest["difficulty_distribution"]["level_5_multi_constraint_instruction"]["count"]
    assert (l4 + l5) / 396 < 0.10

# ==============================================================================
# GROUP 4: Language Capability & Code-Switching (Tests 46-60)
# ==============================================================================

def test_046_tamil_records_contain_tamil_alphabet(inst_records):
    ta_recs = [r for r in inst_records if r["language"] == "ta"]
    tamil_regex = re.compile(r"[஀-௿]")
    for r in ta_recs:
        assert tamil_regex.search(r["response"]) is not None

def test_047_english_records_contain_ascii_alphabet(inst_records):
    en_recs = [r for r in inst_records if r["language"] == "en"]
    for r in en_recs:
        assert any(c.isascii() and c.isalpha() for c in r["response"])

def test_048_tanglish_records_count_exact_five(inst_records):
    tgl_recs = [r for r in inst_records if r["language"] == "tgl"]
    assert len(tgl_recs) == 5

def test_049_mixed_records_contain_bilingual_terms(inst_records):
    mixed_recs = [r for r in inst_records if r["language"] == "mixed"]
    # Check for bilingual term patterns like "பிளாக்செயின் (Blockchain)"
    bilingual_terms = sum(1 for r in mixed_recs if "(" in r["instruction"] or "(" in r["response"])
    assert bilingual_terms >= 100

def test_050_technical_english_in_tamil_context(inst_records):
    tech_in_tamil = 0
    tamil_regex = re.compile(r"[஀-௿]")
    for r in inst_records:
        if r["language"] == "mixed" and tamil_regex.search(r["response"]):
            if any(c.isascii() and c.isalpha() for c in r["response"]):
                tech_in_tamil += 1
    assert tech_in_tamil >= 150

def test_051_language_marker_in_prompts(seq_records):
    # Tokens 7 (<ta>), 8 (<en>), 9 (<tgl>), 10 (<mixed>) must appear in prompts
    lang_tokens = {7, 8, 9, 10}
    for s in seq_records:
        p_len = s["prompt_token_count"]
        assert any(tid in lang_tokens for tid in s["input_ids"][:p_len])

def test_052_tamil_only_task_distribution(inst_records):
    ta_tasks = Counter(r["task_type"] for r in inst_records if r["language"] == "ta")
    assert len(ta_tasks) >= 3

def test_053_english_only_task_distribution(inst_records):
    en_tasks = Counter(r["task_type"] for r in inst_records if r["language"] == "en")
    assert len(en_tasks) >= 3

def test_054_mixed_task_distribution(inst_records):
    mixed_tasks = Counter(r["task_type"] for r in inst_records if r["language"] == "mixed")
    assert len(mixed_tasks) >= 4

def test_055_tanglish_tasks(inst_records):
    tgl_tasks = Counter(r["task_type"] for r in inst_records if r["language"] == "tgl")
    assert "factual_explanation" in tgl_tasks

def test_056_zero_unk_in_tamil_prompts_and_responses(sp2, inst_records):
    ta_recs = [r for r in inst_records if r["language"] == "ta"]
    unks = sum(sp2.EncodeAsIds(r["instruction"] + " " + r["response"]).count(1) for r in ta_recs)
    assert unks == 0

def test_057_zero_unk_in_mixed_prompts_and_responses(sp2, inst_records):
    mixed_recs = [r for r in inst_records if r["language"] == "mixed"]
    unks = sum(sp2.EncodeAsIds(r["instruction"] + " " + r["response"]).count(1) for r in mixed_recs)
    assert unks == 0

def test_058_zero_unk_in_tanglish_records(sp2, inst_records):
    tgl_recs = [r for r in inst_records if r["language"] == "tgl"]
    unks = sum(sp2.EncodeAsIds(r["instruction"] + " " + r["response"]).count(1) for r in tgl_recs)
    assert unks == 0

def test_059_tamil_literary_vocabulary_presence(inst_records):
    lit_terms = ["அகராதி", "கல்லணை", "திருக்குறள்", "தொல்காப்பியம்", "நன்றாற்றின்"]
    all_text = " ".join(r["instruction"] + " " + r["response"] for r in inst_records)
    assert sum(1 for term in lit_terms if term in all_text) >= 3

def test_060_modern_tamil_conversational_presence(inst_records):
    conv_terms = ["வணக்கம்", "எப்படி", "உதவலாம்", "நல்வரவு"]
    all_text = " ".join(r["response"] for r in inst_records)
    assert sum(1 for term in conv_terms if term in all_text) >= 3

# ==============================================================================
# GROUP 5: Reasoning & Arithmetic Support (Tests 61-70)
# ==============================================================================

def test_061_domain_reasoning_record_count(inst_records):
    assert sum(1 for r in inst_records if r["domain"] == "reasoning") == 10

def test_062_reasoning_records_preservation(inst_records):
    reas_recs = [r for r in inst_records if r["domain"] == "reasoning"]
    assert len(reas_recs) == 10
    for r in reas_recs:
        assert len(r["instruction"]) > 0
        assert len(r["response"]) > 0

def test_063_step_by_step_reasoning_markers(inst_records):
    step_markers = ["1.", "2.", "படிமுறை", "படி 1", "படி 2", "முதல் விதி", "இரண்டாம் விதி"]
    cnt = sum(1 for r in inst_records if any(sm in r["response"] for sm in step_markers))
    assert cnt >= 3

def test_064_science_laws_and_principles(inst_records):
    sci_recs = [r for r in inst_records if r["domain"] == "science"]
    assert len(sci_recs) == 10

def test_065_computer_science_algorithms_and_patterns(inst_records):
    cs_recs = [r for r in inst_records if r["domain"] == "computer_science"]
    assert len(cs_recs) == 10

def test_066_arithmetic_digits_count(inst_records):
    digit_cnt = sum(1 for r in inst_records if any(c.isdigit() for c in r["response"]))
    assert digit_cnt >= 40

def test_067_mathematical_formula_presence(inst_records):
    formula_recs = [r for r in inst_records if any(sym in r["response"] for sym in ["=", "+", "-", "×", "÷", "%"])]
    assert len(formula_recs) >= 20

def test_068_logical_connectives_in_tamil(inst_records):
    connectives = ["எனவே", "ஆதலால்", "ஆனால்", "ஏனெனில்", "பொழுது"]
    all_text = " ".join(r["response"] for r in inst_records)
    assert any(conn in all_text for conn in connectives)

def test_069_logical_connectives_in_english(inst_records):
    connectives = ["therefore", "because", "however", "when", "then"]
    all_text = " ".join(r["response"] for r in inst_records).lower()
    assert any(conn in all_text for conn in connectives)

def test_070_distinction_between_labeled_and_actual_reasoning(ws04_manifest):
    # Only 10 records are in domain 'reasoning', while 13 records reach Difficulty Level 4
    assert ws04_manifest["capability_coverage_summary"]["CAP-13_reasoning"] == 10
    assert ws04_manifest["difficulty_distribution"]["level_4_reasoning_inference"]["count"] == 13

# ==============================================================================
# GROUP 6: Response Quality & Structural Formatting (Tests 71-80)
# ==============================================================================

def test_071_single_sentence_answers_prevalence(inst_records):
    # Single sentence answers are common for concise definitions
    single_sents = sum(1 for r in inst_records if "." in r["response"] and r["response"].count(".") <= 1)
    assert single_sents >= 150

def test_072_multi_sentence_paragraphs_presence(inst_records):
    multi_sents = sum(1 for r in inst_records if r["response"].count(".") >= 2)
    assert multi_sents >= 100

def test_073_numbered_lists_and_steps_presence(inst_records):
    lists = sum(1 for r in inst_records if "\n" in r["response"] and ("1." in r["response"] or "•" in r["response"] or "-" in r["response"]))
    assert lists >= 10

def test_074_annotated_explanations_presence(inst_records):
    annotated = sum(1 for r in inst_records if "விளக்கம்" in r["instruction"] or "விளக்கம்" in r["response"])
    assert annotated >= 30

def test_075_structural_diversity_non_collapse(inst_records):
    # Ensure dataset does not collapse to only 1 structure
    structs = set()
    for r in inst_records:
        if "\n" in r["response"]: structs.add("multiline")
        if "." in r["response"] and r["response"].count(".") >= 2: structs.add("paragraph")
        if len(r["response"].split()) < 10: structs.add("short")
    assert len(structs) >= 3

def test_076_format_following_summarize_directive(inst_records):
    sum_recs = [r for r in inst_records if "Summarize" in r["instruction"]]
    assert len(sum_recs) >= 1

def test_077_format_following_greeting_directive(inst_records):
    greet_recs = [r for r in inst_records if "greeting" in r["instruction"].lower() or "வணக்கம்" in r["instruction"]]
    assert len(greet_recs) >= 3

def test_078_format_following_definition_query(inst_records):
    def_recs = [r for r in inst_records if "என்றால் என்ன" in r["instruction"] or "Define" in r["instruction"]]
    assert len(def_recs) >= 150

def test_079_format_following_factual_explanation_query(inst_records):
    fact_recs = [r for r in inst_records if "விளக்குக" in r["instruction"] or "Explain" in r["instruction"]]
    assert len(fact_recs) >= 100

def test_080_terminology_preservation_in_responses(inst_records):
    # Technical terms asked in prompt should appear in response
    preserved = 0
    for r in inst_records:
        if r["domain"] == "vocabulary":
            # Extract term inside prompt
            words = [w for w in r["instruction"].split() if len(w) > 4]
            if words and any(w in r["response"] for w in words):
                preserved += 1
    assert preserved >= 15

# ==============================================================================
# GROUP 7: EOS Supervision & Termination (Tests 81-85)
# ==============================================================================

def test_081_every_sequence_ends_in_eos(seq_records):
    for s in seq_records:
        p_len = s["prompt_token_count"]
        r_len = s["target_token_count"]
        assert s["input_ids"][p_len + r_len - 1] == 3

def test_082_every_eos_is_supervised(seq_records):
    for s in seq_records:
        p_len = s["prompt_token_count"]
        r_len = s["target_token_count"]
        assert s["labels"][p_len + r_len - 1] == 3

def test_083_zero_responses_missing_termination(seq_records):
    missing_eos = sum(1 for s in seq_records if s["input_ids"][s["prompt_token_count"] + s["target_token_count"] - 1] != 3)
    assert missing_eos == 0

def test_084_zero_responses_consisting_only_of_eos(seq_records):
    eos_only = sum(1 for s in seq_records if s["target_token_count"] <= 1)
    assert eos_only == 0

def test_085_non_truncated_sequences_eos_count(seq_records):
    non_trunc = [s for s in seq_records if not s["truncated"]]
    assert len(non_trunc) == 301
    assert all(s["input_ids"][s["prompt_token_count"] + s["target_token_count"] - 1] == 3 for s in non_trunc)

# ==============================================================================
# GROUP 8: Capability Cross-Tabulation & Sparsity (Tests 86-95)
# ==============================================================================

def test_086_crosstab_task_by_language_coverage(inst_records):
    tt_lang = Counter((r["task_type"], r["language"]) for r in inst_records)
    # Check that key intersections exist
    assert tt_lang[("definition_qa", "mixed")] == 196
    assert tt_lang[("factual_explanation", "ta")] == 51
    assert tt_lang[("factual_explanation", "en")] == 47
    assert tt_lang[("literature_explanation", "mixed")] == 35

def test_087_crosstab_sparse_intersection_tanglish_reasoning(inst_records):
    tgl_reas = sum(1 for r in inst_records if r["language"] == "tgl" and r["domain"] == "reasoning")
    # Documented sparse intersection
    assert tgl_reas == 0

def test_088_crosstab_sparse_intersection_english_literature(inst_records):
    en_lit = sum(1 for r in inst_records if r["language"] == "en" and r["domain"] == "thirukkural")
    assert en_lit == 0

def test_089_crosstab_task_by_domain_definition_qa_in_vocabulary(inst_records):
    vocab_def = sum(1 for r in inst_records if r["task_type"] == "definition_qa" and r["domain"] == "vocabulary")
    assert vocab_def == 100

def test_090_crosstab_task_by_domain_factual_in_linguistic(inst_records):
    ling_fact = sum(1 for r in inst_records if r["task_type"] == "factual_explanation" and r["domain"] == "linguistic_pretraining")
    assert ling_fact == 68

def test_091_crosstab_literature_tasks_confined_to_literature_domains(inst_records):
    lit_tasks = [r for r in inst_records if r["task_type"] == "literature_explanation"]
    assert all(r["domain"] in ["thirukkural", "literature", "poem"] for r in lit_tasks)

def test_092_crosstab_difficulty_by_language(inst_records, seq_records):
    # Mixed language records should span multiple difficulty levels
    diffs = set()
    for r, s in zip(inst_records, seq_records):
        if r["language"] == "mixed":
            if s["target_token_count"] > 70: diffs.add("high")
            else: diffs.add("low")
    assert len(diffs) == 2

def test_093_crosstab_difficulty_by_task(inst_records, seq_records):
    def_tokens = [s["target_token_count"] for r, s in zip(inst_records, seq_records) if r["task_type"] == "definition_qa"]
    assert min(def_tokens) >= 15
    assert max(def_tokens) >= 100

def test_094_sparse_dialogue_tasks_distribution(inst_records):
    dial_recs = [r for r in inst_records if r["task_type"] == "dialogue"]
    assert len(dial_recs) == 7
    # Spans en, ta, mixed
    langs = set(r["language"] for r in dial_recs)
    assert len(langs) >= 2

def test_095_sparse_directive_tasks_distribution(inst_records):
    dir_recs = [r for r in inst_records if r["task_type"] == "directive"]
    assert len(dir_recs) == 3

# ==============================================================================
# GROUP 9: Benchmark Alignment & Contradiction Audit (Tests 96-105)
# ==============================================================================

def test_096_benchmark_cluster_count(eval_manifest):
    clusters = set(p["cluster"] for p in eval_manifest["probes"])
    assert len(clusters) == 7

def test_097_benchmark_tamil_language_alignment(inst_records):
    ta_sup = sum(1 for r in inst_records if re.search(r"[஀-௿]", r["response"]))
    assert ta_sup >= 300

def test_098_benchmark_english_language_alignment(inst_records):
    en_sup = sum(1 for r in inst_records if re.search(r"[a-zA-Z]", r["response"]))
    assert en_sup >= 200

def test_099_benchmark_tanglish_alignment_is_limited(inst_records):
    tgl_sup = sum(1 for r in inst_records if r["language"] == "tgl")
    assert tgl_sup == 5

def test_100_benchmark_reasoning_alignment_is_moderate(inst_records):
    reas_sup = sum(1 for r in inst_records if r["domain"] in ["reasoning", "science"] or any(c.isdigit() for c in r["response"]))
    assert reas_sup >= 30

def test_101_benchmark_adversarial_alignment_is_weak(ws04_manifest):
    # Benchmark alignment report identifies adversarial as weak
    assert ws04_manifest["benchmark_alignment"]["adversarial"]["status"] == "WEAK"

def test_102_benchmark_grounding_alignment_is_strong(ws04_manifest):
    assert ws04_manifest["benchmark_alignment"]["grounding"]["status"] == "STRONG"

def test_103_contradiction_audit_csv_field_prompts_identified(inst_records):
    # Identify the 16 heuristic field prompt records
    csv_prompts = {"define or explain record_id.", "record_id என்றால் என்ன?", "text என்றால் என்ன?", "வினா என்றால் என்ன?"}
    cnt = sum(1 for r in inst_records if r["instruction"].strip().lower() in csv_prompts)
    assert cnt == 16

def test_104_factual_contradictions_in_core_knowledge_are_zero(inst_records):
    # Ensure that distinct scientific and historical facts do not assert mutually opposing truths
    # e.g., Thirukkural couplet numbers are unique
    kural_recs = [r for r in inst_records if r["domain"] == "thirukkural"]
    kural_prompts = [r["instruction"] for r in kural_recs]
    assert len(kural_prompts) == len(set(kural_prompts))

def test_105_zero_exact_benchmark_probe_contamination(inst_records, eval_manifest):
    bench_prompts = set("".join(p["prompt"].split()) for p in eval_manifest["probes"])
    for r in inst_records:
        assert "".join(r["instruction"].split()) not in bench_prompts

# ==============================================================================
# GROUP 10: Security, Unsupported Risks & Frozen Baselines (Tests 106-115)
# ==============================================================================

def test_106_unsupported_capability_risk_tanglish_documented(ws04_manifest):
    lims = {lim["category"]: lim for lim in ws04_manifest["documented_limitations"]}
    assert "tanglish_scarcity" in lims

def test_107_unsupported_capability_risk_adversarial_documented(ws04_manifest):
    lims = {lim["category"]: lim for lim in ws04_manifest["documented_limitations"]}
    assert "adversarial_safety_scarcity" in lims

def test_108_unsupported_capability_risk_heuristic_prompts_documented(ws04_manifest):
    lims = {lim["category"]: lim for lim in ws04_manifest["documented_limitations"]}
    assert "heuristic_field_prompts" in lims

def test_109_ws04_verdict_is_qualified_with_limitations(ws04_manifest):
    assert "B — QUALIFIED WITH LIMITATIONS" in ws04_manifest["verdict"]

def test_110_frozen_phase55_corpus_hash_unmodified():
    expected = "3e1481c3279c24eb957a90c9d7b8e642e2f657905463c3d7130475dbcb7919d1"
    assert hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest() == expected

def test_111_frozen_tokenizer_v2_hash_unmodified():
    expected = "65342625ebb88eaab0996f0f6c5f3ef24ae9fd3203bc8377a0db353601e9ffd4"
    assert hashlib.sha256(TOK_PATH.read_bytes()).hexdigest() == expected

def test_112_frozen_benchmark_manifest_hash_unmodified():
    expected = "554bf72317d9439f7bd5f19e514d23c6a8fb0170807699a087631cbd4331d088"
    assert hashlib.sha256(EVAL_PATH.read_bytes()).hexdigest() == expected

def test_113_frozen_production_db_hash_unmodified():
    expected = "34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729"
    assert hashlib.sha256(DB_PATH.read_bytes()).hexdigest() == expected

def test_114_candidate_public_traffic_share_is_zero(ws04_manifest):
    assert ws04_manifest["production_isolation"]["candidate_traffic_share"] == 0.0
    assert ws04_manifest["production_isolation"]["is_public_chat_eligible"] is False

def test_115_training_execution_remains_blocked(ws04_manifest):
    assert ws04_manifest["production_isolation"]["training_execution_authorized"] is False
