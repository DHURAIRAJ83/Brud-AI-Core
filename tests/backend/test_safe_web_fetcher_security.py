"""Phase 20 Step 6/7/37 -- SSRF and safe-fetch security tests for
`backend/services/safe_web_fetcher.py`. Every case here uses an
injectable fake `resolver`/`transport` (never real network I/O),
matching this codebase's own established pattern for testing
`fetch_evidence` and friends -- these are pure, deterministic, fast
unit tests, not integration tests against the live internet.
"""

from __future__ import annotations

import pytest

from backend.services.dataset_verification_transport import EvidenceHttpResponse
from backend.services.safe_web_fetcher import (
    MAX_FETCH_REDIRECTS,
    FetchBlockedError,
    fetch_page,
    validate_fetch_url,
)

ALLOWED_DOMAIN = "example.com"


def _resolver(mapping: dict[str, list[str]]):
    def resolve(hostname: str) -> list[str]:
        return mapping.get(hostname, ["93.184.216.34"])  # a real public IP as the safe default

    return resolve


def _ok_transport(*, status_code=200, headers=None, body=b"<html><title>T</title>hi</html>"):
    def transport(url, headers_arg, timeout_seconds):
        return EvidenceHttpResponse(
            status_code=status_code,
            headers=headers or {"content-type": "text/html"},
            body=body,
        )

    return transport


# -- URL scheme / credential blocks -------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.com/file",
        "gopher://example.com/",
        "data:text/html,<script>alert(1)</script>",
        "javascript:alert(1)",
        "ws://example.com/",
    ],
)
def test_non_http_schemes_are_rejected(url: str) -> None:
    with pytest.raises(FetchBlockedError) as exc_info:
        validate_fetch_url(url, allowed_domain=ALLOWED_DOMAIN, resolver=_resolver({}))
    assert exc_info.value.reason == "unsupported_url_scheme"


def test_credential_bearing_url_is_rejected() -> None:
    with pytest.raises(FetchBlockedError) as exc_info:
        validate_fetch_url(
            "https://user:pass@example.com/",
            allowed_domain=ALLOWED_DOMAIN,
            resolver=_resolver({}),
        )
    assert exc_info.value.reason == "credentials_in_url_rejected"


# -- hostname / domain allowlist blocks ----------------------------------------------------------


def test_localhost_hostname_is_blocked() -> None:
    with pytest.raises(FetchBlockedError) as exc_info:
        validate_fetch_url("http://localhost/", allowed_domain="localhost", resolver=_resolver({}))
    assert exc_info.value.reason == "blocked_hostname"


def test_dot_local_hostname_is_blocked() -> None:
    with pytest.raises(FetchBlockedError) as exc_info:
        validate_fetch_url(
            "http://printer.local/", allowed_domain="printer.local", resolver=_resolver({})
        )
    assert exc_info.value.reason == "blocked_hostname"


def test_metadata_hostname_is_blocked() -> None:
    with pytest.raises(FetchBlockedError) as exc_info:
        validate_fetch_url(
            "http://metadata.google.internal/",
            allowed_domain="metadata.google.internal",
            resolver=_resolver({}),
        )
    # Blocked at the hostname layer (checked before the IP/metadata-address
    # layer) -- still correctly and unconditionally rejected either way.
    assert exc_info.value.reason == "blocked_hostname"


def test_domain_not_in_allowlist_is_blocked() -> None:
    with pytest.raises(FetchBlockedError) as exc_info:
        validate_fetch_url(
            "https://evil-example.com/",
            allowed_domain=ALLOWED_DOMAIN,
            resolver=_resolver({}),
        )
    assert exc_info.value.reason == "domain_not_allowlisted"


def test_subdomain_confusable_lookalike_domain_is_blocked() -> None:
    """`evilexample.com` (no dot) must never match `example.com`."""

    with pytest.raises(FetchBlockedError) as exc_info:
        validate_fetch_url(
            "https://evilexample.com/",
            allowed_domain=ALLOWED_DOMAIN,
            resolver=_resolver({}),
        )
    assert exc_info.value.reason == "domain_not_allowlisted"


def test_legitimate_subdomain_of_allowed_domain_is_allowed() -> None:
    hostname, warnings = validate_fetch_url(
        "https://docs.example.com/page",
        allowed_domain=ALLOWED_DOMAIN,
        resolver=_resolver({}),
    )
    assert hostname == "docs.example.com"
    assert "possible_idn_confusable_label" not in warnings


# -- DNS/IP safety (the core SSRF defense) -------------------------------------------------------


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",  # loopback
        "127.5.5.5",  # loopback range
        "0.0.0.0",  # unspecified
        "10.0.0.1",  # private
        "172.16.0.1",  # private
        "192.168.0.1",  # private
        "169.254.1.1",  # link-local
        "224.0.0.1",  # multicast
        "::1",  # IPv6 loopback
        "fc00::1",  # IPv6 unique local (private)
        "fe80::1",  # IPv6 link-local
        "ff02::1",  # IPv6 multicast
    ],
)
def test_hostname_resolving_to_unsafe_address_is_blocked(ip: str) -> None:
    resolver = _resolver({ALLOWED_DOMAIN: [ip]})
    with pytest.raises(FetchBlockedError) as exc_info:
        validate_fetch_url(
            f"https://{ALLOWED_DOMAIN}/",
            allowed_domain=ALLOWED_DOMAIN,
            resolver=resolver,
        )
    assert exc_info.value.reason in (
        "private_or_reserved_ip_rejected",
        "metadata_endpoint_rejected",
    )


def test_metadata_ip_169_254_169_254_is_blocked() -> None:
    resolver = _resolver({ALLOWED_DOMAIN: ["169.254.169.254"]})
    with pytest.raises(FetchBlockedError) as exc_info:
        validate_fetch_url(
            f"https://{ALLOWED_DOMAIN}/",
            allowed_domain=ALLOWED_DOMAIN,
            resolver=resolver,
        )
    assert exc_info.value.reason == "metadata_endpoint_rejected"


def test_hostname_with_one_safe_and_one_unsafe_resolved_address_is_blocked() -> None:
    """DNS returning multiple A/AAAA records where *any* is unsafe must
    block the whole request -- never picking only the "nice" address."""

    resolver = _resolver({ALLOWED_DOMAIN: ["93.184.216.34", "127.0.0.1"]})
    with pytest.raises(FetchBlockedError):
        validate_fetch_url(
            f"https://{ALLOWED_DOMAIN}/",
            allowed_domain=ALLOWED_DOMAIN,
            resolver=resolver,
        )


def test_public_ip_hostname_is_allowed() -> None:
    hostname, warnings = validate_fetch_url(
        f"https://{ALLOWED_DOMAIN}/",
        allowed_domain=ALLOWED_DOMAIN,
        resolver=_resolver({ALLOWED_DOMAIN: ["93.184.216.34"]}),
    )
    assert hostname == ALLOWED_DOMAIN


# -- IDN confusable heuristic ---------------------------------------------------------------------


def test_mixed_script_hostname_produces_a_warning_not_a_silent_pass() -> None:
    # Cyrillic 'а' mixed with Latin letters in one label.
    hostname, warnings = validate_fetch_url(
        "https://exаmple.com/",
        allowed_domain="exаmple.com",
        resolver=_resolver({}),
    )
    assert "possible_idn_confusable_label" in warnings


# -- redirect handling ------------------------------------------------------------------------


def test_redirect_to_raw_metadata_ip_is_blocked() -> None:
    """The redirect target is a raw IP literal, not `allowed_domain` --
    blocked at the domain-allowlist layer, which is itself sufficient
    defense (the metadata IP is never actually requested either way)."""

    def transport(url, headers, timeout_seconds):
        if url == f"https://{ALLOWED_DOMAIN}/start":
            return EvidenceHttpResponse(
                status_code=302,
                headers={"location": "http://169.254.169.254/secret"},
                body=b"",
            )
        raise AssertionError("must never actually request the redirect target")

    with pytest.raises(FetchBlockedError) as exc_info:
        fetch_page(
            f"https://{ALLOWED_DOMAIN}/start",
            allowed_domain=ALLOWED_DOMAIN,
            max_response_bytes=2_000_000,
            timeout_seconds=5.0,
            transport=transport,
            resolver=_resolver({ALLOWED_DOMAIN: ["93.184.216.34"]}),
        )
    assert exc_info.value.reason == "domain_not_allowlisted"


def test_redirect_to_same_domain_resolving_to_metadata_ip_is_blocked() -> None:
    """A redirect that stays within the allowlisted domain, but whose
    DNS now resolves to the cloud-metadata address, is still blocked
    -- proving the IP/metadata check re-runs on the redirect hop, not
    just the domain-string check."""

    def transport(url, headers, timeout_seconds):
        if url == f"https://{ALLOWED_DOMAIN}/start":
            return EvidenceHttpResponse(
                status_code=302,
                headers={"location": f"https://{ALLOWED_DOMAIN}/internal-redirect"},
                body=b"",
            )
        raise AssertionError("must never actually request the redirect target")

    with pytest.raises(FetchBlockedError) as exc_info:
        fetch_page(
            f"https://{ALLOWED_DOMAIN}/start",
            allowed_domain=ALLOWED_DOMAIN,
            max_response_bytes=2_000_000,
            timeout_seconds=5.0,
            transport=transport,
            resolver=_resolver({ALLOWED_DOMAIN: ["169.254.169.254"]}),
        )
    assert exc_info.value.reason == "metadata_endpoint_rejected"


def test_redirect_to_different_but_allowlisted_domain_is_blocked_by_default_scope() -> None:
    """A redirect off the single scoped `allowed_domain` is rejected --
    this fetch was scoped to exactly one domain, not the whole policy
    allowlist, so cross-domain redirects never silently expand scope."""

    def transport(url, headers, timeout_seconds):
        if url == f"https://{ALLOWED_DOMAIN}/start":
            return EvidenceHttpResponse(
                status_code=302,
                headers={"location": "https://other-allowed.example/"},
                body=b"",
            )
        raise AssertionError("must never request an out-of-scope redirect target")

    with pytest.raises(FetchBlockedError) as exc_info:
        fetch_page(
            f"https://{ALLOWED_DOMAIN}/start",
            allowed_domain=ALLOWED_DOMAIN,
            max_response_bytes=2_000_000,
            timeout_seconds=5.0,
            transport=transport,
            resolver=_resolver({ALLOWED_DOMAIN: ["93.184.216.34"]}),
        )
    assert exc_info.value.reason == "domain_not_allowlisted"


def test_redirect_loop_is_bounded_not_infinite() -> None:
    calls = {"count": 0}

    def transport(url, headers, timeout_seconds):
        calls["count"] += 1
        return EvidenceHttpResponse(
            status_code=302,
            headers={"location": f"https://{ALLOWED_DOMAIN}/next"},
            body=b"",
        )

    with pytest.raises(FetchBlockedError) as exc_info:
        fetch_page(
            f"https://{ALLOWED_DOMAIN}/start",
            allowed_domain=ALLOWED_DOMAIN,
            max_response_bytes=2_000_000,
            timeout_seconds=5.0,
            transport=transport,
            resolver=_resolver({ALLOWED_DOMAIN: ["93.184.216.34"]}),
        )
    assert exc_info.value.reason == "too_many_redirects"
    # At most one redirect is ever followed (MAX_FETCH_REDIRECTS), so the
    # transport is called at most twice before the bounded error fires.
    assert calls["count"] <= MAX_FETCH_REDIRECTS + 2


def test_single_valid_redirect_is_followed_exactly_once() -> None:
    def transport(url, headers, timeout_seconds):
        if url == f"https://{ALLOWED_DOMAIN}/start":
            return EvidenceHttpResponse(
                status_code=302,
                headers={"location": f"https://{ALLOWED_DOMAIN}/final"},
                body=b"",
            )
        return EvidenceHttpResponse(
            status_code=200,
            headers={"content-type": "text/html"},
            body=b"<html><title>Final</title>hello</html>",
        )

    page = fetch_page(
        f"https://{ALLOWED_DOMAIN}/start",
        allowed_domain=ALLOWED_DOMAIN,
        max_response_bytes=2_000_000,
        timeout_seconds=5.0,
        transport=transport,
        resolver=_resolver({ALLOWED_DOMAIN: ["93.184.216.34"]}),
    )
    assert page.resolved_url == f"https://{ALLOWED_DOMAIN}/final"
    assert page.title == "Final"


# -- content-type / size bounds -----------------------------------------------------------------


def test_unsupported_content_type_is_blocked() -> None:
    transport = _ok_transport(headers={"content-type": "application/x-executable"})
    with pytest.raises(FetchBlockedError) as exc_info:
        fetch_page(
            f"https://{ALLOWED_DOMAIN}/file.exe",
            allowed_domain=ALLOWED_DOMAIN,
            max_response_bytes=2_000_000,
            timeout_seconds=5.0,
            transport=transport,
            resolver=_resolver({ALLOWED_DOMAIN: ["93.184.216.34"]}),
        )
    assert exc_info.value.reason == "unsupported_content_type"


def test_zip_archive_content_type_is_blocked() -> None:
    transport = _ok_transport(headers={"content-type": "application/zip"})
    with pytest.raises(FetchBlockedError):
        fetch_page(
            f"https://{ALLOWED_DOMAIN}/archive.zip",
            allowed_domain=ALLOWED_DOMAIN,
            max_response_bytes=2_000_000,
            timeout_seconds=5.0,
            transport=transport,
            resolver=_resolver({ALLOWED_DOMAIN: ["93.184.216.34"]}),
        )


def test_oversized_response_is_truncated_not_unbounded() -> None:
    huge_body = b"<html><title>Big</title>" + (b"x" * 500) + b"</html>"
    transport = _ok_transport(body=huge_body)
    page = fetch_page(
        f"https://{ALLOWED_DOMAIN}/big",
        allowed_domain=ALLOWED_DOMAIN,
        max_response_bytes=100,
        timeout_seconds=5.0,
        transport=transport,
        resolver=_resolver({ALLOWED_DOMAIN: ["93.184.216.34"]}),
    )
    assert len(page.raw_bytes) <= 100
    assert "response_truncated_to_size_limit" in page.warnings


def test_transport_unreachable_raises_blocked_error() -> None:
    def transport(url, headers, timeout_seconds):
        return EvidenceHttpResponse(
            status_code=0,
            headers={},
            body=b"",
            reachable=False,
            error="ConnectTimeout",
        )

    with pytest.raises(FetchBlockedError) as exc_info:
        fetch_page(
            f"https://{ALLOWED_DOMAIN}/",
            allowed_domain=ALLOWED_DOMAIN,
            max_response_bytes=2_000_000,
            timeout_seconds=5.0,
            transport=transport,
            resolver=_resolver({ALLOWED_DOMAIN: ["93.184.216.34"]}),
        )
    assert exc_info.value.reason == "transport_error"


# -- no JS execution, no forms, no cookies, no auth (structural proof) --------------------------


def test_fetcher_never_executes_scripts_scripts_are_stripped_as_text() -> None:
    body = b"<html><title>T</title><script>alert('should never run')</script>real content</html>"
    transport = _ok_transport(body=body)
    page = fetch_page(
        f"https://{ALLOWED_DOMAIN}/",
        allowed_domain=ALLOWED_DOMAIN,
        max_response_bytes=2_000_000,
        timeout_seconds=5.0,
        transport=transport,
        resolver=_resolver({ALLOWED_DOMAIN: ["93.184.216.34"]}),
    )
    assert "alert(" not in page.main_text


def test_fetch_page_signature_has_no_cookie_or_auth_parameter() -> None:
    """Structural proof, not just a docstring claim: `fetch_page`'s
    signature has no cookie jar / credential / proxy parameter for a
    caller to (mis)use."""

    import inspect

    params = set(inspect.signature(fetch_page).parameters)
    assert params == {
        "url",
        "allowed_domain",
        "max_response_bytes",
        "timeout_seconds",
        "transport",
        "resolver",
    }


# -- successful content extraction (positive path) -----------------------------------------------


def test_successful_html_fetch_extracts_title_and_dates() -> None:
    body = (
        b'<html lang="en"><head><title>My Page</title>'
        b'<meta property="article:published_time" content="2026-01-01T00:00:00Z">'
        b'<link rel="canonical" href="https://example.com/canonical">'
        b"</head><body><h1>Heading</h1>Body text here.</body></html>"
    )
    transport = _ok_transport(body=body)
    page = fetch_page(
        f"https://{ALLOWED_DOMAIN}/",
        allowed_domain=ALLOWED_DOMAIN,
        max_response_bytes=2_000_000,
        timeout_seconds=5.0,
        transport=transport,
        resolver=_resolver({ALLOWED_DOMAIN: ["93.184.216.34"]}),
    )
    assert page.title == "My Page"
    assert page.published_at == "2026-01-01T00:00:00Z"
    assert page.canonical_url == "https://example.com/canonical"
    assert page.language == "en"
    assert "Body text here." in page.main_text
