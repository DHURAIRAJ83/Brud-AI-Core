"""MB-21: Evidence Bundle Builder -- pure assembly only. Packages every
earlier stage's already-computed output into the structured evidence
package the admin reviews. Only hashes of raw provider text are
included by default -- the full raw text is included only when the
caller explicitly marks a provider run as retained (mirroring the
`raw_response_retained` flag already recorded per provider run in the
database), never silently.
"""

from __future__ import annotations

from typing import Any


def build_evidence_bundle(
    *, sanitized_prompt_record: dict[str, Any], provider_runs: list[dict[str, Any]],
    normalized_responses: list[dict[str, Any]], agreement_report: dict[str, Any],
    failure_report: dict[str, Any], safety_report: dict[str, Any], suggested_follow_up_actions: list[str],
) -> dict[str, Any]:
    provider_metadata = [
        {
            "provider_key": run["provider_key"], "status": run["status"],
            "response_hash_sha256": run.get("response_hash"), "raw_response_retained": run.get("raw_response_retained", False),
            "raw_response_text": run.get("normalized_response", {}).get("normalized_text") if run.get("raw_response_retained") else None,
            "latency_ms": run.get("latency_ms"),
        }
        for run in provider_runs
    ]

    return {
        "sanitized_prompt": sanitized_prompt_record.get("sanitized_prompt"),
        "sanitized_prompt_hash_sha256": sanitized_prompt_record.get("sanitized_hash_sha256"),
        "original_prompt_hash_sha256": sanitized_prompt_record.get("original_hash_sha256"),
        "privacy_audit": sanitized_prompt_record.get("privacy_audit", {}),
        "provider_metadata": provider_metadata,
        "normalized_responses": normalized_responses,
        "agreement_analysis": agreement_report,
        "detected_failures": failure_report,
        "detected_safety_issues": safety_report,
        "suggested_follow_up_actions": suggested_follow_up_actions,
        "retention_note": (
            "raw provider response text is included only for provider runs an admin explicitly "
            "marked for retention -- every other provider run carries a hash only"
        ),
        "disclosure": "this bundle is untrusted candidate evidence -- nothing here has been verified or approved",
    }
