import json
from pathlib import Path

import pytest

from core_model.knowledge_routing.policy_loader import (
    PolicyValidationError,
    compute_policy_checksum,
    load_policy,
    reset_policy_cache,
    validate_policy_schema,
)


def test_checked_in_policy_loads_and_validates() -> None:
    policy = load_policy()
    assert policy["policy_version"]
    assert policy["taxonomy_version"]
    assert validate_policy_schema(policy) == []


def test_checksum_excludes_its_own_field() -> None:
    policy = load_policy()
    payload_without_checksum = {k: v for k, v in policy.items() if k != "policy_checksum_sha256"}
    assert compute_policy_checksum(policy) == compute_policy_checksum(
        {**payload_without_checksum, "policy_checksum_sha256": "irrelevant-old-value"}
    )


def test_tampered_policy_file_fails_closed(tmp_path: Path) -> None:
    policy = load_policy()
    tampered = dict(policy)
    tampered["domains"] = dict(tampered["domains"])
    tampered["domains"]["mathematics"] = dict(tampered["domains"]["mathematics"])
    existing_keywords = tampered["domains"]["mathematics"]["keywords_en"]
    tampered["domains"]["mathematics"]["keywords_en"] = [*existing_keywords, "injected"]
    # checksum deliberately left stale
    path = tmp_path / "tampered_policy.json"
    path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(PolicyValidationError, match="checksum mismatch"):
        load_policy(path)


def test_malformed_json_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(PolicyValidationError, match="not valid JSON"):
        load_policy(path)


def test_unknown_domain_in_policy_fails_schema_validation() -> None:
    policy = load_policy()
    bad_domain = {"keywords_en": [], "keywords_ta": []}
    invalid = {**policy, "domains": {**policy["domains"], "not_a_real_domain": bad_domain}}
    problems = validate_policy_schema(invalid)
    assert any("not_a_real_domain" in p for p in problems)


def test_missing_required_top_level_key_fails_schema_validation() -> None:
    policy = load_policy()
    invalid = {k: v for k, v in policy.items() if k != "intents"}
    problems = validate_policy_schema(invalid)
    assert any("intents" in p for p in problems)


def test_get_policy_cache_can_be_reset_for_tests() -> None:
    reset_policy_cache()
    policy = load_policy()
    assert policy["policy_version"]
