"""Phase 20 Steps 6-8 -- SSRF-safe, policy-driven Web page fetcher +
content extraction.

Reuses the exact SSRF-defense primitives already proven in
`dataset_verification_transport.py` (`is_domain_allowed`,
`default_resolver`, `default_evidence_http_transport`,
`EvidenceHttpResponse`/`EvidenceHttpTransport`/`Resolver`,
`EVIDENCE_CONTENT_TYPES`) rather than re-implementing DNS/IP safety
checks a third time in this codebase. The fetch *loop* itself is
reimplemented here (not just called via `fetch_evidence`), because
Step 8 needs title/heading/date metadata pulled from the raw HTML
*before* it is stripped to plain text -- `fetch_evidence` only ever
returns the already-stripped text, which is too late for that.

Blocks (Step 6): non-HTTP/HTTPS schemes (`file://`, `ftp://`,
`gopher://`, `data:`, `javascript:`), credential-bearing URLs
(`user:pass@host`), localhost/loopback/private/link-local/multicast/
reserved/unspecified IPv4+IPv6 (`_reject_unsafe_ip`, reused unchanged,
applied to the requested URL *and* every redirect hop), known
cloud-metadata hostnames, and a best-effort IDN-confusable check.
Every redirect target is re-validated identically to the original URL
-- never trusted merely because the initial URL passed. This module
performs at most one re-validated redirect hop and never retries.

Known, inherited limitation (shared with the Phase 11/12 modules this
reuses): the DNS-resolution safety check and the actual TCP connect
are two separate steps, so a adversary controlling DNS with a very
low TTL could in principle swap the resolved address between them
("DNS rebinding"). No module in this codebase closes that gap today;
Phase 20 does not attempt a first-of-its-kind fix here either --
documented, not silently assumed away.
"""

from __future__ import annotations

import hashlib
import ipaddress
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

from backend.services.dataset_verification_transport import (
    EvidenceHttpResponse,
    Resolver,
    default_evidence_http_transport,
    default_resolver,
    is_domain_allowed,
)
from core_model.corpus.text_extraction import extract_html_snapshot_text
from core_model.data_verification import EVIDENCE_CONTENT_TYPES

USER_AGENT = "BrudAI-TrustedWebFetcher/1 (+bounded-fetch; read-only; no-js; no-forms)"
_REDIRECT_STATUS_CODES = (301, 302, 303, 307, 308)
MAX_FETCH_REDIRECTS = 1

_BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "metadata.google.internal",
        "metadata",
    }
)
_METADATA_IPS = frozenset({"169.254.169.254", "fd00:ec2::254"})

# Best-effort IDN-confusable heuristic: a hostname mixing Latin ASCII
# letters with non-ASCII (often-confusable) letters in the same label
# is flagged, never silently trusted -- not a full Unicode-confusables
# database, which this codebase has no dependency for.
_MIXED_SCRIPT_LABEL_RE = re.compile(r"(?=.*[a-zA-Z])(?=.*[^\x00-\x7F])")


class FetchBlockedError(RuntimeError):
    """Carries a stable `reason` code (never a raw exception message)."""

    def __init__(self, reason: str, message: str = "") -> None:
        super().__init__(message or reason)
        self.reason = reason


@dataclass(frozen=True)
class FetchedPage:
    resolved_url: str
    source_domain: str
    http_status: int
    content_type: str
    raw_bytes: bytes
    title: str | None
    main_text: str
    headings: tuple[str, ...]
    published_at: str | None
    updated_at: str | None
    canonical_url: str | None
    language: str | None
    content_checksum: str
    warnings: list[str] = field(default_factory=list)


def _reject_unsafe_ip(hostname: str, resolver: Resolver) -> None:
    if hostname in _METADATA_IPS:
        raise FetchBlockedError("metadata_endpoint_rejected", hostname)
    for address in resolver(hostname):
        if address in _METADATA_IPS:
            raise FetchBlockedError("metadata_endpoint_rejected", f"{hostname} -> {address}")
        parsed = ipaddress.ip_address(address)
        if (
            parsed.is_private
            or parsed.is_loopback
            or parsed.is_link_local
            or parsed.is_multicast
            or parsed.is_reserved
            or parsed.is_unspecified
        ):
            raise FetchBlockedError(
                "private_or_reserved_ip_rejected", f"{hostname} resolved to {address}"
            )


def _check_idn_confusable(hostname: str) -> str | None:
    for label in hostname.split("."):
        if _MIXED_SCRIPT_LABEL_RE.search(label):
            return "possible_idn_confusable_label"
    return None


def validate_fetch_url(
    url: str, *, allowed_domain: str, resolver: Resolver = default_resolver
) -> tuple[str, list[str]]:
    """Validates `url` may be fetched at all (scheme, credentials,
    hostname, domain match, DNS/IP safety), returning
    `(hostname, warnings)`. Raises `FetchBlockedError` on any
    violation. `allowed_domain` is the single, already
    policy-approved domain this fetch is scoped to -- never a
    caller-supplied wildcard set."""

    warnings: list[str] = []
    parsed = urlparse(url)
    if parsed.scheme not in ("https", "http"):
        raise FetchBlockedError("unsupported_url_scheme", parsed.scheme or "missing")
    if parsed.username or parsed.password:
        raise FetchBlockedError("credentials_in_url_rejected", url)
    if not parsed.hostname:
        raise FetchBlockedError("missing_hostname", url)
    hostname = parsed.hostname.lower()
    if hostname in _BLOCKED_HOSTNAMES or hostname.endswith(".local"):
        raise FetchBlockedError("blocked_hostname", hostname)
    if not is_domain_allowed(hostname, {allowed_domain}):
        raise FetchBlockedError("domain_not_allowlisted", hostname)
    confusable = _check_idn_confusable(hostname)
    if confusable:
        warnings.append(confusable)
    _reject_unsafe_ip(hostname, resolver)
    if parsed.scheme != "https":
        warnings.append("fetched_over_plain_http")
    return hostname, warnings


def fetch_page(
    url: str,
    *,
    allowed_domain: str,
    max_response_bytes: int,
    timeout_seconds: float,
    transport=default_evidence_http_transport,
    resolver: Resolver = default_resolver,
) -> FetchedPage:
    warnings: list[str] = []
    hostname, url_warnings = validate_fetch_url(
        url, allowed_domain=allowed_domain, resolver=resolver
    )
    warnings.extend(url_warnings)

    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    response: EvidenceHttpResponse = transport(url, headers, timeout_seconds)
    if not response.reachable:
        raise FetchBlockedError("transport_error", response.error or "unreachable")

    current_url = url
    redirects_followed = 0
    while response.status_code in _REDIRECT_STATUS_CODES:
        location = response.headers.get("location") or response.headers.get("Location")
        if not location:
            raise FetchBlockedError("redirect_missing_location", current_url)
        if redirects_followed >= MAX_FETCH_REDIRECTS:
            raise FetchBlockedError("too_many_redirects", current_url)
        hostname, redirect_warnings = validate_fetch_url(
            location, allowed_domain=allowed_domain, resolver=resolver
        )
        warnings.extend(redirect_warnings)
        current_url = location
        redirects_followed += 1
        warnings.append("followed_one_validated_redirect")
        response = transport(current_url, headers, timeout_seconds)
        if not response.reachable:
            raise FetchBlockedError("transport_error", response.error or "unreachable")

    content_type_header = response.headers.get("content-type", "") or response.headers.get(
        "Content-Type", ""
    )
    content_type = content_type_header.split(";")[0].strip().lower()
    if content_type not in EVIDENCE_CONTENT_TYPES:
        raise FetchBlockedError("unsupported_content_type", content_type or "unknown")

    raw_bytes = response.body
    if len(raw_bytes) > max_response_bytes:
        raw_bytes = raw_bytes[:max_response_bytes]
        warnings.append("response_truncated_to_size_limit")

    title, headings, published_at, updated_at, canonical_url, language, main_text = (
        _extract_content(content_type, raw_bytes, warnings)
    )

    checksum = hashlib.sha256(main_text.encode("utf-8")).hexdigest()
    return FetchedPage(
        resolved_url=current_url,
        source_domain=hostname,
        http_status=response.status_code,
        content_type=content_type,
        raw_bytes=raw_bytes,
        title=title,
        main_text=main_text,
        headings=headings,
        published_at=published_at,
        updated_at=updated_at,
        canonical_url=canonical_url,
        language=language,
        content_checksum=checksum,
        warnings=warnings,
    )


_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_HEADING_RE = re.compile(r"<h[1-3][^>]*>(.*?)</h[1-3]>", re.IGNORECASE | re.DOTALL)
_CANONICAL_RE = re.compile(
    r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']', re.IGNORECASE
)
_LANG_RE = re.compile(r'<html[^>]+lang=["\']([a-zA-Z-]+)["\']', re.IGNORECASE)
_META_DATE_PATTERNS = (
    (
        "published_at",
        re.compile(
            r'<meta[^>]+(?:property|name)=["\']'
            r'(?:article:published_time|og:published_time|date|datePublished)["\']'
            r'[^>]+content=["\']([^"\']+)["\']',
            re.IGNORECASE,
        ),
    ),
    (
        "updated_at",
        re.compile(
            r'<meta[^>]+(?:property|name)=["\']'
            r'(?:article:modified_time|og:updated_time|last-modified|dateModified)["\']'
            r'[^>]+content=["\']([^"\']+)["\']',
            re.IGNORECASE,
        ),
    ),
)
_TAG_STRIP_RE = re.compile(r"<[^>]+>")


def _clean_fragment(fragment: str) -> str:
    return _TAG_STRIP_RE.sub(" ", fragment).strip()


def _extract_content(
    content_type: str, raw_bytes: bytes, warnings: list[str]
) -> tuple[str | None, tuple[str, ...], str | None, str | None, str | None, str | None, str]:
    if content_type in ("text/plain", "text/markdown"):
        text = raw_bytes.decode("utf-8", errors="replace")
        return None, (), None, None, None, None, text

    if content_type == "application/json":
        text = raw_bytes.decode("utf-8", errors="replace")
        return None, (), None, None, None, None, text

    if content_type == "text/html":
        html = raw_bytes.decode("utf-8", errors="replace")
        title = None
        if match := _TITLE_RE.search(html):
            title = _clean_fragment(match.group(1)) or None
        headings = tuple(
            _clean_fragment(m) for m in _HEADING_RE.findall(html) if _clean_fragment(m)
        )[:20]
        canonical_url = None
        if match := _CANONICAL_RE.search(html):
            canonical_url = match.group(1).strip()
        language = None
        if match := _LANG_RE.search(html):
            language = match.group(1).strip()
        published_at = None
        updated_at = None
        for name, pattern in _META_DATE_PATTERNS:
            if match := pattern.search(html):
                value = match.group(1).strip()
                if name == "published_at":
                    published_at = value
                else:
                    updated_at = value
        result = extract_html_snapshot_text(raw_bytes)
        warnings.extend(result.get("issues", []))
        return title, headings, published_at, updated_at, canonical_url, language, result["text"]

    if content_type == "application/pdf":
        text = _extract_pdf_text(raw_bytes, warnings)
        return None, (), None, None, None, None, text

    raise FetchBlockedError("unsupported_content_type", content_type)


def _extract_pdf_text(raw_bytes: bytes, warnings: list[str]) -> str:
    try:
        import fitz
    except ImportError:  # pragma: no cover - capability fallback
        raise FetchBlockedError("pdf_extraction_unavailable") from None

    with fitz.open(stream=raw_bytes, filetype="pdf") as pdf:
        if pdf.needs_pass or pdf.is_encrypted:
            raise FetchBlockedError("encrypted_pdf_rejected")
        pages = [page.get_text("text") for page in pdf]
    text = "\n\n".join(page for page in pages if page.strip())
    if not text:
        warnings.append("no_embedded_text_found_in_pdf")
    return text


__all__ = [
    "MAX_FETCH_REDIRECTS",
    "USER_AGENT",
    "FetchBlockedError",
    "FetchedPage",
    "fetch_page",
    "validate_fetch_url",
]
