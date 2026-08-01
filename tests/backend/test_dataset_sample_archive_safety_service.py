import tarfile
import zipfile
from pathlib import Path

import pytest

from backend.services.dataset_sample_archive_safety_service import (
    ArchiveSafetyError,
    ExternalDatasetArchiveSafetyService,
    detect_archive_format,
)


@pytest.fixture
def service() -> ExternalDatasetArchiveSafetyService:
    return ExternalDatasetArchiveSafetyService()


def _make_zip(path: Path, entries: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return path


def _make_tar(path: Path, entries: dict[str, bytes]) -> Path:
    import io

    with tarfile.open(path, "w") as archive:
        for name, content in entries.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
    return path


def test_detect_archive_format() -> None:
    assert detect_archive_format("bundle.zip") == "zip"
    assert detect_archive_format("bundle.tar") == "tar"
    assert detect_archive_format("bundle.tar.gz") == "tar.gz"
    assert detect_archive_format("bundle.tgz") == "tar.gz"
    assert detect_archive_format("bundle.rar") is None


def test_extract_zip_extracts_safe_members(tmp_path: Path, service) -> None:
    archive = _make_zip(tmp_path / "safe.zip", {"a.txt": b"hello", "sub/b.txt": b"world"})
    destination = tmp_path / "derived"
    result = service.extract(archive, destination, archive_format="zip")
    assert result.aborted is False
    assert {member.member_path for member in result.extracted} == {"a.txt", "sub/b.txt"}
    assert (destination / "a.txt").read_bytes() == b"hello"
    assert (destination / "sub" / "b.txt").read_bytes() == b"world"


def test_extract_tar_extracts_safe_members(tmp_path: Path, service) -> None:
    archive = _make_tar(tmp_path / "safe.tar", {"a.txt": b"hello"})
    destination = tmp_path / "derived"
    result = service.extract(archive, destination, archive_format="tar")
    assert result.aborted is False
    assert len(result.extracted) == 1
    assert (destination / "a.txt").read_bytes() == b"hello"


def test_zip_path_traversal_is_rejected(tmp_path: Path, service) -> None:
    archive = _make_zip(tmp_path / "evil.zip", {"../../etc/passwd": b"pwned"})
    destination = tmp_path / "derived"
    result = service.extract(archive, destination, archive_format="zip")
    assert result.aborted is False
    assert result.extracted == []
    assert result.rejected[0].reason == "path_traversal"
    assert not (tmp_path / "etc").exists()


def test_zip_absolute_path_is_rejected(tmp_path: Path, service) -> None:
    archive = _make_zip(tmp_path / "abs.zip", {"/etc/passwd": b"pwned"})
    destination = tmp_path / "derived"
    result = service.extract(archive, destination, archive_format="zip")
    assert result.rejected[0].reason == "absolute_path"


def test_tar_symlink_is_rejected(tmp_path: Path, service) -> None:
    archive_path = tmp_path / "symlink.tar"
    with tarfile.open(archive_path, "w") as archive:
        info = tarfile.TarInfo(name="link")
        info.type = tarfile.SYMTYPE
        info.linkname = "/etc/passwd"
        archive.addfile(info)
    destination = tmp_path / "derived"
    result = service.extract(archive_path, destination, archive_format="tar")
    assert result.rejected[0].reason == "symlink"


def test_tar_hardlink_is_rejected(tmp_path: Path, service) -> None:
    archive_path = tmp_path / "hardlink.tar"
    with tarfile.open(archive_path, "w") as archive:
        real = tarfile.TarInfo(name="real.txt")
        real.size = 5
        import io

        archive.addfile(real, io.BytesIO(b"hello"))
        link = tarfile.TarInfo(name="link.txt")
        link.type = tarfile.LNKTYPE
        link.linkname = "real.txt"
        archive.addfile(link)
    destination = tmp_path / "derived"
    result = service.extract(archive_path, destination, archive_format="tar")
    rejected_reasons = {rejected.member_path: rejected.reason for rejected in result.rejected}
    assert rejected_reasons.get("link.txt") == "hard_link"


def test_tar_device_file_is_rejected(tmp_path: Path, service) -> None:
    archive_path = tmp_path / "device.tar"
    with tarfile.open(archive_path, "w") as archive:
        info = tarfile.TarInfo(name="dev0")
        info.type = tarfile.CHRTYPE
        info.devmajor = 1
        info.devminor = 1
        archive.addfile(info)
    destination = tmp_path / "derived"
    result = service.extract(archive_path, destination, archive_format="tar")
    assert result.rejected[0].reason == "device_file"


def test_zip_encrypted_entry_is_rejected(tmp_path: Path, service) -> None:
    archive_path = tmp_path / "encrypted.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("secret.txt", b"shh")
        # Flip the encryption bit on the entry we just wrote.
        for info in archive.infolist():
            info.flag_bits |= 0x1
    destination = tmp_path / "derived"
    result = service.extract(archive_path, destination, archive_format="zip")
    assert result.rejected[0].reason == "encrypted_entry"


def test_duplicate_path_is_rejected(tmp_path: Path, service) -> None:
    archive_path = tmp_path / "dupe.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("a.txt", b"first")
        archive.writestr("a.txt", b"second")
    destination = tmp_path / "derived"
    result = service.extract(archive_path, destination, archive_format="zip")
    assert len(result.extracted) == 1
    assert result.rejected[0].reason == "duplicate_path"


def test_member_count_exceeded_aborts_extraction(tmp_path: Path, service) -> None:
    entries = {f"file{i}.txt": b"x" for i in range(10)}
    archive = _make_zip(tmp_path / "many.zip", entries)
    destination = tmp_path / "derived"
    result = service.extract(archive, destination, archive_format="zip", max_member_count=5)
    assert result.aborted is True
    assert result.abort_reason == "member_count_exceeded"
    assert not destination.exists()


def test_expanded_bytes_exceeded_aborts_extraction(tmp_path: Path, service) -> None:
    archive = _make_zip(tmp_path / "big.zip", {"a.txt": b"x" * 10_000})
    destination = tmp_path / "derived"
    result = service.extract(archive, destination, archive_format="zip", max_expanded_bytes=100)
    assert result.aborted is True
    assert result.abort_reason == "expanded_bytes_exceeded"
    assert not destination.exists()


def test_directory_depth_exceeded_is_rejected(tmp_path: Path, service) -> None:
    deep_path = "/".join(["dir"] * 20) + "/leaf.txt"
    archive = _make_zip(tmp_path / "deep.zip", {deep_path: b"x"})
    destination = tmp_path / "derived"
    result = service.extract(archive, destination, archive_format="zip", max_directory_depth=5)
    assert result.rejected[0].reason == "depth_exceeded"


def test_nested_archive_member_is_never_auto_extracted(tmp_path: Path, service) -> None:
    archive = _make_zip(tmp_path / "outer.zip", {"inner.zip": b"PK\x03\x04fakezipbytes"})
    destination = tmp_path / "derived"
    result = service.extract(archive, destination, archive_format="zip")
    assert result.extracted == []
    assert result.rejected[0].reason == "nested_archive_depth_exceeded"


def test_unsupported_archive_format_raises(tmp_path: Path) -> None:
    service = ExternalDatasetArchiveSafetyService()
    with pytest.raises(ArchiveSafetyError):
        service.extract(
            tmp_path / "nonexistent", tmp_path / "derived", archive_format="rar"
        )
