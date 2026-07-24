"""Phase 15 pure-function package: bounded local inference runtime,
model assignment, canary activation, and safe rollback.

None of this package trains a model or duplicates any existing registry.
It only reasons about already-registered, already-verified release
artifacts (Phase 14) and decides deterministically whether a release may
enter a bounded local runtime, under which scope, and with what limits.
Runtime existence never implies model quality, and loading a model is
never the same as assigning it, and assignment is never the same as
public-chat activation.
"""

from __future__ import annotations

RUNTIME_TYPES = ("local_cpu", "local_gpu")

ALLOWED_DTYPES = ("float32",)

RUNTIME_INSTANCE_STATUSES = (
    "offline",
    "starting",
    "idle",
    "loading",
    "ready",
    "busy",
    "unloading",
    "degraded",
    "failed",
    "stopped",
)

ASSIGNMENT_SCOPES = ("admin_diagnostic", "admin_chat_lab", "internal_canary", "public_chat")

ASSIGNMENT_STATUSES = (
    "draft",
    "validating",
    "approved",
    "active",
    "paused",
    "rolled_back",
    "rejected",
    "expired",
    "archived",
)

COMPATIBILITY_STATUSES = ("compatible", "compatible_with_warnings", "incompatible", "not_assessed")

COMPATIBILITY_DIMENSIONS = (
    "release_integrity",
    "checkpoint_integrity",
    "tokenizer_integrity",
    "vocabulary_compatibility",
    "special_token_compatibility",
    "model_config_compatibility",
    "context_compatibility",
    "dtype_compatibility",
    "device_compatibility",
    "memory_compatibility",
    "disk_compatibility",
    "generation_policy_compatibility",
    "evaluation_policy_compatibility",
    "assignment_scope_compatibility",
)

HEALTH_CHECK_TYPES = (
    "runtime_process",
    "model_loaded",
    "tokenizer_loaded",
    "checkpoint_verified",
    "memory_available",
    "generation_smoke_test",
    "latency_within_limit",
    "special_token_output_safe",
)

HEALTH_STATUSES = ("healthy", "degraded", "unhealthy", "not_checked")

INFERENCE_REQUEST_STATUSES = (
    "accepted",
    "validating",
    "queued",
    "running",
    "completed",
    "completed_with_warning",
    "timed_out",
    "cancelled",
    "failed",
    "rejected",
)

FAILURE_CODES = (
    "release_not_eligible",
    "assignment_not_active",
    "assignment_scope_forbidden",
    "registry_fixture_forbidden",
    "manifest_mismatch",
    "artifact_verification_failed",
    "checkpoint_corrupt",
    "tokenizer_invalid",
    "model_config_mismatch",
    "vocabulary_mismatch",
    "special_token_mismatch",
    "memory_guard_failed",
    "disk_guard_failed",
    "model_load_failed",
    "context_too_long",
    "generation_timeout",
    "generation_cancelled",
    "role_token_leakage",
    "prompt_leakage",
    "unicode_invalid",
    "runtime_busy",
    "runtime_unavailable",
    "fallback_used",
)

APPROVAL_ROLES = ("technical", "evaluation", "security", "release")

APPROVAL_DECISIONS = ("approve", "approve_with_warning", "reject", "request_changes")

ASSIGNMENT_EVENT_TYPES = (
    "created",
    "validated",
    "approved",
    "activated",
    "paused",
    "resumed",
    "canary_started",
    "canary_stopped",
    "fallback_used",
    "rollback_started",
    "rollback_completed",
    "rollback_failed",
    "expired",
    "rejected",
)

SESSION_STATUSES = ("active", "expired", "closed", "failed")

FALLBACK_POLICIES = ("placeholder", "previous_active_assignment", "safe_error")

DECODING_MODES = ("greedy", "top_k_sampling")

CONTEXT_TRUNCATION_POLICIES = (
    "reject",
    "truncate_oldest_history",
    "truncate_system_then_history",
)

REGISTRY_FIXTURE_MARKERS = ("registry_workflow_fixture", "not_production_model")

SCOPE_MINIMUM_READINESS = {
    "admin_diagnostic": frozenset({"evaluation_passed_with_limits", "evaluation_warning"}),
    "admin_chat_lab": frozenset({"evaluation_passed_with_limits"}),
    "internal_canary": frozenset({"evaluation_passed_with_limits"}),
    "public_chat": frozenset({"evaluation_passed_with_limits"}),
}
