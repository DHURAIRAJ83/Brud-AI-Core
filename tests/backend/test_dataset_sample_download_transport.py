import hashlib
from pathlib import Path

import pytest

from backend.services.dataset_sample_download_transport import (
    SampleDownloadError,
    StreamResponse,
    stream_download_to_file,
)


def _resolver_public(_hostname: str) -> list[str]:
    return ["93.184.216.34"]


def _resolver_private(_hostname: str) -> list[str]:
    return ["127.0.0.1"]


def _fake_transport(chunks: list[bytes], *, status_code: int = 200, headers: dict | None = None):
    calls = {"count": 0}

    def transport(url: str, headers_sent: dict, timeout_seconds: float) -> StreamResponse:
        calls["count"] += 1
        return StreamResponse(
            status_code=status_code, headers=headers or {}, chunk_iterator=iter(chunks)
        )

    transport.calls = calls
    return transport


def test_successful_bounded_download_writes_file_and_checksum(tmp_path: Path) -> None:
    content = b"hello quarantine world"
    transport = _fake_transport([content[:5], content[5:]])
    destination = tmp_path / "out.txt"

    result = stream_download_to_file(
        "https://example.org/data.txt",
        destination,
        allowed_domains={"example.org"},
        max_bytes=1_000,
        transport=transport,
        resolver=_resolver_public,
    )

    assert destination.read_bytes() == content
    assert result.bytes_downloaded == len(content)
    assert result.checksum == hashlib.sha256(content).hexdigest()
    assert result.source_domain == "example.org"
    assert "downloaded_over_plain_http" not in result.warnings


def test_byte_limit_exceeded_deletes_partial_file(tmp_path: Path) -> None:
    transport = _fake_transport([b"a" * 500, b"b" * 500, b"c" * 500])
    destination = tmp_path / "out.bin"

    with pytest.raises(SampleDownloadError) as exc_info:
        stream_download_to_file(
            "https://example.org/big.bin",
            destination,
            allowed_domains={"example.org"},
            max_bytes=800,
            transport=transport,
            resolver=_resolver_public,
        )
    assert exc_info.value.reason == "byte_limit_exceeded"
    assert not destination.exists()
    assert not any(tmp_path.iterdir())


def test_content_length_precheck_aborts_before_streaming(tmp_path: Path) -> None:
    transport = _fake_transport(
        [b"x" * 2000], headers={"content-length": "2000"}
    )
    destination = tmp_path / "out.bin"

    with pytest.raises(SampleDownloadError) as exc_info:
        stream_download_to_file(
            "https://example.org/oversized.bin",
            destination,
            allowed_domains={"example.org"},
            max_bytes=1000,
            transport=transport,
            resolver=_resolver_public,
        )
    assert exc_info.value.reason == "content_length_exceeds_byte_limit"
    assert not destination.exists()


def test_domain_not_allowlisted_rejected_before_any_transport_call(tmp_path: Path) -> None:
    transport = _fake_transport([b"data"])
    destination = tmp_path / "out.txt"

    with pytest.raises(SampleDownloadError) as exc_info:
        stream_download_to_file(
            "https://evil.example/data.txt",
            destination,
            allowed_domains={"example.org"},
            max_bytes=1000,
            transport=transport,
            resolver=_resolver_public,
        )
    assert exc_info.value.reason == "domain_not_allowlisted"
    assert transport.calls["count"] == 0


def test_private_ip_rejected(tmp_path: Path) -> None:
    transport = _fake_transport([b"data"])
    destination = tmp_path / "out.txt"

    with pytest.raises(SampleDownloadError) as exc_info:
        stream_download_to_file(
            "https://example.org/data.txt",
            destination,
            allowed_domains={"example.org"},
            max_bytes=1000,
            transport=transport,
            resolver=_resolver_private,
        )
    assert exc_info.value.reason == "private_or_reserved_ip_rejected"


def test_credentials_in_url_rejected(tmp_path: Path) -> None:
    transport = _fake_transport([b"data"])
    destination = tmp_path / "out.txt"

    with pytest.raises(SampleDownloadError) as exc_info:
        stream_download_to_file(
            "https://user:pass@example.org/data.txt",
            destination,
            allowed_domains={"example.org"},
            max_bytes=1000,
            transport=transport,
            resolver=_resolver_public,
        )
    assert exc_info.value.reason == "credentials_in_url_rejected"


def test_destination_already_exists_raises(tmp_path: Path) -> None:
    destination = tmp_path / "out.txt"
    destination.write_text("existing")
    transport = _fake_transport([b"data"])

    with pytest.raises(SampleDownloadError) as exc_info:
        stream_download_to_file(
            "https://example.org/data.txt",
            destination,
            allowed_domains={"example.org"},
            max_bytes=1000,
            transport=transport,
            resolver=_resolver_public,
        )
    assert exc_info.value.reason == "destination_already_exists"


def test_unreachable_transport_raises_transport_error(tmp_path: Path) -> None:
    def transport(url: str, headers: dict, timeout_seconds: float) -> StreamResponse:
        return StreamResponse(status_code=0, headers={}, reachable=False, error="ConnectError")

    destination = tmp_path / "out.txt"
    with pytest.raises(SampleDownloadError) as exc_info:
        stream_download_to_file(
            "https://example.org/data.txt",
            destination,
            allowed_domains={"example.org"},
            max_bytes=1000,
            transport=transport,
            resolver=_resolver_public,
        )
    assert exc_info.value.reason == "transport_error"


def test_plain_http_succeeds_but_adds_warning(tmp_path: Path) -> None:
    transport = _fake_transport([b"data"])
    destination = tmp_path / "out.txt"

    result = stream_download_to_file(
        "http://example.org/data.txt",
        destination,
        allowed_domains={"example.org"},
        max_bytes=1000,
        transport=transport,
        resolver=_resolver_public,
    )
    assert "downloaded_over_plain_http" in result.warnings


def test_redirect_is_followed_once_and_revalidated(tmp_path: Path) -> None:
    responses = [
        StreamResponse(
            status_code=302, headers={"location": "https://example.org/final.txt"},
            chunk_iterator=iter([]),
        ),
        StreamResponse(status_code=200, headers={}, chunk_iterator=iter([b"final content"])),
    ]

    def transport(url: str, headers: dict, timeout_seconds: float) -> StreamResponse:
        return responses.pop(0)

    destination = tmp_path / "out.txt"
    result = stream_download_to_file(
        "https://example.org/start.txt",
        destination,
        allowed_domains={"example.org"},
        max_bytes=1000,
        transport=transport,
        resolver=_resolver_public,
    )
    assert destination.read_bytes() == b"final content"
    assert "followed_one_validated_redirect" in result.warnings


def test_too_many_redirects_raises(tmp_path: Path) -> None:
    def transport(url: str, headers: dict, timeout_seconds: float) -> StreamResponse:
        return StreamResponse(
            status_code=302, headers={"location": "https://example.org/next.txt"},
            chunk_iterator=iter([]),
        )

    destination = tmp_path / "out.txt"
    with pytest.raises(SampleDownloadError) as exc_info:
        stream_download_to_file(
            "https://example.org/start.txt",
            destination,
            allowed_domains={"example.org"},
            max_bytes=1000,
            transport=transport,
            resolver=_resolver_public,
        )
    assert exc_info.value.reason == "too_many_redirects"


def test_redirect_target_must_also_be_allowlisted(tmp_path: Path) -> None:
    def transport(url: str, headers: dict, timeout_seconds: float) -> StreamResponse:
        if url == "https://example.org/start.txt":
            return StreamResponse(
                status_code=302, headers={"location": "https://evil.example/steal.txt"},
                chunk_iterator=iter([]),
            )
        raise AssertionError("should never reach the redirect target")

    destination = tmp_path / "out.txt"
    with pytest.raises(SampleDownloadError) as exc_info:
        stream_download_to_file(
            "https://example.org/start.txt",
            destination,
            allowed_domains={"example.org"},
            max_bytes=1000,
            transport=transport,
            resolver=_resolver_public,
        )
    assert exc_info.value.reason == "domain_not_allowlisted"
