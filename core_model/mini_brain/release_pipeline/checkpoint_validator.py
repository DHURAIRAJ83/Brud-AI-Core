"""MB-07: Checkpoint Validator -- pure. Decides whether an already
-promoted checkpoint is safe to convert, from facts the service layer
already gathered (never re-derives them): does it exist, is it
readable, is its recorded metadata sane, and does its tensor set match
the architecture the release was promoted under.
"""

from __future__ import annotations

from typing import Any

VALID_CHECKPOINT_STATUSES = {"completed", "verified"}


def validate_checkpoint(
    *,
    artifact_exists: bool,
    artifact_path_confined: bool,
    artifact_size_ok: bool,
    artifact_checksum_matches: bool | None,
    checkpoint_row: dict[str, Any] | None,
    load_error: str | None,
    state_dict_keys: list[str] | None,
    expected_tensor_keys: list[str],
) -> dict[str, Any]:
    checks: dict[str, bool] = {}
    reasons: list[str] = []

    checks["exists"] = artifact_exists and artifact_path_confined
    if not checks["exists"]:
        reasons.append("checkpoint directory does not exist or is outside the approved artifact root")

    checks["metadata_present"] = checkpoint_row is not None
    if checkpoint_row is None:
        reasons.append("no checkpoint metadata row found")
    else:
        status_ok = checkpoint_row.get("status") in VALID_CHECKPOINT_STATUSES
        checks["metadata_status_valid"] = status_ok
        if not status_ok:
            reasons.append(f"checkpoint status is {checkpoint_row.get('status')!r}, not completed/verified")

    checks["size_ok"] = artifact_size_ok
    if not artifact_size_ok:
        reasons.append("checkpoint artifact size is zero or exceeds the configured maximum")

    checks["checksum_matches"] = bool(artifact_checksum_matches)
    if not artifact_checksum_matches:
        reasons.append("checkpoint checksum could not be verified")

    checks["readable"] = load_error is None and state_dict_keys is not None
    if load_error is not None:
        reasons.append(f"checkpoint failed to load: {load_error}")

    if state_dict_keys is not None:
        actual = set(state_dict_keys)
        expected = set(expected_tensor_keys)
        checks["tensor_keys_match_architecture"] = actual == expected
        if actual != expected:
            missing = sorted(expected - actual)
            unexpected = sorted(actual - expected)
            reasons.append(
                f"checkpoint tensors do not match the expected architecture "
                f"(missing={missing[:5]}, unexpected={unexpected[:5]})"
            )
    else:
        checks["tensor_keys_match_architecture"] = False

    valid = all(checks.values())
    return {
        "status": "Valid" if valid else "Invalid",
        "checks": checks,
        "reasons": reasons,
    }
