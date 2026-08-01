import fitz
import pytest

from backend.services.dataset_verification_transport import (
    EvidenceHttpResponse,
    EvidenceRetrievalError,
    default_resolver,
    fetch_evidence,
    is_domain_allowed,
)


def make_pdf(*texts: str) -> bytes:
    pdf = fitz.open()
    for text in texts:
        page = pdf.new_page()
        page.insert_text((72, 72), text)
    value = pdf.tobytes()
    pdf.close()
    return value


def _transport(*responses: EvidenceHttpResponse):
    remaining = list(responses)

    def transport(url, headers, timeout_seconds):
        del url, headers, timeout_seconds
        assert remaining, "transport called more times than expected"
        return remaining.pop(0)

    return transport


def _resolver(mapping: dict[str, list[str]]):
    def resolver(hostname: str) -> list[str]:
        return mapping[hostname]

    return resolver


# -- domain allowlist matching -------------------------------------------------


def test_is_domain_allowed_exact_and_subdomain_match() -> None:
    allowed = {"huggingface.co"}
    assert is_domain_allowed("huggingface.co", allowed) is True
    assert is_domain_allowed("datasets.huggingface.co", allowed) is True
    assert is_domain_allowed("HUGGINGFACE.CO", allowed) is True


def test_is_domain_allowed_never_substring_matches() -> None:
    allowed = {"huggingface.co"}
    assert is_domain_allowed("evilhuggingface.co", allowed) is False
    assert is_domain_allowed("huggingface.co.evil.com", allowed) is False
    assert is_domain_allowed("nothuggingface.co", allowed) is False


# -- domain allowlist enforcement (rejects arbitrary URLs) ---------------------


def test_fetch_evidence_rejects_url_outside_allowlist() -> None:
    with pytest.raises(EvidenceRetrievalError) as excinfo:
        fetch_evidence(
            "https://attacker.example.com/licence.txt",
            allowed_domains={"huggingface.co"},
            resolver=_resolver({}),
        )
    assert excinfo.value.reason == "domain_not_allowlisted"


def test_fetch_evidence_rejects_unsupported_scheme() -> None:
    with pytest.raises(EvidenceRetrievalError) as excinfo:
        fetch_evidence(
            "ftp://huggingface.co/licence.txt",
            allowed_domains={"huggingface.co"},
            resolver=_resolver({"huggingface.co": ["18.0.0.1"]}),
        )
    assert excinfo.value.reason == "unsupported_url_scheme"


# -- SSRF: private/loopback/link-local/multicast/reserved IP rejection --------


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",  # loopback
        "10.0.0.5",  # private
        "192.168.1.1",  # private
        "169.254.1.1",  # link-local
        "224.0.0.1",  # multicast
        "0.0.0.0",  # unspecified
        "::1",  # loopback (IPv6)
        "fc00::1",  # unique local (private, IPv6)
    ],
)
def test_fetch_evidence_rejects_unsafe_resolved_ip(address: str) -> None:
    with pytest.raises(EvidenceRetrievalError) as excinfo:
        fetch_evidence(
            "https://huggingface.co/licence.txt",
            allowed_domains={"huggingface.co"},
            resolver=_resolver({"huggingface.co": [address]}),
        )
    assert excinfo.value.reason == "private_or_reserved_ip_rejected"


def test_fetch_evidence_accepts_public_resolved_ip() -> None:
    result = fetch_evidence(
        "https://huggingface.co/licence.txt",
        allowed_domains={"huggingface.co"},
        resolver=_resolver({"huggingface.co": ["18.0.0.1"]}),
        transport=_transport(
            EvidenceHttpResponse(
                status_code=200,
                headers={"content-type": "text/plain"},
                body=b"CC-BY-4.0",
            )
        ),
    )
    assert result.content_text == "CC-BY-4.0"
    assert result.http_status == 200


def test_default_resolver_rejects_unresolvable_hostname() -> None:
    with pytest.raises(EvidenceRetrievalError) as excinfo:
        default_resolver("this-host-does-not-exist.invalid")
    assert excinfo.value.reason == "dns_resolution_failed"


# -- redirect handling: single validated hop only ------------------------------


def test_fetch_evidence_follows_one_redirect_to_allowlisted_domain() -> None:
    result = fetch_evidence(
        "https://huggingface.co/old-licence.txt",
        allowed_domains={"huggingface.co"},
        resolver=_resolver({"huggingface.co": ["18.0.0.1"]}),
        transport=_transport(
            EvidenceHttpResponse(
                status_code=302,
                headers={"location": "https://huggingface.co/new-licence.txt"},
                body=b"",
            ),
            EvidenceHttpResponse(
                status_code=200,
                headers={"content-type": "text/plain"},
                body=b"CC-BY-4.0",
            ),
        ),
    )
    assert result.resolved_url == "https://huggingface.co/new-licence.txt"
    assert "followed_one_validated_redirect" in result.warnings


def test_fetch_evidence_rejects_redirect_to_unallowlisted_domain() -> None:
    with pytest.raises(EvidenceRetrievalError) as excinfo:
        fetch_evidence(
            "https://huggingface.co/licence.txt",
            allowed_domains={"huggingface.co"},
            resolver=_resolver(
                {"huggingface.co": ["18.0.0.1"], "attacker.example.com": ["18.0.0.2"]}
            ),
            transport=_transport(
                EvidenceHttpResponse(
                    status_code=302,
                    headers={"location": "https://attacker.example.com/steal"},
                    body=b"",
                )
            ),
        )
    assert excinfo.value.reason == "domain_not_allowlisted"


def test_fetch_evidence_rejects_second_redirect_hop() -> None:
    with pytest.raises(EvidenceRetrievalError) as excinfo:
        fetch_evidence(
            "https://huggingface.co/a.txt",
            allowed_domains={"huggingface.co"},
            resolver=_resolver({"huggingface.co": ["18.0.0.1"]}),
            transport=_transport(
                EvidenceHttpResponse(
                    status_code=302,
                    headers={"location": "https://huggingface.co/b.txt"},
                    body=b"",
                ),
                EvidenceHttpResponse(
                    status_code=302,
                    headers={"location": "https://huggingface.co/c.txt"},
                    body=b"",
                ),
            ),
        )
    assert excinfo.value.reason == "too_many_redirects"


def test_fetch_evidence_rejects_redirect_response_missing_location() -> None:
    with pytest.raises(EvidenceRetrievalError) as excinfo:
        fetch_evidence(
            "https://huggingface.co/a.txt",
            allowed_domains={"huggingface.co"},
            resolver=_resolver({"huggingface.co": ["18.0.0.1"]}),
            transport=_transport(EvidenceHttpResponse(status_code=302, headers={}, body=b"")),
        )
    assert excinfo.value.reason == "redirect_missing_location"


# -- transport failure ----------------------------------------------------------


def test_fetch_evidence_raises_on_unreachable_transport() -> None:
    with pytest.raises(EvidenceRetrievalError) as excinfo:
        fetch_evidence(
            "https://huggingface.co/a.txt",
            allowed_domains={"huggingface.co"},
            resolver=_resolver({"huggingface.co": ["18.0.0.1"]}),
            transport=_transport(
                EvidenceHttpResponse(
                    status_code=0, headers={}, body=b"", reachable=False, error="ConnectTimeout"
                )
            ),
        )
    assert excinfo.value.reason == "transport_error"


# -- MIME allowlist ---------------------------------------------------------------


def test_fetch_evidence_rejects_unsupported_mime_type() -> None:
    with pytest.raises(EvidenceRetrievalError) as excinfo:
        fetch_evidence(
            "https://huggingface.co/a.zip",
            allowed_domains={"huggingface.co"},
            resolver=_resolver({"huggingface.co": ["18.0.0.1"]}),
            transport=_transport(
                EvidenceHttpResponse(
                    status_code=200,
                    headers={"content-type": "application/zip"},
                    body=b"PK\x03\x04",
                )
            ),
        )
    assert excinfo.value.reason == "unsupported_content_type"


@pytest.mark.parametrize(
    ("content_type", "body", "expected_text"),
    [
        ("text/plain", b"Plain licence text", "Plain licence text"),
        ("text/markdown", b"# Licence\nCC-BY-4.0", "# Licence\nCC-BY-4.0"),
        ("application/json", b'{"licence": "CC-BY-4.0"}', '{"licence": "CC-BY-4.0"}'),
    ],
)
def test_fetch_evidence_accepts_each_supported_text_mime_type(
    content_type: str, body: bytes, expected_text: str
) -> None:
    result = fetch_evidence(
        "https://huggingface.co/a",
        allowed_domains={"huggingface.co"},
        resolver=_resolver({"huggingface.co": ["18.0.0.1"]}),
        transport=_transport(
            EvidenceHttpResponse(status_code=200, headers={"content-type": content_type}, body=body)
        ),
    )
    assert result.content_type == content_type
    assert result.content_text == expected_text


# -- HTML safe stripping ----------------------------------------------------------


def test_fetch_evidence_strips_html_scripts_and_tags() -> None:
    html = (
        b"<html><head><script>alert('xss')</script></head>"
        b"<body><h1>Licence</h1><p>CC-BY-4.0</p></body></html>"
    )
    result = fetch_evidence(
        "https://huggingface.co/licence.html",
        allowed_domains={"huggingface.co"},
        resolver=_resolver({"huggingface.co": ["18.0.0.1"]}),
        transport=_transport(
            EvidenceHttpResponse(status_code=200, headers={"content-type": "text/html"}, body=html)
        ),
    )
    assert "alert" not in result.content_text
    assert "<script>" not in result.content_text
    assert "<h1>" not in result.content_text
    assert "CC-BY-4.0" in result.content_text
    assert "html_stripped" in result.warnings


# -- PDF embedded-text extraction -------------------------------------------------


def test_fetch_evidence_extracts_embedded_pdf_text() -> None:
    pdf_bytes = make_pdf("CC-BY-4.0 Licence Text")
    result = fetch_evidence(
        "https://huggingface.co/licence.pdf",
        allowed_domains={"huggingface.co"},
        resolver=_resolver({"huggingface.co": ["18.0.0.1"]}),
        transport=_transport(
            EvidenceHttpResponse(
                status_code=200, headers={"content-type": "application/pdf"}, body=pdf_bytes
            )
        ),
    )
    assert "CC-BY-4.0 Licence Text" in result.content_text


def test_fetch_evidence_rejects_encrypted_pdf() -> None:
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "Secret licence")
    encrypted_bytes = pdf.tobytes(
        encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="user"
    )
    pdf.close()

    with pytest.raises(EvidenceRetrievalError) as excinfo:
        fetch_evidence(
            "https://huggingface.co/encrypted.pdf",
            allowed_domains={"huggingface.co"},
            resolver=_resolver({"huggingface.co": ["18.0.0.1"]}),
            transport=_transport(
                EvidenceHttpResponse(
                    status_code=200,
                    headers={"content-type": "application/pdf"},
                    body=encrypted_bytes,
                )
            ),
        )
    assert excinfo.value.reason == "encrypted_pdf_rejected"


# -- size bounds -------------------------------------------------------------------


def test_fetch_evidence_truncates_oversized_response() -> None:
    from core_model.data_verification import MAX_EVIDENCE_RESPONSE_BYTES

    oversized_body = b"A" * (MAX_EVIDENCE_RESPONSE_BYTES + 1000)
    result = fetch_evidence(
        "https://huggingface.co/huge.txt",
        allowed_domains={"huggingface.co"},
        resolver=_resolver({"huggingface.co": ["18.0.0.1"]}),
        transport=_transport(
            EvidenceHttpResponse(
                status_code=200, headers={"content-type": "text/plain"}, body=oversized_body
            )
        ),
    )
    assert result.size_bytes == MAX_EVIDENCE_RESPONSE_BYTES
    assert "response_truncated_to_size_limit" in result.warnings


# -- warnings for plain HTTP --------------------------------------------------------


def test_fetch_evidence_warns_on_plain_http() -> None:
    result = fetch_evidence(
        "http://huggingface.co/a.txt",
        allowed_domains={"huggingface.co"},
        resolver=_resolver({"huggingface.co": ["18.0.0.1"]}),
        transport=_transport(
            EvidenceHttpResponse(status_code=200, headers={"content-type": "text/plain"}, body=b"x")
        ),
    )
    assert "fetched_over_plain_http" in result.warnings


# -- no dynamic execution ------------------------------------------------------------


def test_transport_module_never_executes_or_shells_out() -> None:
    import re
    from pathlib import Path

    source = Path("backend/services/dataset_verification_transport.py").read_text()
    forbidden = re.compile(r"\b(eval|exec|subprocess|os\.system|pickle\.loads)\s*\(")
    assert not forbidden.search(source)
