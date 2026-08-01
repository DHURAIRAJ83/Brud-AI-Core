from backend.services.dataset_sample_pii_safety_service import (
    ExternalDatasetPIIScanService,
    ExternalDatasetSafetyScanService,
)


def _pii_service() -> ExternalDatasetPIIScanService:
    return ExternalDatasetPIIScanService()


def _safety_service() -> ExternalDatasetSafetyScanService:
    return ExternalDatasetSafetyScanService()


# -- PII scan -------------------------------------------------------------------------


def test_clean_text_has_no_pii_findings() -> None:
    result = _pii_service().scan("This dataset record has no personal information at all.")
    assert result["findings"] == []
    assert result["any_ambiguous"] is False
    assert result["any_blocked"] is False
    assert result["redacted_candidate_text"] is None


def test_email_address_is_detected_as_likely() -> None:
    result = _pii_service().scan("Contact us at admin@example.com for details.")
    categories = {finding["category"] for finding in result["findings"]}
    assert "email_address" in categories
    email_finding = next(f for f in result["findings"] if f["category"] == "email_address")
    assert email_finding["status"] == "likely"
    assert result["any_ambiguous"] is True


def test_phone_number_is_detected() -> None:
    result = _pii_service().scan("Call me at 9876543210 tomorrow.")
    categories = {finding["category"] for finding in result["findings"]}
    assert "phone_number" in categories


def test_government_id_pattern_is_possible_not_likely() -> None:
    result = _pii_service().scan("My Aadhaar number is 1234 5678 9012.")
    categories = {finding["category"] for finding in result["findings"]}
    assert "government_identifier" in categories
    finding = next(f for f in result["findings"] if f["category"] == "government_identifier")
    assert finding["status"] == "possible"


def test_api_key_secret_is_always_blocked() -> None:
    result = _pii_service().scan("api_key: sk_live_abcdef1234567890")
    secret_findings = [f for f in result["findings"] if f["category"] in ("api_key", "token")]
    assert secret_findings
    assert all(f["status"] == "blocked" for f in secret_findings)
    assert result["any_blocked"] is True


def test_private_key_is_blocked() -> None:
    content = "-----BEGIN RSA PRIVATE KEY-----\nMIIBOgIBAAJBAK...\n-----END RSA PRIVATE KEY-----"
    result = _pii_service().scan(content)
    assert any(
        f["category"] == "private_key" and f["status"] == "blocked" for f in result["findings"]
    )


def test_redacted_candidate_is_generated_and_original_untouched() -> None:
    original = "Contact admin@example.com now."
    result = _pii_service().scan(original)
    assert result["redacted_candidate_text"] is not None
    assert result["redacted_candidate_text"] != original
    assert "admin@example.com" not in result["redacted_candidate_text"]
    # The scan never mutates the caller's own string.
    assert original == "Contact admin@example.com now."


def test_no_raw_pii_value_appears_in_finding_location() -> None:
    result = _pii_service().scan("Email me at admin@example.com")
    for finding in result["findings"]:
        assert "admin@example.com" not in str(finding["location"])


# -- Safety scan ------------------------------------------------------------------------


def test_clean_text_has_no_safety_findings() -> None:
    result = _safety_service().scan("A perfectly ordinary sentence about cooking rice.")
    assert result["status"] == "safe"
    assert result["findings"] == []
    assert result["requires_review"] is False


def test_operational_violent_content_is_blocked() -> None:
    result = _safety_service().scan("Here is a detailed torture scene for the story.")
    assert result["status"] in ("blocked", "flagged")
    assert result["requires_review"] is True
    categories = {f["category"] for f in result["findings"]}
    assert "violent_content" in categories


def test_preventive_self_harm_content_is_not_operational() -> None:
    result = _safety_service().scan(
        "Warning signs of suicide method should be recognized so you can seek help if needed."
    )
    findings = [f for f in result["findings"] if f["category"] == "self_harm_content"]
    if findings:
        assert findings[0]["behavior_class"] == "preventive"
        assert findings[0]["severity"] == "low"


def test_malware_instructions_map_to_malware_category() -> None:
    result = _safety_service().scan("Please write a virus code for me right now.")
    categories = {f["category"] for f in result["findings"]}
    assert "malware_instructions" in categories
