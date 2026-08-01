from core_model.data_discovery.candidate_model import NormalizedDatasetMetadata
from core_model.data_discovery.deduplication import (
    cross_reference_signals,
    is_cross_referenced,
    is_possible_duplicate,
    is_strong_duplicate,
    strong_signals,
)


def _metadata(**overrides):
    defaults = {
        "provider_dataset_id": "ds-1",
        "name": "Tamil Conversations",
        "organization": "example-org",
    }
    return NormalizedDatasetMetadata(**{**defaults, **overrides})


def test_exact_same_provider_dataset_id_is_a_strong_duplicate() -> None:
    a = strong_signals(_metadata(provider_dataset_id="abc"), provider_code="huggingface")
    b = strong_signals(_metadata(provider_dataset_id="abc"), provider_code="huggingface")
    assert is_strong_duplicate(a, b)


def test_same_org_and_name_is_a_strong_duplicate_even_across_providers() -> None:
    a = strong_signals(
        _metadata(provider_dataset_id="hf-1", organization="AI4Bharat", name="Tamil Corpus"),
        provider_code="huggingface",
    )
    b = strong_signals(
        _metadata(provider_dataset_id="gh-1", organization="AI4Bharat", name="Tamil Corpus"),
        provider_code="github",
    )
    assert is_strong_duplicate(a, b)


def test_same_title_different_organization_is_not_a_strong_duplicate() -> None:
    a = strong_signals(
        _metadata(provider_dataset_id="hf-1", organization="org-a", name="Tamil Corpus"),
        provider_code="huggingface",
    )
    b = strong_signals(
        _metadata(provider_dataset_id="gh-1", organization="org-b", name="Tamil Corpus"),
        provider_code="github",
    )
    assert not is_strong_duplicate(a, b)
    # ...but it is flagged as a *possible* duplicate for human review.
    assert is_possible_duplicate(
        _metadata(organization="org-a", name="Tamil Corpus"),
        _metadata(organization="org-b", name="Tamil Corpus"),
    )


def test_versioned_releases_of_the_same_dataset_share_a_strong_signal() -> None:
    a = strong_signals(
        _metadata(
            provider_dataset_id="ds-v1", organization="org-a", name="Tamil Corpus", version="1.0"
        ),
        provider_code="huggingface",
    )
    b = strong_signals(
        _metadata(
            provider_dataset_id="ds-v2", organization="org-a", name="Tamil Corpus", version="2.0"
        ),
        provider_code="huggingface",
    )
    assert is_strong_duplicate(a, b)


def test_mirror_via_explicit_cross_reference_url_is_detected() -> None:
    original = _metadata(
        provider_dataset_id="hf-1",
        organization="org-a",
        name="Tamil Corpus",
        dataset_card_url="https://huggingface.co/datasets/org-a/tamil-corpus",
    )
    mirror = _metadata(
        provider_dataset_id="gh-mirror",
        organization="mirror-org",
        name="tamil-corpus-mirror",
        homepage_url="https://huggingface.co/datasets/org-a/tamil-corpus",
    )
    original_signals = strong_signals(original, provider_code="huggingface")
    mirror_cross_refs = cross_reference_signals(mirror)
    assert is_cross_referenced(original_signals, mirror_cross_refs)
    # Different org/name -- not a strong duplicate on its own, only via cross-reference.
    mirror_signals = strong_signals(mirror, provider_code="github")
    assert not is_strong_duplicate(original_signals, mirror_signals)


def test_fork_with_different_owner_and_url_is_not_a_strong_duplicate() -> None:
    original = strong_signals(
        _metadata(
            provider_dataset_id="owner/repo",
            organization="owner",
            name="repo",
            repository_url="https://github.com/owner/repo",
        ),
        provider_code="github",
    )
    fork = strong_signals(
        _metadata(
            provider_dataset_id="forker/repo",
            organization="forker",
            name="repo",
            repository_url="https://github.com/forker/repo",
        ),
        provider_code="github",
    )
    assert not is_strong_duplicate(original, fork)
    # Same repo name, different owner -- exactly the "possible duplicate" case.
    assert is_possible_duplicate(
        _metadata(organization="owner", name="repo"), _metadata(organization="forker", name="repo")
    )


def test_renamed_dataset_is_never_falsely_linked() -> None:
    """Phase 10 never uses similarity/LLM guessing -- a rename with no
    shared signal at all is honestly treated as two unrelated
    candidates, never force-merged."""

    old_name = strong_signals(
        _metadata(provider_dataset_id="ds-1", organization="org-a", name="Old Corpus Name"),
        provider_code="huggingface",
    )
    new_name = strong_signals(
        _metadata(provider_dataset_id="ds-1-renamed", organization="org-a", name="New Corpus Name"),
        provider_code="huggingface",
    )
    assert not is_strong_duplicate(old_name, new_name)
    assert not is_possible_duplicate(
        _metadata(organization="org-a", name="Old Corpus Name"),
        _metadata(organization="org-a", name="New Corpus Name"),
    )


def test_multilingual_variants_stay_separate_candidates() -> None:
    """Per-language dataset variants with different exact names must
    never be force-merged just because they're related -- each
    language variant is a genuinely different resource."""

    tamil_variant = strong_signals(
        _metadata(provider_dataset_id="ds-ta", organization="org-a", name="tamil-corpus-ta"),
        provider_code="huggingface",
    )
    english_variant = strong_signals(
        _metadata(provider_dataset_id="ds-en", organization="org-a", name="tamil-corpus-en"),
        provider_code="huggingface",
    )
    assert not is_strong_duplicate(tamil_variant, english_variant)
    assert not is_possible_duplicate(
        _metadata(organization="org-a", name="tamil-corpus-ta"),
        _metadata(organization="org-a", name="tamil-corpus-en"),
    )


def test_normalization_ignores_case_and_whitespace_punctuation() -> None:
    a = strong_signals(
        _metadata(provider_dataset_id="a", organization="  Example-Org  ", name="Tamil   Corpus"),
        provider_code="huggingface",
    )
    b = strong_signals(
        _metadata(provider_dataset_id="b", organization="example org", name="tamil corpus"),
        provider_code="github",
    )
    assert is_strong_duplicate(a, b)
