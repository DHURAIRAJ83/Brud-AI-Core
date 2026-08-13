"""MB-07: pure-module unit tests for
core_model/mini_brain/release_pipeline/."""

from core_model.mini_brain.release_pipeline.checkpoint_validator import validate_checkpoint
from core_model.mini_brain.release_pipeline.compatibility_validator import validate_compatibility
from core_model.mini_brain.release_pipeline.gguf_export_manager import build_export_plan
from core_model.mini_brain.release_pipeline.integrity_validator import validate_integrity
from core_model.mini_brain.release_pipeline.model_converter import build_tensor_mapping
from core_model.mini_brain.release_pipeline.performance_validator import classify_performance
from core_model.mini_brain.release_pipeline.quantization_manager import (
    available_levels,
    describe_quantization_level,
    plan_quantization,
)
from core_model.mini_brain.release_pipeline.release_report_generator import generate_release_report
from core_model.mini_brain.release_pipeline.rollback_manager import evaluate_rollback_target
from core_model.mini_brain.release_pipeline.version_manager import (
    parse_version,
    suggest_next_version,
    validate_next_version,
)

# -- checkpoint_validator --------------------------------------------------------

_CHECKPOINT_ROW = {"status": "verified"}


def test_checkpoint_validator_passes_when_everything_matches() -> None:
    keys = ["a", "b"]
    result = validate_checkpoint(
        artifact_exists=True, artifact_path_confined=True, artifact_size_ok=True,
        artifact_checksum_matches=True, checkpoint_row=_CHECKPOINT_ROW, load_error=None,
        state_dict_keys=keys, expected_tensor_keys=keys,
    )
    assert result["status"] == "Valid"
    assert result["reasons"] == []


def test_checkpoint_validator_fails_when_missing() -> None:
    result = validate_checkpoint(
        artifact_exists=False, artifact_path_confined=False, artifact_size_ok=False,
        artifact_checksum_matches=False, checkpoint_row=None, load_error=None,
        state_dict_keys=None, expected_tensor_keys=["a"],
    )
    assert result["status"] == "Invalid"
    assert any("does not exist" in r for r in result["reasons"])
    assert any("no checkpoint metadata" in r for r in result["reasons"])


def test_checkpoint_validator_fails_on_tensor_key_mismatch() -> None:
    result = validate_checkpoint(
        artifact_exists=True, artifact_path_confined=True, artifact_size_ok=True,
        artifact_checksum_matches=True, checkpoint_row=_CHECKPOINT_ROW, load_error=None,
        state_dict_keys=["a", "c"], expected_tensor_keys=["a", "b"],
    )
    assert result["status"] == "Invalid"
    assert any("do not match the expected architecture" in r for r in result["reasons"])


def test_checkpoint_validator_fails_on_load_error() -> None:
    result = validate_checkpoint(
        artifact_exists=True, artifact_path_confined=True, artifact_size_ok=True,
        artifact_checksum_matches=True, checkpoint_row=_CHECKPOINT_ROW, load_error="checksum mismatch",
        state_dict_keys=None, expected_tensor_keys=["a"],
    )
    assert result["status"] == "Invalid"
    assert any("failed to load" in r for r in result["reasons"])


# -- model_converter --------------------------------------------------------------


def _full_state_dict_keys(num_layers: int) -> list[str]:
    keys = ["embed_tokens.embedding.weight", "norm.weight", "lm_head.weight"]
    for i in range(num_layers):
        p = f"layers.{i}."
        keys += [
            p + "input_norm.weight", p + "attention.q_proj.weight", p + "attention.k_proj.weight",
            p + "attention.v_proj.weight", p + "attention.o_proj.weight",
            p + "post_attention_norm.weight", p + "feed_forward.gate_proj.weight",
            p + "feed_forward.up_proj.weight", p + "feed_forward.down_proj.weight",
        ]
    return keys


def test_model_converter_maps_all_tensors_for_complete_state_dict() -> None:
    result = build_tensor_mapping(num_hidden_layers=2, state_dict_keys=_full_state_dict_keys(2))
    assert result["architecture_compatible"] is True
    assert result["missing_source_tensors"] == []
    assert result["tensor_count"] == 3 + 2 * 9
    assert result["permute_applied"] is False
    assert result["mapping"]["blk.0.attn_q.weight"] == "layers.0.attention.q_proj.weight"


def test_model_converter_reports_missing_tensors() -> None:
    keys = _full_state_dict_keys(1)
    keys.remove("layers.0.attention.q_proj.weight")
    result = build_tensor_mapping(num_hidden_layers=1, state_dict_keys=keys)
    assert result["architecture_compatible"] is False
    assert "layers.0.attention.q_proj.weight" in result["missing_source_tensors"]
    assert "blk.0.attn_q.weight" not in result["mapping"]


def test_model_converter_reports_unmapped_extra_tensors() -> None:
    keys = _full_state_dict_keys(1) + ["some.extra.buffer"]
    result = build_tensor_mapping(num_hidden_layers=1, state_dict_keys=keys)
    assert result["unmapped_source_tensors"] == ["some.extra.buffer"]
    assert result["architecture_compatible"] is True


# -- quantization_manager ----------------------------------------------------------


def test_supported_levels_are_reported_supported() -> None:
    for level in available_levels():
        desc = describe_quantization_level(level)
        assert desc["supported"] is True
        assert "gguf_type" in desc


def test_k_quant_levels_are_reported_unsupported_with_real_reason() -> None:
    for level in ("q2", "q3", "q4_k_m", "q5", "q6"):
        desc = describe_quantization_level(level)
        assert desc["supported"] is False
        assert "no quantize encoder" in desc["reason"]


def test_unknown_level_is_unsupported() -> None:
    desc = describe_quantization_level("not-a-real-level")
    assert desc["supported"] is False


def test_plan_quantization_splits_supported_and_unsupported() -> None:
    plan = plan_quantization(["f32", "q8_0", "q4_k_m", "q2"])
    assert plan["supported_count"] == 2
    assert plan["unsupported_count"] == 2
    assert plan["all_supported"] is False


# -- gguf_export_manager ------------------------------------------------------------


def test_build_export_plan_has_required_llama_kv_fields() -> None:
    plan = build_export_plan(
        context_length=512, hidden_size=256, intermediate_size=512, num_hidden_layers=4,
        num_attention_heads=8, num_key_value_heads=8, head_dimension=32, rms_norm_epsilon=1e-5,
        rope_theta=10000.0, vocabulary_size=1000, bos_token_id=1, eos_token_id=2, unk_token_id=3,
        pad_token_id=0, quantization_gguf_type="Q8_0", tensor_mapping={"token_embd.weight": "x"},
    )
    assert plan["architecture"] == "llama"
    kv = plan["kv_metadata"]
    assert kv["general.architecture"] == "llama"
    assert kv["llama.context_length"] == 512
    assert kv["llama.attention.head_count"] == 8
    assert kv["tokenizer.ggml.model"] == "llama"
    assert plan["expected_tensor_count"] == 1


# -- integrity_validator ------------------------------------------------------------


def test_integrity_validator_passes_when_everything_matches() -> None:
    result = validate_integrity(
        file_exists=True, file_size_bytes=1000, checksum_sha256="a" * 64,
        expected_tensor_count=21, actual_tensor_count=21, vocabulary_size_expected=100,
        vocabulary_size_in_file=100, architecture_in_file="llama", expected_architecture="llama",
    )
    assert result["status"] == "Valid"


def test_integrity_validator_fails_on_tensor_count_mismatch() -> None:
    result = validate_integrity(
        file_exists=True, file_size_bytes=1000, checksum_sha256="a" * 64,
        expected_tensor_count=21, actual_tensor_count=20, vocabulary_size_expected=100,
        vocabulary_size_in_file=100, architecture_in_file="llama", expected_architecture="llama",
    )
    assert result["status"] == "Invalid"
    assert any("tensor count mismatch" in r for r in result["reasons"])


def test_integrity_validator_fails_on_missing_file() -> None:
    result = validate_integrity(
        file_exists=False, file_size_bytes=0, checksum_sha256=None,
        expected_tensor_count=21, actual_tensor_count=None, vocabulary_size_expected=100,
        vocabulary_size_in_file=None, architecture_in_file=None, expected_architecture="llama",
    )
    assert result["status"] == "Invalid"
    assert len(result["reasons"]) >= 3


# -- compatibility_validator ---------------------------------------------------------


def test_compatibility_validator_passes_when_load_and_generation_succeed() -> None:
    result = validate_compatibility(
        load_succeeded=True, load_error=None, vocabulary_size_matches=True,
        context_length_matches=True, generation_smoke_test_passed=True,
        generation_smoke_test_error=None,
    )
    assert result["status"] == "Compatible"
    assert result["components"]["prompt_builder"]["compatible_by_construction"] is True


def test_compatibility_validator_fails_on_load_error() -> None:
    result = validate_compatibility(
        load_succeeded=False, load_error="bad magic", vocabulary_size_matches=True,
        context_length_matches=True, generation_smoke_test_passed=False,
        generation_smoke_test_error="no model loaded",
    )
    assert result["status"] == "Incompatible"
    assert result["components"]["mb04_runtime"]["reason"] == "bad magic"


# -- performance_validator ------------------------------------------------------------


def test_performance_validator_fast_tier() -> None:
    result = classify_performance(
        load_time_ms=500, memory_bytes=1024**3, tokens_per_second=20.0,
        prompt_latency_ms=100, generation_latency_ms=100,
    )
    assert result["overall_tier"] == "Fast"


def test_performance_validator_slow_tier_when_any_metric_is_slow() -> None:
    result = classify_performance(
        load_time_ms=500, memory_bytes=1024**3, tokens_per_second=20.0,
        prompt_latency_ms=100, generation_latency_ms=10_000,
    )
    assert result["overall_tier"] == "Slow"
    assert result["tiers"]["generation_latency"] == "Slow"


# -- version_manager -----------------------------------------------------------------


def test_parse_version_valid() -> None:
    assert parse_version("Brud-0.1") == (0, 1)
    assert parse_version("Brud-1.10") == (1, 10)


def test_parse_version_invalid() -> None:
    assert parse_version("0.1") is None
    assert parse_version("brud-0.1") is None


def test_validate_next_version_rejects_duplicate() -> None:
    result = validate_next_version(proposed="Brud-0.1", existing_versions=["Brud-0.1"])
    assert result["valid"] is False


def test_validate_next_version_rejects_not_ahead() -> None:
    result = validate_next_version(proposed="Brud-0.1", existing_versions=["Brud-0.2"])
    assert result["valid"] is False


def test_validate_next_version_accepts_ahead_version() -> None:
    result = validate_next_version(proposed="Brud-0.3", existing_versions=["Brud-0.1", "Brud-0.2"])
    assert result["valid"] is True


def test_suggest_next_version_first_release() -> None:
    assert suggest_next_version([]) == "Brud-0.1"


def test_suggest_next_version_increments_minor() -> None:
    assert suggest_next_version(["Brud-0.1", "Brud-0.5", "Brud-0.2"]) == "Brud-0.6"


# -- rollback_manager -----------------------------------------------------------------


def test_rollback_target_valid() -> None:
    releases = [{"version": "Brud-0.1", "status": "released"}, {"version": "Brud-0.2", "status": "released"}]
    result = evaluate_rollback_target(target_version="Brud-0.1", current_version="Brud-0.2", releases=releases)
    assert result["valid"] is True


def test_rollback_target_missing_is_invalid() -> None:
    result = evaluate_rollback_target(target_version="Brud-9.9", current_version="Brud-0.2", releases=[])
    assert result["valid"] is False


def test_rollback_target_archived_is_invalid() -> None:
    releases = [{"version": "Brud-0.1", "status": "archived"}]
    result = evaluate_rollback_target(target_version="Brud-0.1", current_version="Brud-0.2", releases=releases)
    assert result["valid"] is False
    assert any("archived" in r for r in result["reasons"])


def test_rollback_target_same_as_current_is_invalid() -> None:
    releases = [{"version": "Brud-0.2", "status": "released"}]
    result = evaluate_rollback_target(target_version="Brud-0.2", current_version="Brud-0.2", releases=releases)
    assert result["valid"] is False


# -- release_report_generator ----------------------------------------------------------


def test_release_report_marks_sections_present() -> None:
    report = generate_release_report(
        session_public_id="s1", checkpoint_validation_report={"status": "Valid"},
        conversion_report={"architecture_compatible": True}, quantization_report=None,
        integrity_report=None, compatibility_report=None, performance_report=None,
        version_string=None, model_release_public_id=None,
    )
    assert report["sections_present"]["checkpoint_validation_report"] is True
    assert report["sections_present"]["quantization_report"] is False
    assert report["ready_for_admin_review"] is True


def test_release_report_flags_blocking_findings() -> None:
    report = generate_release_report(
        session_public_id="s1", checkpoint_validation_report={"status": "Invalid", "reasons": ["bad checksum"]},
        conversion_report=None, quantization_report=None, integrity_report=None,
        compatibility_report=None, performance_report=None, version_string=None,
        model_release_public_id=None,
    )
    assert report["has_blocking_findings"] is True
    assert "bad checksum" in report["blocking_reasons"]
    assert report["ready_for_admin_review"] is False
