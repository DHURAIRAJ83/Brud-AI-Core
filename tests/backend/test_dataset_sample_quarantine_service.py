from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.services.dataset_sample_quarantine_service import (
    ExternalDatasetQuarantineService,
    QuarantineStorageError,
    safe_filename,
)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        database_path=tmp_path / "db.sqlite3",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        quarantine_dir=tmp_path / "quarantine",
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
        log_level="CRITICAL",
    )


@pytest.fixture
def service(settings: Settings) -> ExternalDatasetQuarantineService:
    return ExternalDatasetQuarantineService(settings)


def test_safe_filename_strips_path_and_unsafe_characters() -> None:
    assert safe_filename("../../etc/passwd") == "passwd"
    assert safe_filename("my file (1).csv") == "my_file__1_.csv"
    assert safe_filename("...hidden") == "hidden"
    assert safe_filename("") == "file"


def test_ensure_layout_creates_expected_directories_and_manifest(
    service: ExternalDatasetQuarantineService,
) -> None:
    root = service.ensure_layout("sample-1")
    assert root.is_dir()
    assert service.original_dir("sample-1").is_dir()
    assert service.derived_dir("sample-1").is_dir()
    assert service.reports_dir("sample-1").is_dir()
    assert service.manifest_path("sample-1").exists()
    manifest = service.read_manifest("sample-1")
    assert manifest == {"files": []}


def test_directories_are_created_with_owner_only_permissions(
    service: ExternalDatasetQuarantineService,
) -> None:
    service.ensure_layout("sample-1")
    mode = service.original_dir("sample-1").stat().st_mode & 0o777
    assert mode == 0o700


def test_add_manifest_entry_appends_and_persists(
    service: ExternalDatasetQuarantineService,
) -> None:
    service.ensure_layout("sample-1")
    service.add_manifest_entry("sample-1", {"filename": "a.txt", "checksum": "abc"})
    service.add_manifest_entry("sample-1", {"filename": "b.txt", "checksum": "def"})
    manifest = service.read_manifest("sample-1")
    assert len(manifest["files"]) == 2
    assert manifest["files"][0]["filename"] == "a.txt"


def test_original_file_path_rejects_path_traversal(
    service: ExternalDatasetQuarantineService,
) -> None:
    service.ensure_layout("sample-1")
    path = service.original_file_path("sample-1", "../../etc/passwd")
    # safe_filename() strips the traversal components before the path
    # is ever resolved, so the resulting path always stays inside the
    # per-import original/ directory.
    assert path.parent == service.original_dir("sample-1")
    assert path.name == "passwd"


def test_get_safe_text_preview_reads_bounded_text(
    service: ExternalDatasetQuarantineService,
) -> None:
    service.ensure_layout("sample-1")
    target = service.original_file_path("sample-1", "note.txt")
    target.write_text("hello world", encoding="utf-8")
    preview = service.get_safe_text_preview("sample-1", "note.txt")
    assert preview == "hello world"


def test_get_safe_text_preview_raises_for_missing_file(
    service: ExternalDatasetQuarantineService,
) -> None:
    service.ensure_layout("sample-1")
    with pytest.raises(QuarantineStorageError):
        service.get_safe_text_preview("sample-1", "missing.txt")


def test_bytes_used_sums_file_sizes_across_subdirectories_including_manifest(
    service: ExternalDatasetQuarantineService,
) -> None:
    service.ensure_layout("sample-1")
    before = service.bytes_used("sample-1")  # the manifest.json itself has nonzero size
    service.original_file_path("sample-1", "a.txt").write_bytes(b"x" * 100)
    service.derived_file_path("sample-1", "a.norm.txt").write_bytes(b"y" * 50)
    assert service.bytes_used("sample-1") == before + 150


def test_original_bytes_used_excludes_manifest_and_derived(
    service: ExternalDatasetQuarantineService,
) -> None:
    service.ensure_layout("sample-1")
    service.original_file_path("sample-1", "a.txt").write_bytes(b"x" * 100)
    service.derived_file_path("sample-1", "a.norm.txt").write_bytes(b"y" * 50)
    assert service.original_bytes_used("sample-1") == 100


def test_remaining_quota_bytes_never_goes_negative(
    service: ExternalDatasetQuarantineService,
) -> None:
    service.ensure_layout("sample-1")
    service.original_file_path("sample-1", "a.txt").write_bytes(b"x" * 200)
    assert service.remaining_quota_bytes("sample-1", 100) == 0
    assert service.remaining_quota_bytes("sample-1", 500) == 300


def test_delete_payload_removes_original_and_derived_but_keeps_manifest_and_reports(
    service: ExternalDatasetQuarantineService,
) -> None:
    service.ensure_layout("sample-1")
    service.original_file_path("sample-1", "a.txt").write_bytes(b"x")
    service.derived_file_path("sample-1", "a.norm.txt").write_bytes(b"y")
    (service.reports_dir("sample-1") / "report.json").write_text("{}", encoding="utf-8")

    service.delete_payload("sample-1")

    assert not service.original_dir("sample-1").exists()
    assert not service.derived_dir("sample-1").exists()
    assert service.manifest_path("sample-1").exists()
    assert (service.reports_dir("sample-1") / "report.json").exists()


def test_two_imports_get_fully_isolated_directories(
    service: ExternalDatasetQuarantineService,
) -> None:
    service.ensure_layout("sample-1")
    service.ensure_layout("sample-2")
    service.original_file_path("sample-1", "a.txt").write_bytes(b"only in sample 1")
    assert not service.original_file_path("sample-2", "a.txt").exists()
