"""P0-1: N-distinct-human approval enforcement & explicit self-approval semantics.

Governance decision implemented (see
deploy/repository-audit/BRUD_AI_P0_1_GOVERNANCE_DECISION_PACKET.md, Option B): role
labels (technical/evaluation/security/release) remain descriptive approval
categories, not verified RBAC permissions. Satisfying a multi-role approval
policy now additionally requires that the approvals covering the required roles
come from at least `ApprovalPolicy.minimum_distinct_approvers` distinct
`admin_public_id` identities -- a single admin can no longer satisfy a
multi-role policy by submitting every role themselves.

This file proves, with real (non-mocked) execution:
- the pure policy function's new distinct-approver semantics (Tests 1-8),
- the exact previously-proven exploit now fails (Test 2, the critical
  adversarial regression),
- release self-approval is unchanged (Test 9),
- inference-assignment self-approval is no longer hardcoded-permissive
  (Test 10),
- the new configuration fields are actually respected end-to-end (Test 11),
- approval identity cannot be supplied by a client payload (Test 12),
- approval staleness protection is unaffected (Test 13),
- approval audit metadata is preserved (Test 14).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError as PydanticValidationError

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.base import ValidationError
from backend.database.repositories.inference_runtime import InferenceRuntimeRepository
from backend.database.repositories.model_release import ModelReleaseRepository
from backend.models.inference_runtime import AssignmentApprovalCreate, AssignmentCreate
from backend.models.model_release import ApprovalCreate, ModelReleaseCreate
from backend.services.inference_runtime_service import InferenceRuntimeService
from backend.services.model_assignment_service import ModelAssignmentService
from backend.services.model_release_service import ModelReleaseService
from core_model.release.approval_policy import ApprovalPolicy, is_policy_satisfied
from tests.backend.test_production_model_release_validation_activation import (
    _profile,
    _validated_release_request,
)
from tests.backend.test_training_suitability_and_transformation import ADMIN_ID

ADMIN_A = ADMIN_ID
ADMIN_B = "99999999-0000-0000-0000-000000000002"
ADMIN_C = "99999999-0000-0000-0000-000000000003"
ADMIN_D = "99999999-0000-0000-0000-000000000004"

FOUR_ROLES = ("technical", "evaluation", "security", "release")


def _approval(role: str, admin_public_id: str, decision: str = "approve") -> dict:
    return {"role": role, "decision": decision, "admin_public_id": admin_public_id}


# ---------------------------------------------------------------------------
# Tests 1-8: pure ApprovalPolicy / is_policy_satisfied() semantics
# ---------------------------------------------------------------------------


def test_1_four_distinct_admins_four_roles_satisfied() -> None:
    policy = ApprovalPolicy(required_roles=FOUR_ROLES, minimum_distinct_approvers=4)
    approvals = [
        _approval("technical", ADMIN_A), _approval("evaluation", ADMIN_B),
        _approval("security", ADMIN_C), _approval("release", ADMIN_D),
    ]
    result = is_policy_satisfied(approvals, policy)
    assert result["satisfied"] is True
    assert result["missing_roles"] == []
    assert result["distinct_approver_count"] == 4


def test_2_adversarial_one_admin_four_roles_not_satisfied() -> None:
    """The critical adversarial regression: the exact scenario the prior audit
    proved succeeds today must now fail."""

    policy = ApprovalPolicy(required_roles=FOUR_ROLES, minimum_distinct_approvers=4)
    approvals = [_approval(role, ADMIN_A) for role in FOUR_ROLES]

    result = is_policy_satisfied(approvals, policy)

    assert result["satisfied"] is False
    assert result["missing_roles"] == [], "all 4 roles ARE present -- the gap is identity, not coverage"
    assert result["distinct_approver_count"] == 1
    assert result["minimum_distinct_approvers"] == 4
    assert result["meets_minimum_distinct_approvers"] is False
    assert result["has_rejection"] is False


def test_3_partial_distinctness_a_b_c_c_not_satisfied_for_minimum_four() -> None:
    policy = ApprovalPolicy(required_roles=FOUR_ROLES, minimum_distinct_approvers=4)
    approvals = [
        _approval("technical", ADMIN_A), _approval("evaluation", ADMIN_B),
        _approval("security", ADMIN_C), _approval("release", ADMIN_C),
    ]
    result = is_policy_satisfied(approvals, policy)
    assert result["satisfied"] is False
    assert result["distinct_approver_count"] == 3


def test_4_exact_minimum_three_distinct_satisfied_for_three_role_policy() -> None:
    policy = ApprovalPolicy(
        required_roles=("technical", "evaluation", "security"), minimum_distinct_approvers=3,
    )
    approvals = [
        _approval("technical", ADMIN_A), _approval("evaluation", ADMIN_B),
        _approval("security", ADMIN_C),
    ]
    result = is_policy_satisfied(approvals, policy)
    assert result["satisfied"] is True
    assert result["distinct_approver_count"] == 3


def test_5_missing_role_not_satisfied_even_with_four_distinct_admins() -> None:
    policy = ApprovalPolicy(required_roles=FOUR_ROLES, minimum_distinct_approvers=4)
    approvals = [
        _approval("technical", ADMIN_A), _approval("evaluation", ADMIN_B),
        _approval("security", ADMIN_C),
        # "release" role never submitted, despite 3 distinct admins already present
    ]
    result = is_policy_satisfied(approvals, policy)
    assert result["satisfied"] is False
    assert result["missing_roles"] == ["release"]


def test_6_rejection_not_satisfied_even_with_all_roles_and_distinct_admins() -> None:
    policy = ApprovalPolicy(required_roles=FOUR_ROLES, minimum_distinct_approvers=4)
    approvals = [
        _approval("technical", ADMIN_A), _approval("evaluation", ADMIN_B),
        _approval("security", ADMIN_C), _approval("release", ADMIN_D, decision="reject"),
    ]
    result = is_policy_satisfied(approvals, policy)
    assert result["satisfied"] is False
    assert result["has_rejection"] is True
    # ADMIN_D's rejection is never counted toward distinctness (only approving
    # decisions are) -- this fails on has_rejection, not on an insufficient
    # distinct count; the 3 who actually approved would otherwise be one short
    # of the minimum-4 policy anyway.
    assert result["distinct_approver_count"] == 3


def test_7_warning_approval_still_requires_a_comment() -> None:
    from core_model.release.approval_policy import validate_approval_submission

    policy = ApprovalPolicy(required_roles=("release",), minimum_distinct_approvers=1)
    violations = validate_approval_submission(
        decision="approve_with_warning", comment="", candidate_status_is_blocked=False,
        is_self_approval=False, policy=policy,
    )
    assert "warning_approval_requires_comment" in violations

    violations_with_comment = validate_approval_submission(
        decision="approve_with_warning", comment="acceptable risk, documented",
        candidate_status_is_blocked=False, is_self_approval=False, policy=policy,
    )
    assert violations_with_comment == []


def test_8_latest_by_role_semantics_preserved_with_distinct_counting() -> None:
    """A given role's LATEST submission still wins for role-coverage/decision
    purposes (missing_roles/has_rejection are unchanged, pre-existing
    semantics, driven only by the latest submission per role). Distinct-
    approver counting is a separate, cumulative question and spans every
    *approving* submission for a required role, not only the current one --
    see test_8b for a case where that distinction actually changes the count."""

    policy = ApprovalPolicy(required_roles=FOUR_ROLES, minimum_distinct_approvers=4)
    approvals = [
        _approval("technical", ADMIN_A, decision="reject"),  # superseded, AND a reject -- excluded either way
        _approval("technical", ADMIN_B, decision="approve"),  # latest for "technical"
        _approval("evaluation", ADMIN_C),
        _approval("security", ADMIN_D),
        _approval("release", ADMIN_B),  # ADMIN_B appears again under a different role
    ]
    result = is_policy_satisfied(approvals, policy)
    # latest "technical" is ADMIN_B's approve, not ADMIN_A's stale reject
    assert result["has_rejection"] is False
    assert result["latest_by_role"]["technical"] == "approve"
    # ADMIN_A never counts (their only submission was a reject); B appears
    # under two different roles but only counts once: {B, C, D} = 3
    assert result["distinct_approver_count"] == 3
    assert result["satisfied"] is False  # 3 < minimum 4


def test_8b_superseded_but_approving_submission_still_counts_toward_distinctness() -> None:
    """The precise case that distinguishes 'count only the latest submission
    per role' from 'count every approving submission for a required role':
    ADMIN_A's "technical" approval is later superseded by ADMIN_B's own
    "technical" approval -- role-coverage/decision for "technical" reflects
    only B's (latest) approval, but A's own, still-real, still-approving
    submission continues to count toward distinctness."""

    policy = ApprovalPolicy(required_roles=("technical", "evaluation"), minimum_distinct_approvers=2)
    approvals = [
        _approval("technical", ADMIN_A, decision="approve"),  # superseded, but WAS an approval
        _approval("technical", ADMIN_B, decision="approve"),  # latest for "technical"
        _approval("evaluation", ADMIN_B, decision="approve"),
    ]
    result = is_policy_satisfied(approvals, policy)
    assert result["latest_by_role"]["technical"] == "approve"
    # Only ADMIN_B's submissions are "latest" for either role, but ADMIN_A's
    # own earlier, superseded, approving submission still counts: {A, B} = 2
    assert result["distinct_approver_count"] == 2
    assert result["satisfied"] is True


def test_8c_duplicate_resubmission_from_the_same_admin_does_not_count_twice() -> None:
    """GOV-26 requirement: the same admin resubmitting (even under a
    different decision, or repeatedly) never inflates the distinct count --
    a `set` of admin_public_id is inherently duplicate-free, proven directly."""

    policy = ApprovalPolicy(required_roles=("release",), minimum_distinct_approvers=2)
    approvals = [
        _approval("release", ADMIN_A, decision="approve"),
        _approval("release", ADMIN_A, decision="approve"),  # same admin, resubmitted
        _approval("release", ADMIN_A, decision="approve"),  # same admin, resubmitted again
    ]
    result = is_policy_satisfied(approvals, policy)
    assert result["distinct_approver_count"] == 1
    assert result["satisfied"] is False  # 1 < minimum 2, no matter how many times A resubmits


# ---------------------------------------------------------------------------
# GOV-26b: resolve_minimum_distinct_approvers() -- max(floor, role_count)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("role_count", "expected_minimum"),
    [(1, 2), (2, 2), (3, 3), (4, 4), (5, 5)],
)
def test_gov_26b_minimum_tracks_role_count_with_a_floor_of_2(
    role_count: int, expected_minimum: int,
) -> None:
    from core_model.release.approval_policy import resolve_minimum_distinct_approvers

    required_roles = tuple(f"role-{i}" for i in range(role_count))
    assert resolve_minimum_distinct_approvers(required_roles, floor=2) == expected_minimum


def test_gov_26b_floor_is_never_reduced_below_itself_by_role_count() -> None:
    """Explicit floor-never-lowered proof, independent of the parametrized
    table above: a single required role with a floor of 2 must never
    resolve to anything less than 2."""

    from core_model.release.approval_policy import resolve_minimum_distinct_approvers

    assert resolve_minimum_distinct_approvers(("release",), floor=2) == 2
    assert resolve_minimum_distinct_approvers((), floor=2) == 2


# ---------------------------------------------------------------------------
# Service-level integration tests (real, isolated DB)
# ---------------------------------------------------------------------------


def _settings(tmp_path: Path, **overrides: object) -> Settings:
    settings = Settings(
        database_path=tmp_path / "p0_1.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        tokenizer_corpus_dir=tmp_path / "tokenizer_corpus",
        tokenizer_dir=tmp_path / "tokenizers",
        core_model_dir=tmp_path / "core_models",
        core_checkpoint_dir=tmp_path / "core_models" / "checkpoints",
        release_artifact_dir=tmp_path / "release_artifacts",
        release_bundle_dir=tmp_path / "release_bundles",
        allow_external_storage=True,
        log_level="CRITICAL",
        **overrides,
    )
    initialize_database(settings.resolved_database_path)
    return settings


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return _settings(tmp_path)


def test_9_release_self_approval_creator_identity_comparison_unchanged(tmp_path: Path) -> None:
    """Real, DB-backed proof that the release flow's identity-aware
    self-approval check still works exactly as before this change."""

    settings = _settings(tmp_path, release_allow_self_approval=False)
    request = _validated_release_request(settings)
    release_service = ModelReleaseService(
        ModelReleaseRepository(settings.resolved_database_path), settings
    )
    # ADMIN_ID created the candidate (via _validated_release_request's own
    # internal use of ADMIN_ID) -- submitting under that same identity with
    # self-approval disallowed must be rejected.
    with pytest.raises(ValidationError, match="self_approval_not_allowed"):
        release_service.submit_approval(
            request["model_release_candidate_public_id"],
            ApprovalCreate(role="release", decision="approve", comment="self-approval attempt"),
            ADMIN_ID,
        )


def test_10_inference_assignment_self_approval_no_longer_hardcoded(tmp_path: Path) -> None:
    """Real, DB-backed proof that inference-assignment self-approval is now
    genuinely identity-aware and configuration-controlled, not a hardcoded
    permissive no-op."""

    settings = _settings(tmp_path, inference_assignment_allow_self_approval=False)
    request = _validated_release_request(settings)
    release_service = ModelReleaseService(
        ModelReleaseRepository(settings.resolved_database_path), settings
    )
    # GOV-26's floor of 2 now applies even to the default single-role
    # ("release") policy -- two distinct admins are required before the
    # candidate can be released, not just one. GOV-33: ADMIN_ID is the
    # candidate's own creator (via _validated_release_request) and can
    # never approve it -- both approvals use genuinely non-creator
    # identities; ADMIN_ID is used only for create_release() itself.
    release_service.submit_approval(
        request["model_release_candidate_public_id"],
        ApprovalCreate(role="release", decision="approve", comment="first reviewer"),
        ADMIN_B,
    )
    release_service.submit_approval(
        request["model_release_candidate_public_id"],
        ApprovalCreate(role="release", decision="approve", comment="second reviewer"),
        ADMIN_C,
    )
    release = release_service.create_release(
        ModelReleaseCreate(candidate_public_id=request["model_release_candidate_public_id"], version="v1"), ADMIN_ID,
    )

    runtime_repository = InferenceRuntimeRepository(settings.resolved_database_path)
    release_repository = ModelReleaseRepository(settings.resolved_database_path)
    runtime_service = InferenceRuntimeService(runtime_repository, release_repository, settings)
    assignment_service = ModelAssignmentService(
        runtime_repository, release_repository, runtime_service, settings,
    )
    profile_public_id = _profile(settings)

    from backend.models.inference_runtime import AssignmentCreate as _AC

    assignment = assignment_service.create_assignment(
        _AC(
            scope="admin_diagnostic", release_public_id=release["public_id"],
            runtime_profile_public_id=profile_public_id,
        ),
        ADMIN_ID,  # same admin creates the assignment...
    )
    assignment_service.validate_assignment(assignment["public_id"], ADMIN_ID)

    # ...and then attempts to approve their own assignment -- must now be
    # rejected, proving self-approval detection is real (before this change,
    # is_self_approval was hardcoded True/allow_self_approval hardcoded True,
    # so this call always silently succeeded regardless of any setting).
    with pytest.raises(ValidationError, match="self_approval_not_allowed"):
        assignment_service.approve_assignment(
            assignment["public_id"],
            AssignmentApprovalCreate(role="release", decision="approve", comment="self-approval attempt"),
            ADMIN_ID,
        )


def test_11_configured_minimum_distinct_approvers_is_respected_end_to_end(tmp_path: Path) -> None:
    """Real, DB-backed proof that a configured minimum_distinct_approvers
    value is actually enforced through the full submit_approval ->
    create_release path, not merely in the pure-function tests above."""

    settings = _settings(
        tmp_path, release_required_approval_roles="technical,release",
        release_minimum_distinct_approvers=2,
    )
    request = _validated_release_request(settings)
    release_service = ModelReleaseService(
        ModelReleaseRepository(settings.resolved_database_path), settings
    )
    candidate_public_id = request["model_release_candidate_public_id"]

    # Same (non-creator) admin submits both required roles -- must NOT
    # satisfy the policy, so submit_approval() itself never flips the
    # candidate to "approved" (its own internal is_policy_satisfied() check,
    # mirroring the one in create_release(), fails the distinct-approver
    # requirement). GOV-33: ADMIN_A is the candidate's own creator (via
    # _validated_release_request) and can never approve it -- ADMIN_B is
    # used for both initial submissions instead, so this test continues to
    # isolate the *distinctness* failure from any self-approval failure.
    technical_approval = release_service.submit_approval(
        candidate_public_id,
        ApprovalCreate(role="technical", decision="approve", comment="ok"), ADMIN_B,
    )
    release_approval = release_service.submit_approval(
        candidate_public_id,
        ApprovalCreate(role="release", decision="approve", comment="ok"), ADMIN_B,
    )
    assert technical_approval["admin_public_id"] == ADMIN_B
    assert release_approval["admin_public_id"] == ADMIN_B
    with pytest.raises(ValidationError, match="candidate must be approved before creating a release"):
        release_service.create_release(
            ModelReleaseCreate(candidate_public_id=candidate_public_id, version="v-should-fail"),
            ADMIN_A,
        )

    # A second, distinct (also non-creator) admin now submits the "release"
    # role instead -- policy should become satisfiable.
    release_service.submit_approval(
        candidate_public_id,
        ApprovalCreate(role="release", decision="approve", comment="second reviewer"), ADMIN_C,
    )
    released = release_service.create_release(
        ModelReleaseCreate(candidate_public_id=candidate_public_id, version="v-should-pass"), ADMIN_A,
    )
    assert released["public_id"]


def test_12_approval_identity_cannot_be_supplied_by_client_payload() -> None:
    """ApprovalCreate/AssignmentApprovalCreate use DomainModel's strict
    `extra="forbid"` config -- a client cannot inject an admin_public_id (or
    any other field) into the approval payload; the approving identity is
    only ever the `admin_id` parameter services receive from the
    authenticated AdminContext (backend/api/routes/model_release.py:174,
    backend/api/routes/inference_runtime.py:217, both pass
    `admin.admin.public_id`, never anything from the request body)."""

    with pytest.raises(PydanticValidationError):
        ApprovalCreate(
            role="release", decision="approve", comment="",
            admin_public_id="attacker-supplied-identity",  # type: ignore[call-arg]
        )
    with pytest.raises(PydanticValidationError):
        AssignmentApprovalCreate(
            role="release", decision="approve", comment="",
            admin_public_id="attacker-supplied-identity",  # type: ignore[call-arg]
        )


def test_13_approval_staleness_protection_is_unaffected(settings: Settings) -> None:
    """`is_approval_stale()` was not modified by this change -- a direct,
    real-data proof that an approval recorded against now-superseded
    eligibility evidence is still correctly treated as stale."""

    from core_model.release.approval_policy import is_approval_stale

    assert is_approval_stale(
        approval_eligibility_checksum="old-checksum",
        current_eligibility_checksum="new-checksum",
        approval_manifest_checksum=None, current_manifest_checksum=None,
    ) is True
    assert is_approval_stale(
        approval_eligibility_checksum="same-checksum",
        current_eligibility_checksum="same-checksum",
        approval_manifest_checksum="m1", current_manifest_checksum="m1",
    ) is False


def test_14_approval_audit_metadata_is_preserved(settings: Settings) -> None:
    """Real, DB-backed proof that approval records still retain
    admin_public_id, role, decision, and evidence checksums after this
    change -- the distinct-approver check reads existing persisted columns,
    it does not require or trigger any new/different persistence shape."""

    request = _validated_release_request(settings)
    release_service = ModelReleaseService(
        ModelReleaseRepository(settings.resolved_database_path), settings
    )
    # GOV-33: ADMIN_ID is the candidate's own creator (via
    # _validated_release_request) and can never approve it -- ADMIN_B is
    # used instead; this test is about persisted metadata, not identity,
    # so any real non-creator admin proves the same thing.
    release_service.submit_approval(
        request["model_release_candidate_public_id"],
        ApprovalCreate(role="release", decision="approve", comment="ok"), ADMIN_B,
    )
    approvals = release_service.approvals_for_candidate(request["model_release_candidate_public_id"])["items"]
    assert len(approvals) == 1
    row = approvals[0]
    assert row["admin_public_id"] == ADMIN_B
    assert row["role"] == "release"
    assert row["decision"] == "approve"
    assert row["eligibility_checksum_sha256"]


# ---------------------------------------------------------------------------
# GOV-26: real, DB-backed proof against the actual default configuration
# (release_minimum_distinct_approvers=2, release_required_approval_roles
# still just ("release",) -- unchanged, out of scope this phase)
# ---------------------------------------------------------------------------


def test_gov_26_one_approval_is_insufficient_under_the_real_default_config(tmp_path: Path) -> None:
    settings = _settings(tmp_path)  # no overrides -- exercises the real, shipped defaults
    request = _validated_release_request(settings)
    release_service = ModelReleaseService(
        ModelReleaseRepository(settings.resolved_database_path), settings
    )
    candidate_public_id = request["model_release_candidate_public_id"]

    # GOV-33: ADMIN_A is the candidate's own creator and can never approve
    # it -- ADMIN_B (non-creator) submits instead.
    release_service.submit_approval(
        candidate_public_id,
        ApprovalCreate(role="release", decision="approve", comment="ok"), ADMIN_B,
    )
    with pytest.raises(ValidationError, match="candidate must be approved before creating a release"):
        release_service.create_release(
            ModelReleaseCreate(candidate_public_id=candidate_public_id, version="v-should-fail"),
            ADMIN_A,
        )


def test_gov_26_two_distinct_admins_are_sufficient_under_the_real_default_config(tmp_path: Path) -> None:
    settings = _settings(tmp_path)  # no overrides
    request = _validated_release_request(settings)
    release_service = ModelReleaseService(
        ModelReleaseRepository(settings.resolved_database_path), settings
    )
    candidate_public_id = request["model_release_candidate_public_id"]

    # GOV-33: ADMIN_A is the candidate's own creator -- both approvals use
    # genuinely non-creator identities (ADMIN_B, ADMIN_C); ADMIN_A is used
    # only for create_release() itself.
    release_service.submit_approval(
        candidate_public_id,
        ApprovalCreate(role="release", decision="approve", comment="first reviewer"), ADMIN_B,
    )
    release_service.submit_approval(
        candidate_public_id,
        ApprovalCreate(role="release", decision="approve", comment="second reviewer"), ADMIN_C,
    )
    released = release_service.create_release(
        ModelReleaseCreate(candidate_public_id=candidate_public_id, version="v-should-pass"), ADMIN_A,
    )
    assert released["public_id"]


def test_gov_26_duplicate_resubmission_by_the_same_admin_does_not_count_twice_end_to_end(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    request = _validated_release_request(settings)
    release_service = ModelReleaseService(
        ModelReleaseRepository(settings.resolved_database_path), settings
    )
    candidate_public_id = request["model_release_candidate_public_id"]

    # GOV-33: ADMIN_A is the candidate's own creator and can never approve
    # it -- ADMIN_B (non-creator) resubmits their own "release" approval a
    # second time -- still only one distinct identity, still insufficient
    # against the floor of 2.
    release_service.submit_approval(
        candidate_public_id,
        ApprovalCreate(role="release", decision="approve", comment="first"), ADMIN_B,
    )
    release_service.submit_approval(
        candidate_public_id,
        ApprovalCreate(role="release", decision="approve", comment="resubmitted"), ADMIN_B,
    )
    with pytest.raises(ValidationError, match="candidate must be approved before creating a release"):
        release_service.create_release(
            ModelReleaseCreate(candidate_public_id=candidate_public_id, version="v-should-still-fail"),
            ADMIN_A,
        )


# ---------------------------------------------------------------------------
# GOV-26c: non-public inference-assignment scopes share one minimum (2)
# ---------------------------------------------------------------------------


def _released_and_profiled(settings: Settings) -> tuple[dict, str]:
    """Real release (2 distinct approvers, matching the real GOV-26 default)
    plus a real runtime profile -- shared setup for the inference-assignment
    tests below.

    GOV-33 (Phase 15.2): `_validated_release_request()` always creates the
    candidate with ADMIN_A (=ADMIN_ID) as its creator -- ADMIN_A can
    therefore never submit an approval for it. Both approvals here use
    genuinely non-creator identities (ADMIN_B, ADMIN_C); ADMIN_A is used
    only for the final create_release() call, which does not itself check
    self-approval."""

    request = _validated_release_request(settings)
    release_service = ModelReleaseService(
        ModelReleaseRepository(settings.resolved_database_path), settings
    )
    candidate_public_id = request["model_release_candidate_public_id"]
    release_service.submit_approval(
        candidate_public_id,
        ApprovalCreate(role="release", decision="approve", comment="first reviewer"), ADMIN_B,
    )
    release_service.submit_approval(
        candidate_public_id,
        ApprovalCreate(role="release", decision="approve", comment="second reviewer"), ADMIN_C,
    )
    release = release_service.create_release(
        ModelReleaseCreate(candidate_public_id=candidate_public_id, version="v-gov26c"), ADMIN_A,
    )
    profile_public_id = _profile(settings)
    return release, profile_public_id


def _assignment_service_for(settings: Settings) -> ModelAssignmentService:
    runtime_repository = InferenceRuntimeRepository(settings.resolved_database_path)
    release_repository = ModelReleaseRepository(settings.resolved_database_path)
    runtime_service = InferenceRuntimeService(runtime_repository, release_repository, settings)
    return ModelAssignmentService(runtime_repository, release_repository, runtime_service, settings)


def test_gov_26c_one_approval_is_insufficient_for_a_non_public_scope(tmp_path: Path) -> None:
    settings = _settings(tmp_path)  # no overrides -- real default of 2
    release, profile_public_id = _released_and_profiled(settings)
    assignment_service = _assignment_service_for(settings)

    assignment = assignment_service.create_assignment(
        AssignmentCreate(
            scope="admin_diagnostic", release_public_id=release["public_id"],
            runtime_profile_public_id=profile_public_id,
        ),
        ADMIN_C,  # a third, distinct admin creates the assignment (not a self-approval test)
    )
    assignment_service.validate_assignment(assignment["public_id"], ADMIN_C)

    result = assignment_service.approve_assignment(
        assignment["public_id"],
        AssignmentApprovalCreate(role="release", decision="approve", comment="only reviewer"),
        ADMIN_D,
    )
    assert result["status"] != "approved"  # one distinct approver is not enough


def test_gov_26c_two_distinct_admins_are_sufficient_for_a_non_public_scope(tmp_path: Path) -> None:
    settings = _settings(tmp_path)  # no overrides -- real default of 2
    release, profile_public_id = _released_and_profiled(settings)
    assignment_service = _assignment_service_for(settings)

    assignment = assignment_service.create_assignment(
        AssignmentCreate(
            scope="admin_diagnostic", release_public_id=release["public_id"],
            runtime_profile_public_id=profile_public_id,
        ),
        ADMIN_C,
    )
    assignment_service.validate_assignment(assignment["public_id"], ADMIN_C)

    assignment_service.approve_assignment(
        assignment["public_id"],
        AssignmentApprovalCreate(role="release", decision="approve", comment="first reviewer"),
        ADMIN_D,
    )
    result = assignment_service.approve_assignment(
        assignment["public_id"],
        AssignmentApprovalCreate(role="release", decision="approve", comment="second reviewer"),
        ADMIN_A,
    )
    assert result["status"] == "approved"


# ---------------------------------------------------------------------------
# GOV-31 / GOV-32: inference-assignment self-approval prohibited by default
# ---------------------------------------------------------------------------


def test_gov_32_default_configuration_value_is_false() -> None:
    """The shipped source-level default, with no environment override at all."""

    assert Settings.model_fields["inference_assignment_allow_self_approval"].default is False


def test_gov_31_creator_self_approval_is_rejected_under_the_real_default_config(
    tmp_path: Path,
) -> None:
    """No explicit `inference_assignment_allow_self_approval` override --
    relies entirely on the new shipped default (False) to reject a real
    self-approval attempt."""

    settings = _settings(tmp_path)  # no overrides
    release, profile_public_id = _released_and_profiled(settings)
    assignment_service = _assignment_service_for(settings)

    assignment = assignment_service.create_assignment(
        AssignmentCreate(
            scope="admin_diagnostic", release_public_id=release["public_id"],
            runtime_profile_public_id=profile_public_id,
        ),
        ADMIN_C,
    )
    assignment_service.validate_assignment(assignment["public_id"], ADMIN_C)

    with pytest.raises(ValidationError, match="self_approval_not_allowed"):
        assignment_service.approve_assignment(
            assignment["public_id"],
            AssignmentApprovalCreate(role="release", decision="approve", comment="self-approval attempt"),
            ADMIN_C,  # same admin who created the assignment
        )


def test_gov_31_legitimate_non_self_approval_remains_functional_under_the_real_default_config(
    tmp_path: Path,
) -> None:
    """The other side of GOV-31: a genuinely distinct admin approving
    someone else's assignment must still work normally -- self-approval
    prohibition must not accidentally block legitimate approvals."""

    settings = _settings(tmp_path)  # no overrides
    release, profile_public_id = _released_and_profiled(settings)
    assignment_service = _assignment_service_for(settings)

    assignment = assignment_service.create_assignment(
        AssignmentCreate(
            scope="admin_diagnostic", release_public_id=release["public_id"],
            runtime_profile_public_id=profile_public_id,
        ),
        ADMIN_C,
    )
    assignment_service.validate_assignment(assignment["public_id"], ADMIN_C)

    # ADMIN_D (not the creator) approves -- must not raise self_approval_not_allowed.
    # Still needs a second distinct approver (GOV-26c, floor of 2) to fully
    # satisfy the policy, so this call alone is expected to succeed without
    # a self-approval violation, even though the assignment isn't "approved" yet.
    result = assignment_service.approve_assignment(
        assignment["public_id"],
        AssignmentApprovalCreate(role="release", decision="approve", comment="legitimate reviewer"),
        ADMIN_D,
    )
    assert result["status"] != "rejected"


# ---------------------------------------------------------------------------
# GOV-33: absolute, non-overridable creator self-approval prohibition
# (release + inference-assignment)
# ---------------------------------------------------------------------------


def test_gov_33_release_self_approval_rejected_even_with_allow_self_approval_true(
    tmp_path: Path,
) -> None:
    """GOV-33 is absolute: an explicit release_allow_self_approval=True
    override must not permit the candidate's own creator to approve it --
    the opposite of Phase 15.1's own release_allow_self_approval=False test."""

    settings = _settings(tmp_path, release_allow_self_approval=True)
    request = _validated_release_request(settings)
    release_service = ModelReleaseService(
        ModelReleaseRepository(settings.resolved_database_path), settings
    )
    with pytest.raises(ValidationError, match="self_approval_not_allowed"):
        release_service.submit_approval(
            request["model_release_candidate_public_id"],
            ApprovalCreate(role="release", decision="approve", comment="self-approval attempt"),
            ADMIN_ID,
        )


def test_gov_33_inference_assignment_self_approval_rejected_even_with_allow_self_approval_true(
    tmp_path: Path,
) -> None:
    """GOV-33 is absolute: an explicit
    inference_assignment_allow_self_approval=True override must not permit
    the assignment's own creator to approve it -- the opposite of Phase
    15.1's own inference_assignment_allow_self_approval=False test."""

    settings = _settings(tmp_path, inference_assignment_allow_self_approval=True)
    release, profile_public_id = _released_and_profiled(settings)
    assignment_service = _assignment_service_for(settings)

    assignment = assignment_service.create_assignment(
        AssignmentCreate(
            scope="admin_diagnostic", release_public_id=release["public_id"],
            runtime_profile_public_id=profile_public_id,
        ),
        ADMIN_C,
    )
    assignment_service.validate_assignment(assignment["public_id"], ADMIN_C)

    with pytest.raises(ValidationError, match="self_approval_not_allowed"):
        assignment_service.approve_assignment(
            assignment["public_id"],
            AssignmentApprovalCreate(role="release", decision="approve", comment="self-approval attempt"),
            ADMIN_C,  # same admin who created the assignment
        )


def test_gov_33_pure_function_ignores_allow_self_approval_in_both_directions() -> None:
    """Direct, isolated proof at the policy-function level: `allow_self_approval`
    no longer has any effect on the self-approval outcome, whether True or False."""

    from core_model.release.approval_policy import validate_approval_submission

    for allow_value in (True, False):
        violations = validate_approval_submission(
            decision="approve", comment="", candidate_status_is_blocked=False,
            is_self_approval=True,
            policy=ApprovalPolicy(allow_self_approval=allow_value),
        )
        assert "self_approval_not_allowed" in violations, f"allow_self_approval={allow_value}"

    # Non-self-approval is, as always, unaffected by this check either way.
    for allow_value in (True, False):
        violations = validate_approval_submission(
            decision="approve", comment="", candidate_status_is_blocked=False,
            is_self_approval=False,
            policy=ApprovalPolicy(allow_self_approval=allow_value),
        )
        assert "self_approval_not_allowed" not in violations
