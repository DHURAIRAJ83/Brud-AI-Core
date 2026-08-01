from __future__ import annotations

from core_model.pipeline_integration.manifest import build_manifest_extension


def _base_kwargs(**overrides):
    base = {
        "build_request_code": "GBR-0001",
        "target_pipeline": "pretraining",
        "dataset_version_public_id": "ver-1",
        "record_type_counts": {"pretrain": 10},
        "language_counts": {"ta": 6, "en": 4},
        "domain_counts": {"general": 10},
        "source_counts": {"src-1": 10},
        "rights_status_counts": {"licensed": 10},
        "verification_status_counts": {"verified": 10},
        "quality_summary": {"average_overall_score": 0.9},
        "duplicate_resolution_summary": {"resolved": 0},
        "conflict_resolution_summary": {"resolved": 0},
        "approval_summary": {"allowed": 10},
        "legacy_record_count": 0,
        "override_count": 0,
        "attribution_entries": [],
        "created_at": "2026-01-01T00:00:00Z",
    }
    base.update(overrides)
    return base


def test_manifest_extension_includes_all_required_fields():
    extension = build_manifest_extension(**_base_kwargs())
    for key in (
        "build_request_code", "target_pipeline", "dataset_version_id", "record_count",
        "record_type_counts", "language_counts", "domain_counts", "source_counts",
        "rights_status_counts", "verification_status_counts", "quality_summary",
        "duplicate_resolution_summary", "conflict_resolution_summary", "approval_summary",
        "legacy_record_count", "override_count", "attribution_entries",
        "source_manifest_checksum", "record_manifest_checksum", "created_at",
    ):
        assert key in extension, key


def test_record_count_is_derived_from_record_type_counts():
    extension = build_manifest_extension(
        **_base_kwargs(record_type_counts={"pretrain": 4, "instruction": 6})
    )
    assert extension["record_count"] == 10


def test_checksum_is_deterministic_for_identical_inputs():
    first = build_manifest_extension(**_base_kwargs())
    second = build_manifest_extension(**_base_kwargs())
    assert first["source_manifest_checksum"] == second["source_manifest_checksum"]
    assert first["record_manifest_checksum"] == second["record_manifest_checksum"]


def test_checksum_changes_when_source_counts_change():
    first = build_manifest_extension(**_base_kwargs())
    second = build_manifest_extension(**_base_kwargs(source_counts={"src-2": 10}))
    assert first["source_manifest_checksum"] != second["source_manifest_checksum"]


def test_record_checksum_unaffected_by_source_counts_change():
    first = build_manifest_extension(**_base_kwargs())
    second = build_manifest_extension(**_base_kwargs(source_counts={"src-2": 10}))
    assert first["record_manifest_checksum"] == second["record_manifest_checksum"]
