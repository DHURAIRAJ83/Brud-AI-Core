"""MB-30: unit tests for the core_model/mini_brain/runtime_manager/
modules -- no database, no app, no HTTP client, no filesystem I/O.
"""

from __future__ import annotations

import pytest

from core_model.mini_brain.runtime_manager import (
    benchmark_scorer,
    checksum_verifier,
    disk_space_guard,
    download_progress_tracker,
    fallback_orchestrator,
    install_plan_builder,
    model_catalog,
    ram_guard,
    runtime_state_builder,
    uninstall_planner,
)

# -- model_catalog ------------------------------------------------------------------------


def test_known_model_ids_has_four_entries() -> None:
    assert len(model_catalog.known_model_ids()) == 4


def test_recommended_model_id_is_qwen_1_5b() -> None:
    assert model_catalog.recommended_model_id() == "qwen2.5-1.5b-instruct-q4_k_m"


def test_optional_model_ids_excludes_recommended() -> None:
    optional = model_catalog.optional_model_ids()
    assert model_catalog.recommended_model_id() not in optional
    assert len(optional) == 3


def test_catalog_entry_known_model_has_all_required_fields() -> None:
    entry = model_catalog.catalog_entry("qwen2.5-1.5b-instruct-q4_k_m")
    for field in ("display_name", "download_url", "sha256", "expected_size_bytes", "recommended_ram_gb", "tamil_support", "speed_tier"):
        assert field in entry


def test_catalog_entry_unknown_returns_none() -> None:
    assert model_catalog.catalog_entry("bogus-model") is None


def test_is_known_model() -> None:
    assert model_catalog.is_known_model("tinyllama-1.1b-chat-q4_k_m") is True
    assert model_catalog.is_known_model("bogus") is False


def test_full_catalog_includes_model_id_in_each_entry() -> None:
    result = model_catalog.full_catalog()
    assert len(result["models"]) == 4
    assert all("model_id" in entry for entry in result["models"])


def test_download_urls_are_official_huggingface() -> None:
    for model_id in model_catalog.known_model_ids():
        entry = model_catalog.catalog_entry(model_id)
        assert entry["download_url"].startswith("https://huggingface.co/")


def test_catalog_sha256_values_are_real_not_placeholders() -> None:
    """Regression guard (post-audit remediation): every catalog sha256
    must be a genuine, well-formed digest -- not the all-zeros
    placeholder this catalog originally shipped with. Guards against a
    future edit silently reverting to a placeholder."""
    for model_id in model_catalog.known_model_ids():
        entry = model_catalog.catalog_entry(model_id)
        digest = entry["sha256"]
        assert digest != "0" * 64, f"{model_id} still has a placeholder sha256"
        assert len(digest) == 64
        assert all(ch in "0123456789abcdef" for ch in digest.lower())


def test_catalog_expected_size_bytes_are_real_not_round_placeholders() -> None:
    """The original placeholders were suspiciously round numbers
    (1_100_000_000, 669_000_000, 1_900_000_000). Real Hugging Face LFS
    file sizes are never exactly round -- this guards against a future
    edit reverting to an approximate placeholder instead of the real,
    published byte count."""
    placeholder_sizes = {1_100_000_000, 669_000_000, 1_900_000_000}
    for model_id in model_catalog.known_model_ids():
        entry = model_catalog.catalog_entry(model_id)
        assert entry["expected_size_bytes"] not in placeholder_sizes, f"{model_id} still has a placeholder size"
        assert entry["expected_size_bytes"] > 0


def test_qwen_0_5b_catalog_entry_exists() -> None:
    """MB-31A: the new low-RAM catalog entry, verified against the real
    Hugging Face repo (API `?blobs=true` and the resolve URL's own
    x-linked-etag/x-linked-size, both agreeing) before this was written."""
    entry = model_catalog.catalog_entry("qwen2.5-0.5b-instruct-q4_k_m")
    assert entry is not None
    assert entry["display_name"] == "Qwen2.5-0.5B-Instruct-Q4_K_M"
    assert entry["file_name"] == "qwen2.5-0.5b-instruct-q4_k_m.gguf"
    assert entry["tier"] == "optional"


def test_qwen_0_5b_sha256_is_real_not_placeholder() -> None:
    entry = model_catalog.catalog_entry("qwen2.5-0.5b-instruct-q4_k_m")
    digest = entry["sha256"]
    assert digest == "74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db"
    assert digest != "0" * 64
    assert len(digest) == 64
    assert all(ch in "0123456789abcdef" for ch in digest.lower())


def test_qwen_0_5b_file_size_is_real_and_smaller_than_1_5b() -> None:
    entry = model_catalog.catalog_entry("qwen2.5-0.5b-instruct-q4_k_m")
    larger_entry = model_catalog.catalog_entry("qwen2.5-1.5b-instruct-q4_k_m")
    assert entry["expected_size_bytes"] == 491_400_032
    assert entry["expected_size_bytes"] > 0
    assert entry["expected_size_bytes"] < larger_entry["expected_size_bytes"]


def test_recommended_model_id_still_qwen_1_5b_after_0_5b_addition() -> None:
    """MB-31A must not change the Runtime-Manager-level single
    recommendation -- only which models a low-RAM machine can load."""
    assert model_catalog.recommended_model_id() == "qwen2.5-1.5b-instruct-q4_k_m"


# -- install_plan_builder -----------------------------------------------------------------


def test_build_plan_joins_target_path() -> None:
    entry = model_catalog.catalog_entry("qwen2.5-1.5b-instruct-q4_k_m")
    plan = install_plan_builder.build_plan(model_id="qwen2.5-1.5b-instruct-q4_k_m", catalog_entry=entry, allowed_model_dir="/opt/models")
    assert plan["target_path"] == "/opt/models/qwen2.5-1.5b-instruct-q4_k_m.gguf"


def test_build_plan_preserves_expected_sha256_and_size() -> None:
    entry = model_catalog.catalog_entry("tinyllama-1.1b-chat-q4_k_m")
    plan = install_plan_builder.build_plan(model_id="tinyllama-1.1b-chat-q4_k_m", catalog_entry=entry, allowed_model_dir="/opt/models")
    assert plan["expected_sha256"] == entry["sha256"]
    assert plan["expected_size_bytes"] == entry["expected_size_bytes"]


def test_build_plan_windows_style_dir() -> None:
    entry = model_catalog.catalog_entry("qwen2.5-1.5b-instruct-q4_k_m")
    plan = install_plan_builder.build_plan(model_id="qwen2.5-1.5b-instruct-q4_k_m", catalog_entry=entry, allowed_model_dir="C:\\Users\\admin\\models")
    assert plan["file_name"] in plan["target_path"]


# -- checksum_verifier ---------------------------------------------------------------------


def test_compute_sha256_deterministic() -> None:
    assert checksum_verifier.compute_sha256(b"abc") == checksum_verifier.compute_sha256(b"abc")


def test_compute_sha256_differs_for_different_bytes() -> None:
    assert checksum_verifier.compute_sha256(b"abc") != checksum_verifier.compute_sha256(b"abd")


def test_verify_digest_case_insensitive() -> None:
    digest = checksum_verifier.compute_sha256(b"hello")
    result = checksum_verifier.verify_digest(actual_sha256=digest.upper(), expected_sha256=digest.lower())
    assert result["matches"] is True


def test_verify_digest_bilingual_message_on_mismatch() -> None:
    result = checksum_verifier.verify_digest(actual_sha256="a" * 64, expected_sha256="b" * 64)
    assert result["matches"] is False
    assert result["message_en"] and result["message_ta"]


# -- disk_space_guard -----------------------------------------------------------------------


def test_disk_space_guard_exact_boundary_unsafe_within_margin() -> None:
    result = disk_space_guard.check(available_bytes=1_100_000_000, required_bytes=1_100_000_000)
    assert result["safe"] is False  # exactly at required, no margin


def test_disk_space_guard_safe_with_generous_headroom() -> None:
    result = disk_space_guard.check(available_bytes=10_000_000_000, required_bytes=1_100_000_000)
    assert result["safe"] is True


def test_disk_space_guard_shortfall_computed() -> None:
    result = disk_space_guard.check(available_bytes=500_000_000, required_bytes=1_100_000_000)
    assert result["shortfall_bytes"] > 0


def test_disk_space_guard_bilingual_messages() -> None:
    result = disk_space_guard.check(available_bytes=0, required_bytes=1)
    assert result["message_en"] and result["message_ta"]


# -- ram_guard ------------------------------------------------------------------------------


def test_ram_guard_exact_minimum_boundary_is_safe() -> None:
    result = ram_guard.check_load_safety(available_ram_gb=4.0, estimated_model_ram_gb=2.5)
    assert result["projected_free_ram_gb"] == 1.5
    assert result["safe"] is True


def test_ram_guard_just_below_minimum_is_unsafe() -> None:
    result = ram_guard.check_load_safety(available_ram_gb=3.99, estimated_model_ram_gb=2.5)
    assert result["safe"] is False


@pytest.mark.parametrize("available,estimated,expected_safe", [
    (4.5, 2.5, True),   # 6GB machine, 1.5B model -- must pass per spec section 6
    (4.5, 3.5, False),  # 6GB machine, 3B model -- must warn per spec section 6
])
def test_ram_guard_matches_spec_worked_examples(available: float, estimated: float, expected_safe: bool) -> None:
    result = ram_guard.check_load_safety(available_ram_gb=available, estimated_model_ram_gb=estimated)
    assert result["safe"] is expected_safe


def test_ram_guard_minimum_constant_is_1_5gb() -> None:
    assert ram_guard.MIN_FREE_RAM_GB == 1.5


# -- benchmark_scorer -----------------------------------------------------------------------


@pytest.mark.parametrize("tps,expected_rating", [
    (20.0, "excellent"),
    (10.0, "good"),
    (5.0, "fair"),
    (1.0, "poor"),
])
def test_benchmark_scorer_rating_thresholds(tps: float, expected_rating: str) -> None:
    result = benchmark_scorer.score(load_time_ms=500, first_token_latency_ms=100, tokens_per_second=tps, peak_ram_mb=2000)
    assert result["rating"] == expected_rating


def test_benchmark_scorer_rating_label_bilingual() -> None:
    result = benchmark_scorer.score(load_time_ms=500, first_token_latency_ms=100, tokens_per_second=20, peak_ram_mb=2000)
    assert result["rating_label"]["en"] == "Excellent"
    assert result["rating_label"]["ta"]


def test_benchmark_scorer_preserves_raw_metrics() -> None:
    result = benchmark_scorer.score(load_time_ms=123.4, first_token_latency_ms=56.7, tokens_per_second=9.0, peak_ram_mb=1500.5)
    assert result["load_time_ms"] == 123.4
    assert result["peak_ram_mb"] == 1500.5


# -- runtime_state_builder -----------------------------------------------------------------------


def test_build_status_no_current_runtime() -> None:
    result = runtime_state_builder.build_status(current_runtime=None, installations=[], hardware=None)
    assert result["loaded"] is False
    assert result["installed_count"] == 0


def test_build_status_counts_only_installed_status() -> None:
    installations = [
        {"status": "installed"}, {"status": "installed"}, {"status": "removed"}, {"status": "failed"},
    ]
    result = runtime_state_builder.build_status(current_runtime=None, installations=installations, hardware=None)
    assert result["installed_count"] == 2
    assert len(result["installed_models"]) == 2


def test_build_status_loaded_reflects_current_runtime() -> None:
    result = runtime_state_builder.build_status(current_runtime={"loaded": True}, installations=[], hardware={"total_ram_gb": 8})
    assert result["loaded"] is True
    assert result["hardware"]["total_ram_gb"] == 8


# -- fallback_orchestrator -----------------------------------------------------------------------


def test_fallback_step1_loaded_local() -> None:
    result = fallback_orchestrator.decide(local_loaded=True, local_installed_not_loaded=False, external_enabled=True)
    assert result["step"] == 1
    assert result["backend"] == "local_loaded"


def test_fallback_step2_installed_not_loaded() -> None:
    result = fallback_orchestrator.decide(local_loaded=False, local_installed_not_loaded=True, external_enabled=False)
    assert result["step"] == 2
    assert result["backend"] == "local_installed"


def test_fallback_step3_external() -> None:
    result = fallback_orchestrator.decide(local_loaded=False, local_installed_not_loaded=False, external_enabled=True)
    assert result["step"] == 3
    assert result["backend"] == "external"


def test_fallback_step4_unavailable() -> None:
    result = fallback_orchestrator.decide(local_loaded=False, local_installed_not_loaded=False, external_enabled=False)
    assert result["step"] == 4
    assert result["backend"] == "unavailable"


def test_fallback_loaded_takes_priority_over_everything() -> None:
    result = fallback_orchestrator.decide(local_loaded=True, local_installed_not_loaded=True, external_enabled=True)
    assert result["step"] == 1


# -- download_progress_tracker -----------------------------------------------------------------------


def test_progress_zero_bytes() -> None:
    result = download_progress_tracker.compute_progress(bytes_downloaded=0, total_bytes=1000, elapsed_seconds=1.0)
    assert result["percent"] == 0.0
    assert result["complete"] is False


def test_progress_complete() -> None:
    result = download_progress_tracker.compute_progress(bytes_downloaded=1000, total_bytes=1000, elapsed_seconds=10.0)
    assert result["percent"] == 100.0
    assert result["complete"] is True


def test_progress_percent_never_exceeds_100() -> None:
    result = download_progress_tracker.compute_progress(bytes_downloaded=1100, total_bytes=1000, elapsed_seconds=10.0)
    assert result["percent"] == 100.0


def test_progress_zero_total_bytes_does_not_crash() -> None:
    result = download_progress_tracker.compute_progress(bytes_downloaded=0, total_bytes=0, elapsed_seconds=1.0)
    assert result["percent"] == 0.0


def test_progress_eta_none_when_no_speed_yet() -> None:
    result = download_progress_tracker.compute_progress(bytes_downloaded=0, total_bytes=1000, elapsed_seconds=0.0)
    assert result["eta_seconds"] is None


def test_progress_speed_and_eta_computed() -> None:
    result = download_progress_tracker.compute_progress(bytes_downloaded=100_000_000, total_bytes=1_000_000_000, elapsed_seconds=10.0)
    assert result["speed_mb_per_sec"] > 0
    assert result["eta_seconds"] is not None
    assert result["eta_seconds"] > 0


# -- uninstall_planner -----------------------------------------------------------------------


def test_build_removal_plan_shape() -> None:
    installation = {"public_id": "p1", "model_name": "qwen2.5-1.5b-instruct-q4_k_m", "install_path": "/opt/models/x.gguf", "status": "installed"}
    plan = uninstall_planner.build_removal_plan(installation=installation)
    assert plan["file_to_delete"] == "/opt/models/x.gguf"
    assert plan["was_installed"] is True


def test_build_removal_plan_not_installed_flag() -> None:
    installation = {"public_id": "p1", "model_name": "x", "install_path": "/opt/models/x.gguf", "status": "failed"}
    plan = uninstall_planner.build_removal_plan(installation=installation)
    assert plan["was_installed"] is False
