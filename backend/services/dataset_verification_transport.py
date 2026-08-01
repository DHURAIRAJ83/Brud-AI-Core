"""Phase 11 safe, SSRF-protected evidence retrieval transport.

Fetches licence/terms/dataset-card evidence only from an explicitly
allowlisted domain (a Phase 9 registered provider domain, or an
admin-registered upstream domain for one specific verification case)
-- never an arbitrary admin-pasted URL. Implements every control from
Step 17: domain allowlist, DNS resolution + private/loopback/
link-local/multicast/reserved/unspecified IP rejection before treating
any URL as safe, HTTPS preference (plain HTTP is allowed but flagged
as a warning, never silently upgraded or rejected outright), a single
validated redirect hop (the redirect *target* is re-validated against
the same allowlist -- never trusted just because the original URL
was), a bounded response size, a MIME allowlist, zero automatic
retries (matches Phase 9/10's own `MAX_RETRIES_PER_PROVIDER=0`
precedent), and a fixed identifying User-Agent. Nothing here ever
executes retrieved content: no `eval`, `exec`, `subprocess`, template
rendering, or archive extraction exists in this module.

Mirrors Phase 9's own connector pattern -- every network call goes
through an injectable transport callable
(`default_evidence_http_transport` is the only implementation that
performs real I/O), and DNS resolution goes through an injectable
resolver callable, so tests never make a real network or DNS call.

HTML is converted to safe text via
`core_model.corpus.text_extraction.extract_html_snapshot_text()`
(reused unchanged, never a second HTML sanitizer). PDF text extraction
mirrors -- does not import, since it is a private method --
`CorpusProcessingService._extract_pdf_embedded`'s exact pattern:
reject encrypted/password-protected PDFs, join each page's
`get_text("text")`. OCR is never attempted automatically here (Step 5's
rule) -- an image-only PDF simply yields empty text plus a warning for
a human to review manually; a separate, explicitly-flagged
`ocr_derived=true` evidence path exists only in the repository's own
`add_evidence_snapshot`, never in this transport.
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import NamedTuple
from urllib.parse import urlparse

from core_model.corpus.text_extraction import content_checksum, extract_html_snapshot_text
from core_model.data_verification import (
    EVIDENCE_CONTENT_TYPES,
    EVIDENCE_FETCH_TIMEOUT_SECONDS,
    MAX_EVIDENCE_CONTENT_CHARS,
    MAX_EVIDENCE_RESPONSE_BYTES,
    MAX_REDIRECTS_PER_EVIDENCE_FETCH,
)

try:
    import fitz
except ImportError:  # pragma: no cover - capability fallback
    fitz = None

USER_AGENT = "BrudAI-DatasetVerification/1 (+evidence-retrieval; read-only)"
_REDIRECT_STATUS_CODES = (301, 302, 303, 307, 308)


class EvidenceRetrievalError(RuntimeError):
    """Raised whenever evidence cannot be safely retrieved -- carries a
    stable `reason` code (never a raw exception message) so callers can
    record an honest `retrieval_status` instead of crashing."""

    def __init__(self, reason: str, message: str = "") -> None:
        super().__init__(message or reason)
        self.reason = reason


class EvidenceHttpResponse(NamedTuple):
    status_code: int
    headers: dict[str, str]
    body: bytes
    reachable: bool = True
    error: str | None = None


EvidenceHttpTransport = Callable[[str, dict[str, str], float], EvidenceHttpResponse]
Resolver = Callable[[str], list[str]]


@dataclass(frozen=True)
class EvidenceFetchResult:
    resolved_url: str
    source_domain: str
    http_status: int
    content_type: str
    content_text: str
    size_bytes: int
    response_headers: dict[str, str]
    content_checksum: str
    warnings: list[str] = field(default_factory=list)


def is_domain_allowed(domain: str, allowed_domains: set[str]) -> bool:
    """Exact-or-subdomain match only -- never a substring/prefix match
    (`"evilhuggingface.co"` must never match `"huggingface.co"`)."""

    domain = domain.lower().rstrip(".")
    for allowed in allowed_domains:
        allowed = allowed.lower().rstrip(".")
        if domain == allowed or domain.endswith(f".{allowed}"):
            return True
    return False


def default_resolver(hostname: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(hostname, None)
    except OSError as exc:
        raise EvidenceRetrievalError("dns_resolution_failed", str(exc)) from exc
    return [info[4][0] for info in infos]


def _reject_unsafe_ip(hostname: str, resolver: Resolver) -> None:
    """The core SSRF defense: resolves `hostname` and rejects it if any
    resolved address is private/loopback/link-local/multicast/
    reserved/unspecified, run before every connection this module
    makes -- including the redirect target."""

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
            raise EvidenceRetrievalError(
                "private_or_reserved_ip_rejected", f"{hostname} resolved to {address}"
            )


def _validate_url(url: str, allowed_domains: set[str], resolver: Resolver) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("https", "http"):
        raise EvidenceRetrievalError("unsupported_url_scheme", parsed.scheme or "missing")
    if not parsed.hostname:
        raise EvidenceRetrievalError("missing_hostname", url)
    if not is_domain_allowed(parsed.hostname, allowed_domains):
        raise EvidenceRetrievalError("domain_not_allowlisted", parsed.hostname)
    _reject_unsafe_ip(parsed.hostname, resolver)
    return parsed.hostname


def default_evidence_http_transport(
    url: str, headers: dict[str, str], timeout_seconds: float
) -> EvidenceHttpResponse:
    """The only real-network implementation of `EvidenceHttpTransport`
    in this codebase. GET-only, bounded timeout, redirects never
    auto-followed (the caller re-validates and follows manually, at
    most once)."""

    import httpx

    try:
        response = httpx.get(
            url, headers=headers, timeout=timeout_seconds, follow_redirects=False
        )
        return EvidenceHttpResponse(
            status_code=response.status_code,
            headers=dict(response.headers),
            body=response.content[: MAX_EVIDENCE_RESPONSE_BYTES + 1],
        )
    except httpx.HTTPError as exc:
        return EvidenceHttpResponse(
            status_code=0, headers={}, body=b"", reachable=False, error=type(exc).__name__
        )


def fetch_evidence(
    url: str,
    *,
    allowed_domains: set[str],
    transport: EvidenceHttpTransport = default_evidence_http_transport,
    resolver: Resolver = default_resolver,
    timeout_seconds: float = EVIDENCE_FETCH_TIMEOUT_SECONDS,
) -> EvidenceFetchResult:
    """Validates the *requested* URL against `allowed_domains` (plus a
    live DNS/IP safety check) before connecting, follows at most one
    redirect and re-validates the *final* URL the same way, and never
    retries on failure -- one honest attempt only
    (`MAX_REDIRECTS_PER_EVIDENCE_FETCH`/zero built-in retry)."""

    warnings: list[str] = []
    hostname = _validate_url(url, allowed_domains, resolver)
    if urlparse(url).scheme != "https":
        warnings.append("fetched_over_plain_http")

    request_headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    response = transport(url, request_headers, timeout_seconds)
    if not response.reachable:
        raise EvidenceRetrievalError("transport_error", response.error or "unreachable")

    current_url = url
    redirects_followed = 0
    while response.status_code in _REDIRECT_STATUS_CODES:
        location = response.headers.get("location") or response.headers.get("Location")
        if not location:
            raise EvidenceRetrievalError("redirect_missing_location", current_url)
        if redirects_followed >= MAX_REDIRECTS_PER_EVIDENCE_FETCH:
            raise EvidenceRetrievalError("too_many_redirects", current_url)
        hostname = _validate_url(location, allowed_domains, resolver)
        current_url = location
        redirects_followed += 1
        warnings.append("followed_one_validated_redirect")
        response = transport(current_url, request_headers, timeout_seconds)
        if not response.reachable:
            raise EvidenceRetrievalError("transport_error", response.error or "unreachable")

    content_type_header = response.headers.get("content-type", "") or response.headers.get(
        "Content-Type", ""
    )
    content_type = content_type_header.split(";")[0].strip().lower()
    if content_type not in EVIDENCE_CONTENT_TYPES:
        raise EvidenceRetrievalError("unsupported_content_type", content_type or "unknown")

    raw_bytes = response.body
    if len(raw_bytes) > MAX_EVIDENCE_RESPONSE_BYTES:
        raw_bytes = raw_bytes[:MAX_EVIDENCE_RESPONSE_BYTES]
        warnings.append("response_truncated_to_size_limit")

    text = _extract_text(content_type, raw_bytes, warnings)
    if len(text) > MAX_EVIDENCE_CONTENT_CHARS:
        text = text[:MAX_EVIDENCE_CONTENT_CHARS]
        warnings.append("content_truncated_to_char_limit")
    checksum = content_checksum(text)

    kept_header_names = {"content-type", "content-length", "last-modified", "etag"}
    kept_headers = {
        key: value for key, value in response.headers.items() if key.lower() in kept_header_names
    }
    return EvidenceFetchResult(
        resolved_url=current_url,
        source_domain=hostname,
        http_status=response.status_code,
        content_type=content_type,
        content_text=text,
        size_bytes=len(raw_bytes),
        response_headers=kept_headers,
        content_checksum=checksum,
        warnings=warnings,
    )


def _extract_text(content_type: str, raw_bytes: bytes, warnings: list[str]) -> str:
    if content_type in ("text/plain", "text/markdown", "application/json"):
        return raw_bytes.decode("utf-8", errors="replace")
    if content_type == "text/html":
        result = extract_html_snapshot_text(raw_bytes)
        warnings.extend(result.get("issues", []))
        return result["text"]
    if content_type == "application/pdf":
        return _extract_pdf_embedded_text(raw_bytes, warnings)
    raise EvidenceRetrievalError("unsupported_content_type", content_type)


def _extract_pdf_embedded_text(raw_bytes: bytes, warnings: list[str]) -> str:
    if fitz is None:
        raise EvidenceRetrievalError("pdf_extraction_unavailable")
    with fitz.open(stream=raw_bytes, filetype="pdf") as pdf:
        if pdf.needs_pass or pdf.is_encrypted:
            raise EvidenceRetrievalError("encrypted_pdf_rejected")
        pages = [page.get_text("text") for page in pdf]
    text = "\n\n".join(page for page in pages if page.strip())
    if not text:
        warnings.append("no_embedded_text_found_in_pdf")
    return text
