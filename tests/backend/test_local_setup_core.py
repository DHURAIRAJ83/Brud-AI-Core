"""MB-29: unit tests for the core_model/mini_brain/local_setup/
modules -- no database, no app, no HTTP client.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core_model.mini_brain.local_setup import (
    bilingual_help_registry,
    capability_catalog,
    diagnostics_formatter,
    hardware_probe,
    health_status_builder,
    model_recommender,
    model_scanner,
    provider_model_catalog,
    setup_guide_builder,
    storage_estimator,
)

# -- hardware_probe --------------------------------------------------------------------


def test_probe_returns_all_required_fields(tmp_path: Path) -> None:
    result = hardware_probe.probe(disk_check_path=tmp_path)
    for field in (
        "total_ram_gb", "available_ram_gb", "cpu_cores", "cpu_threads", "architecture",
        "os_name", "disk_free_gb", "python_version", "recommended_ram_tier",
    ):
        assert field in result


def test_probe_ram_tier_boundaries() -> None:
    assert hardware_probe._ram_tier(3.5) == "4GB"
    assert hardware_probe._ram_tier(4.0) == "4GB"
    assert hardware_probe._ram_tier(5.5) == "6GB"
    assert hardware_probe._ram_tier(7.9) == "8GB"
    assert hardware_probe._ram_tier(15.9) == "16GB"
    assert hardware_probe._ram_tier(64.0) == "32GB+"


def test_probe_disk_free_gb_reflects_real_tmp_path(tmp_path: Path) -> None:
    result = hardware_probe.probe(disk_check_path=tmp_path)
    assert result["disk_free_gb"] > 0


def test_probe_never_raises_on_nonexistent_disk_path() -> None:
    result = hardware_probe.probe(disk_check_path=Path("/totally/nonexistent/path/xyz"))
    assert result["disk_free_gb"] == 0.0


def test_probe_cpu_counts_are_positive_integers() -> None:
    result = hardware_probe.probe()
    assert isinstance(result["cpu_threads"], int)
    assert result["cpu_threads"] >= 1


# -- model_scanner ---------------------------------------------------------------------


def test_scan_directory_empty(tmp_path: Path) -> None:
    root = tmp_path / "models"
    root.mkdir()
    assert model_scanner.scan_directory(root) == []


def test_scan_directory_nonexistent_returns_empty() -> None:
    assert model_scanner.scan_directory(Path("/totally/nonexistent/xyz")) == []


def test_scan_directory_finds_gguf_and_uppercase_variant(tmp_path: Path) -> None:
    root = tmp_path / "models"
    root.mkdir()
    (root / "a.gguf").write_bytes(b"x")
    (root / "b.GGUF").write_bytes(b"yy")
    results = model_scanner.scan_directory(root)
    assert len(results) == 2


def test_scan_directory_ignores_non_gguf_files(tmp_path: Path) -> None:
    root = tmp_path / "models"
    root.mkdir()
    (root / "readme.txt").write_text("hi")
    (root / "model.gguf").write_bytes(b"x")
    results = model_scanner.scan_directory(root)
    assert len(results) == 1
    assert results[0]["filename"] == "model.gguf"


@pytest.mark.parametrize(
    "filename,expected_family,expected_quant,expected_params",
    [
        ("qwen2.5-1.5b-instruct-q4_k_m.gguf", "qwen2.5", "Q4_K_M", 1.5),
        ("tinyllama-1.1b-chat.Q4_K_M.gguf", "tinyllama", "Q4_K_M", 1.1),
        ("mistral-7b-instruct.Q5_K_M.gguf", "mistral", "Q5_K_M", 7.0),
        ("totally-unrecognizable-file.gguf", None, None, None),
    ],
)
def test_scan_directory_infers_metadata_from_filename(
    tmp_path: Path, filename: str, expected_family, expected_quant, expected_params,
) -> None:
    root = tmp_path / "models"
    root.mkdir()
    (root / filename).write_bytes(b"x")
    results = model_scanner.scan_directory(root)
    assert results[0]["inferred_family"] == expected_family
    assert results[0]["inferred_quantization"] == expected_quant
    assert results[0]["inferred_params"] == expected_params


def test_scan_directory_size_and_mtime_are_real(tmp_path: Path) -> None:
    root = tmp_path / "models"
    root.mkdir()
    (root / "model.gguf").write_bytes(b"x" * (2 * 1024 * 1024))  # 2 MiB -- large enough to round to a nonzero GB figure
    results = model_scanner.scan_directory(root)
    assert results[0]["size_gb"] > 0
    assert results[0]["modified_at"] > 0


# -- storage_estimator ------------------------------------------------------------------


def test_estimate_ram_usage_scales_with_params() -> None:
    small = storage_estimator.estimate_ram_usage_gb(params_billions=1.0, quantization="Q4_K_M")
    large = storage_estimator.estimate_ram_usage_gb(params_billions=7.0, quantization="Q4_K_M")
    assert large > small


def test_estimate_ram_usage_unknown_quant_uses_default() -> None:
    result = storage_estimator.estimate_ram_usage_gb(params_billions=1.0, quantization="totally_unknown")
    assert result > 0


def test_estimate_disk_usage_less_than_ram_usage() -> None:
    disk = storage_estimator.estimate_disk_usage_gb(params_billions=3.0, quantization="Q4_K_M")
    ram = storage_estimator.estimate_ram_usage_gb(params_billions=3.0, quantization="Q4_K_M")
    assert disk < ram


# -- capability_catalog ------------------------------------------------------------------


def test_label_known_key() -> None:
    assert capability_catalog.label(capability_catalog.SPEED_LEVELS, "good") == {"en": "Good", "ta": "நல்லது"}


def test_label_unknown_key_falls_back_to_key_itself() -> None:
    assert capability_catalog.label(capability_catalog.SPEED_LEVELS, "bogus") == {"en": "bogus", "ta": "bogus"}


def test_yes_no() -> None:
    assert capability_catalog.yes_no(True) == {"en": "Yes", "ta": "ஆம்"}
    assert capability_catalog.yes_no(False) == {"en": "No", "ta": "இல்லை"}


# -- model_recommender -------------------------------------------------------------------


def test_recommend_6gb_matches_section14_worked_example() -> None:
    result = model_recommender.recommend(total_ram_gb=5.69, recommended_ram_tier="6GB")
    top = result["top_recommendation"]
    assert top["model_name"] == "Qwen2.5-1.5B-Instruct"
    assert top["expected_ram_usage_gb"] == 2.5
    assert top["expected_speed"]["en"] == "Good"
    assert top["tamil_support"]["en"] == "Good"
    assert top["offline_support"]["en"] == "Yes"
    assert top["recommended_for_brud_admin"]["en"] == "Yes"


def test_recommend_6gb_has_exactly_four_models() -> None:
    result = model_recommender.recommend(total_ram_gb=5.0, recommended_ram_tier="6GB")
    assert len(result["models"]) == 4


def test_recommend_8gb_is_cumulative_with_6gb() -> None:
    result = model_recommender.recommend(total_ram_gb=7.5, recommended_ram_tier="8GB")
    names = {m["model_name"] for m in result["models"]}
    assert "Qwen2.5-1.5B-Instruct" in names  # from the 6GB tier
    assert "Qwen2.5-3B-Instruct" in names  # 8GB addition
    assert "Phi-3-mini-4k-instruct" in names  # 8GB addition
    assert len(result["models"]) == 6


def test_recommend_16gb_includes_all_eight_models() -> None:
    result = model_recommender.recommend(total_ram_gb=16.0, recommended_ram_tier="16GB")
    assert len(result["models"]) == 8


def test_recommend_32gb_plus_still_bounded_by_catalog() -> None:
    result = model_recommender.recommend(total_ram_gb=64.0, recommended_ram_tier="32GB+")
    assert len(result["models"]) == 8  # catalog has no 32GB-exclusive entries


def test_recommend_below_minimum_tier_flagged() -> None:
    result = model_recommender.recommend(total_ram_gb=3.0, recommended_ram_tier="4GB")
    assert result["below_minimum_catalog_tier"] is True
    assert len(result["models"]) == 4  # best-effort minimum: still shows the 6GB list


# -- MB-31A: Qwen2.5-0.5B addition -------------------------------------------------------


def test_recommend_6gb_ranks_0_5b_ahead_of_tinyllama() -> None:
    """The explicit MB-31A requirement: when Tamil support is weighted,
    the new 0.5B model (tamil_support='fair') must outrank TinyLlama
    ('limited') in the 6GB-tier ranked list."""
    result = model_recommender.recommend(total_ram_gb=5.69, recommended_ram_tier="6GB")
    names = [m["model_name"] for m in result["models"]]
    assert "Qwen2.5-0.5B-Instruct" in names
    assert names.index("Qwen2.5-0.5B-Instruct") < names.index("TinyLlama-1.1B-Chat")


def test_recommend_0_5b_is_marked_recommended_for_brud_admin() -> None:
    result = model_recommender.recommend(total_ram_gb=5.69, recommended_ram_tier="6GB")
    entry = next(m for m in result["models"] if m["model_name"] == "Qwen2.5-0.5B-Instruct")
    assert entry["recommended_for_brud_admin"]["en"] == "Yes"


@pytest.mark.parametrize(
    ("tier", "ram"), [("6GB", 5.69), ("8GB", 7.5), ("16GB", 16.0), ("32GB+", 64.0)],
)
def test_top_recommendation_unchanged_at_every_tier_after_0_5b_addition(tier: str, ram: float) -> None:
    """MB-31A must not change recommendations for higher RAM tiers --
    the single top pick stays Qwen2.5-1.5B-Instruct everywhere, exactly
    as it was before this pass."""
    result = model_recommender.recommend(total_ram_gb=ram, recommended_ram_tier=tier)
    assert result["top_recommendation"]["model_name"] == "Qwen2.5-1.5B-Instruct"


# -- provider_model_catalog ---------------------------------------------------------------


def test_known_external_providers_matches_mb27_registry() -> None:
    assert set(provider_model_catalog.known_external_providers()) == {"openai", "anthropic", "gemini", "openrouter"}


def test_catalog_entry_for_each_known_provider() -> None:
    for provider_key in provider_model_catalog.known_external_providers():
        entry = provider_model_catalog.catalog_entry(provider_key)
        assert entry is not None
        assert entry["recommended_models"]
        assert entry["context_window"] > 0


def test_catalog_entry_unknown_provider_returns_none() -> None:
    assert provider_model_catalog.catalog_entry("bogus") is None


def test_full_catalog_shape() -> None:
    result = provider_model_catalog.full_catalog()
    assert len(result["providers"]) == 4


# -- health_status_builder -----------------------------------------------------------------


def test_health_unconfigured_when_nothing_set() -> None:
    result = health_status_builder.build(
        hardware={"total_ram_gb": 8.0, "recommended_ram_tier": "8GB", "disk_free_gb": 50.0},
        local_model_configured=False, local_model_available=False,
    )
    assert result["health"] == "unconfigured"


def test_health_degraded_when_configured_but_unavailable() -> None:
    result = health_status_builder.build(
        hardware={"total_ram_gb": 8.0, "recommended_ram_tier": "8GB", "disk_free_gb": 50.0},
        local_model_configured=True, local_model_available=False,
    )
    assert result["health"] == "degraded"


def test_health_healthy_when_available() -> None:
    result = health_status_builder.build(
        hardware={"total_ram_gb": 8.0, "recommended_ram_tier": "8GB", "disk_free_gb": 50.0},
        local_model_configured=True, local_model_available=True,
    )
    assert result["health"] == "healthy"


def test_health_unknown_when_hardware_probe_failed() -> None:
    result = health_status_builder.build(
        hardware={"total_ram_gb": 0, "recommended_ram_tier": "4GB", "disk_free_gb": 0},
        local_model_configured=False, local_model_available=False,
    )
    assert result["health"] == "unknown"


# -- diagnostics_formatter -----------------------------------------------------------------


def test_build_diagnostics_masks_model_path() -> None:
    result = diagnostics_formatter.build_diagnostics(
        hardware={"total_ram_gb": 8.0}, scanned_model_count=2, configured_model_path="/home/user/models/x.gguf",
        local_model_available=True, additional_model_dirs_count=1, configured_external_providers=["openai"],
    )
    assert result["configured_model_path"] == "x.gguf"
    assert "/home/user" not in str(result)


def test_build_diagnostics_none_path() -> None:
    result = diagnostics_formatter.build_diagnostics(
        hardware={"total_ram_gb": 8.0}, scanned_model_count=0, configured_model_path=None,
        local_model_available=False, additional_model_dirs_count=0, configured_external_providers=[],
    )
    assert result["configured_model_path"] is None


# -- setup_guide_builder -------------------------------------------------------------------


def test_build_guide_always_has_at_least_two_steps() -> None:
    guide = setup_guide_builder.build_guide(
        hardware={"total_ram_gb": 6.0, "recommended_ram_tier": "6GB", "cpu_cores": 4},
        scanned_model_count=0, top_recommendation=None, local_model_configured=False,
    )
    assert len(guide["steps"]) >= 2


def test_build_guide_mentions_recommendation_when_present() -> None:
    guide = setup_guide_builder.build_guide(
        hardware={"total_ram_gb": 6.0, "recommended_ram_tier": "6GB", "cpu_cores": 4},
        scanned_model_count=0,
        top_recommendation={"model_name": "Qwen2.5-1.5B-Instruct", "quantization": "Q4_K_M", "expected_ram_usage_gb": 2.5},
        local_model_configured=False,
    )
    assert any("Qwen2.5-1.5B-Instruct" in step["body_en"] for step in guide["steps"])


def test_build_guide_bilingual_fields_present() -> None:
    guide = setup_guide_builder.build_guide(
        hardware={"total_ram_gb": 6.0, "recommended_ram_tier": "6GB", "cpu_cores": 4},
        scanned_model_count=1, top_recommendation=None, local_model_configured=True,
    )
    for step in guide["steps"]:
        assert step["title_en"] and step["title_ta"] and step["body_en"] and step["body_ta"]


# -- bilingual_help_registry ---------------------------------------------------------------


def test_help_for_every_subtab_key_exists() -> None:
    expected_keys = [
        "local_setup.hardware", "local_setup.local_models", "local_setup.recommendations",
        "local_setup.local_configuration", "local_setup.external_providers", "local_setup.diagnostics",
        "local_setup.setup_guide", "local_setup.help",
    ]
    for key in expected_keys:
        entry = bilingual_help_registry.help_for(key)
        assert entry is not None
        assert entry["title_en"] and entry["title_ta"] and entry["body_en"] and entry["body_ta"]


def test_help_for_unknown_key_returns_none() -> None:
    assert bilingual_help_registry.help_for("bogus.key") is None


def test_all_help_returns_full_registry() -> None:
    assert len(bilingual_help_registry.all_help()) == 8
