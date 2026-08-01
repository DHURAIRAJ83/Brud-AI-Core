"""Phase 12 Step 8 safe, SSRF-protected, byte-capped streaming download
transport for approved sample files.

Extends Phase 11's domain-allowlist/SSRF pattern
(`dataset_verification_transport.is_domain_allowed`/`default_resolver`,
reused unchanged) with genuine chunked streaming, since sample
downloads can legitimately be much larger than a 2MB evidence fetch:
the byte cap is enforced *during* streaming (the connection is aborted
the instant the running total exceeds the approved limit, never only
checked after the fact), the destination file is written to a
temporary name inside the caller-supplied quarantine directory and
atomically renamed into place only once the stream completes cleanly,
and the checksum is computed incrementally per chunk rather than over
a fully-buffered body. Never resumes from an unverified partial file,
never sends credentials in the URL, and follows at most one
re-validated redirect hop, mirroring Phase 11 exactly.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from backend.services.dataset_verification_transport import default_resolver, is_domain_allowed
from core_model.sample_import import DOWNLOAD_CHUNK_BYTES, DOWNLOAD_TIMEOUT_SECONDS

USER_AGENT = "BrudAI-SampleImport/1 (+bounded-sample-download; read-only)"
_REDIRECT_STATUS_CODES = (301, 302, 303, 307, 308)
MAX_DOWNLOAD_REDIRECTS = 1


class SampleDownloadError(RuntimeError):
    """Carries a stable `reason` code (never a raw exception message) so
    callers can record an honest, auditable failure reason instead of
    crashing with an opaque traceback."""

    def __init__(self, reason: str, message: str = "") -> None:
        super().__init__(message or reason)
        self.reason = reason


@dataclass
class StreamResponse:
    status_code: int
    headers: dict[str, str]
    chunk_iterator: Iterator[bytes] = field(default_factory=lambda: iter(()))
    reachable: bool = True
    error: str | None = None
    close: Callable[[], None] = field(default=lambda: None)


StreamTransport = Callable[[str, dict[str, str], float], StreamResponse]
Resolver = Callable[[str], list[str]]


@dataclass(frozen=True)
class DownloadResult:
    resolved_url: str
    source_domain: str
    http_status: int
    bytes_downloaded: int
    checksum: str
    warnings: list[str] = field(default_factory=list)


def _reject_unsafe_ip(hostname: str, resolver: Resolver) -> None:
    import ipaddress

    for address in resolver(hostname):
        parsed = ipaddress.ip_address(address)
        if (
            parsed.is_private
            or parsed.is_loopback
            or parsed.is_link_local
            or parsed.is_multicast
            or parsed.is_reserved
            or parsed.is_unspecified
        ):
            raise SampleDownloadError(
                "private_or_reserved_ip_rejected", f"{hostname} resolved to {address}"
            )


def _validate_url(url: str, allowed_domains: set[str], resolver: Resolver) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("https", "http"):
        raise SampleDownloadError("unsupported_url_scheme", parsed.scheme or "missing")
    if parsed.username or parsed.password:
        raise SampleDownloadError("credentials_in_url_rejected", url)
    if not parsed.hostname:
        raise SampleDownloadError("missing_hostname", url)
    if not is_domain_allowed(parsed.hostname, allowed_domains):
        raise SampleDownloadError("domain_not_allowlisted", parsed.hostname)
    _reject_unsafe_ip(parsed.hostname, resolver)
    return parsed.hostname


def default_stream_http_transport(
    url: str, headers: dict[str, str], timeout_seconds: float
) -> StreamResponse:
    """The only real-network implementation of `StreamTransport` in
    this codebase. GET-only, redirects never auto-followed."""

    import httpx

    try:
        client = httpx.Client(timeout=timeout_seconds)
        request = client.build_request("GET", url, headers=headers)
        response = client.send(request, stream=True, follow_redirects=False)
    except httpx.HTTPError as exc:
        return StreamResponse(status_code=0, headers={}, reachable=False, error=type(exc).__name__)

    def _close() -> None:
        response.close()
        client.close()

    return StreamResponse(
        status_code=response.status_code,
        headers=dict(response.headers),
        chunk_iterator=response.iter_bytes(DOWNLOAD_CHUNK_BYTES),
        close=_close,
    )


def stream_download_to_file(
    url: str,
    destination: Path,
    *,
    allowed_domains: set[str],
    max_bytes: int,
    transport: StreamTransport = default_stream_http_transport,
    resolver: Resolver = default_resolver,
    timeout_seconds: float = DOWNLOAD_TIMEOUT_SECONDS,
) -> DownloadResult:
    """Streams `url` into `destination` (which must not already exist),
    enforcing `max_bytes` chunk-by-chunk. On any failure -- byte-limit
    exceeded, unreachable, unsafe redirect target -- the partial
    temporary file is deleted and a `SampleDownloadError` is raised;
    `destination` itself is only ever created via an atomic rename
    after the stream finishes cleanly, so a caller never observes a
    half-written file at the final path."""

    if destination.exists():
        raise SampleDownloadError("destination_already_exists", str(destination))

    warnings: list[str] = []
    hostname = _validate_url(url, allowed_domains, resolver)
    if urlparse(url).scheme != "https":
        warnings.append("downloaded_over_plain_http")

    request_headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    response = transport(url, request_headers, timeout_seconds)
    if not response.reachable:
        raise SampleDownloadError("transport_error", response.error or "unreachable")

    current_url = url
    redirects_followed = 0
    while response.status_code in _REDIRECT_STATUS_CODES:
        response.close()
        location = response.headers.get("location") or response.headers.get("Location")
        if not location:
            raise SampleDownloadError("redirect_missing_location", current_url)
        if redirects_followed >= MAX_DOWNLOAD_REDIRECTS:
            raise SampleDownloadError("too_many_redirects", current_url)
        hostname = _validate_url(location, allowed_domains, resolver)
        current_url = location
        redirects_followed += 1
        warnings.append("followed_one_validated_redirect")
        response = transport(current_url, request_headers, timeout_seconds)
        if not response.reachable:
            raise SampleDownloadError("transport_error", response.error or "unreachable")

    content_length_header = response.headers.get("content-length") or response.headers.get(
        "Content-Length"
    )
    if content_length_header is not None:
        try:
            if int(content_length_header) > max_bytes:
                response.close()
                raise SampleDownloadError(
                    "content_length_exceeds_byte_limit", content_length_header
                )
        except ValueError:
            pass

    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.parent / f".{destination.name}.{uuid4().hex}.part"
    digest = hashlib.sha256()
    total = 0
    try:
        with temp_path.open("xb") as handle:
            os.chmod(temp_path, 0o600)
            for chunk in response.chunk_iterator:
                total += len(chunk)
                if total > max_bytes:
                    raise SampleDownloadError("byte_limit_exceeded", str(max_bytes))
                digest.update(chunk)
                handle.write(chunk)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    finally:
        response.close()

    os.replace(temp_path, destination)
    os.chmod(destination, 0o600)
    return DownloadResult(
        resolved_url=current_url,
        source_domain=hostname,
        http_status=response.status_code,
        bytes_downloaded=total,
        checksum=digest.hexdigest(),
        warnings=warnings,
    )
