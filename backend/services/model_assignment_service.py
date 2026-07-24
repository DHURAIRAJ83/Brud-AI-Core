"""Phase 15 model-assignment lifecycle: versioned scope-specific
assignment of an already-released model into the bounded inference
runtime, admin diagnostics/chat-lab, controlled canary, and
metadata-level assignment rollback.

Composes `InferenceRuntimeService` (runtime profiles/instances/loading/
generation) and the Phase 14 release registry — this module never loads
a model itself; it only decides whether a release may be assigned to a
scope, and asks the runtime service to do the loading and generation.
No assignment here ever touches the public `/api/chat` endpoint.
"""

from __future__ import annotations

import hashlib
from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import NotFoundError, ValidationError
from backend.database.repositories.inference_runtime import (
    InferenceRuntimeRepository,
    public_row,
)
from backend.database.repositories.model_release import ModelReleaseRepository
from backend.models.inference_runtime import (
    AssignmentApprovalCreate,
    AssignmentCreate,
    AssignmentPatch,
    CanaryStartRequest,
    ChatLabSessionCreate,
    DiagnosticGenerateRequest,
    RollbackPreviewRequest,
)
from backend.services.inference_runtime_service import InferenceRuntimeService
from core_model.inference_runtime import ASSIGNMENT_SCOPES
from core_model.inference_runtime.assignment_policy import (
    AssignmentEligibilityResult,
    PublicActivationThresholds,
    assess_assignment_eligibility,
    assess_public_activation_gate,
)
from core_model.inference_runtime.canary import (
    CanaryThresholds,
    assess_canary_stop,
    compute_canary_metrics,
    stable_routing_key,
)
from core_model.inference_runtime.context_builder import ConversationTurn, build_context
from core_model.inference_runtime.fallback import build_fallback_event, decide_fallback
from core_model.inference_runtime.generation_config import (
    GenerationConfig,
    validate_generation_config,
)
from core_model.release.approval_policy import (
    ApprovalPolicy,
    is_policy_satisfied,
    validate_approval_submission,
)
from core_model.release.manifest import manifest_checksum, scan_for_sensitive_content

DIAGNOSTIC_DISCLAIMER = (
    "Admin-only diagnostic generation. This output is not from the public chatbot."
)
PUBLIC_ACTIVATION_NOTICE = (
    "Public-chat activation requires an eligible release, passing evaluation evidence, "
    "runtime health, canary success, approvals, and rollback readiness."
)


class ModelAssignmentService:
    def __init__(
        self,
        repository: InferenceRuntimeRepository,
        release_repository: ModelReleaseRepository,
        runtime_service: InferenceRuntimeService,
        settings: Settings,
    ) -> None:
        self.repository = repository
        self.release_repository = release_repository
        self.runtime_service = runtime_service
        self.settings = settings

    # --- scopes -----------------------------------------------------

    def list_scopes(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            self.repository.ensure_default_scopes(connection)
            return {"items": [public_row(row) for row in self.repository.list_scopes(connection)]}

    # --- assignment eligibility gathering -----------------------------------------------------

    def _eligibility_for(
        self,
        connection,
        *,
        scope: str,
        release_public_id: str,
        acknowledge_evaluation_warning: bool,
        acknowledge_missing_human_review: bool = False,
    ) -> tuple[AssignmentEligibilityResult, dict[str, Any]]:
        facts = self.runtime_service.gather_release_facts(connection, release_public_id)
        release = facts["release"]
        result = assess_assignment_eligibility(
            scope=scope,
            release_status=release["status"],
            deployment_eligibility=release["deployment_eligibility"],
            evaluation_status=facts["evaluation_status"],
            manifest_verified=facts["manifest_verified"],
            artifacts_verified=facts["artifacts_verified"],
            checkpoint_verified=facts["checkpoint_structurally_present"],
            tokenizer_verified=facts["tokenizer_verified"],
            model_config_matches=facts["model_config_matches"],
            has_blocking_release_issue=facts["has_blocking_release_issue"],
            is_registry_fixture=facts["is_registry_fixture"],
            allow_registry_fixture_diagnostics=(
                self.settings.inference_allow_registry_fixture_diagnostics
            ),
            acknowledged_evaluation_warning=acknowledge_evaluation_warning,
            acknowledged_missing_human_review=acknowledge_missing_human_review,
        )
        return result, facts

    @staticmethod
    def _checksum(payload: dict[str, Any]) -> str:
        return hashlib.sha256(dumps_json(payload).encode("utf-8")).hexdigest()

    # --- assignments -----------------------------------------------------

    def create_assignment(self, payload: AssignmentCreate, admin_id: str) -> dict[str, Any]:
        if payload.scope not in ASSIGNMENT_SCOPES:
            raise ValidationError(f"scope must be one of {ASSIGNMENT_SCOPES}")
        with self.repository.transaction() as connection:
            self.repository.ensure_default_scopes(connection)
            scope_row = self.repository.scope_by_key(connection, payload.scope)
            release = self.release_repository.release(connection, payload.release_public_id)
            profile = self.repository.profile(connection, payload.runtime_profile_public_id)

            generation_config = GenerationConfig(**{
                key: value
                for key, value in payload.generation_config.items()
                if key in GenerationConfig.__dataclass_fields__
            })
            errors = validate_generation_config(
                generation_config,
                scope=payload.scope,
                profile_maximum_new_tokens=profile["maximum_new_tokens"],
                profile_maximum_context_length=profile["maximum_context_length"],
            )
            if errors:
                raise ValidationError("; ".join(errors))

            public_id = self.repository.create_assignment(
                connection,
                {
                    "model_assignment_scope_id": scope_row["id"],
                    "model_release_id": release["id"],
                    "inference_runtime_profile_id": profile["id"],
                    "generation_config_json": dumps_json(payload.generation_config),
                    "context_policy_json": dumps_json(payload.context_policy),
                    "fallback_policy_json": dumps_json(payload.fallback_policy),
                    "canary_percentage": payload.canary_percentage,
                    "start_at": payload.start_at,
                    "expire_at": payload.expire_at,
                    "created_by_admin_public_id": admin_id,
                },
            )
            self.repository.record_event(
                connection,
                {
                    "model_assignment_id": self.repository.assignment(connection, public_id)["id"],
                    "event_type": "created",
                    "actor_admin_public_id": admin_id,
                },
            )
            self._audit(connection, "inference_assignment_created", admin_id, public_id)
            return public_row(self.repository.assignment(connection, public_id))

    def list_assignments(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return {
                "items": [public_row(row) for row in self.repository.list_assignments(connection)]
            }

    def get_assignment(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.assignment(connection, public_id))

    def patch_assignment(
        self, public_id: str, payload: AssignmentPatch, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            assignment = self.repository.assignment(connection, public_id)
            if assignment["status"] not in {"draft", "active", "paused"}:
                raise ValidationError(
                    "assignment configuration can only change while draft, active, or paused"
                )
            fields: dict[str, Any] = {}
            reopen_for_revalidation = assignment["status"] != "draft"
            if payload.release_public_id is not None:
                release = self.release_repository.release(connection, payload.release_public_id)
                fields["model_release_id"] = release["id"]
            if payload.generation_config is not None:
                fields["generation_config_json"] = dumps_json(payload.generation_config)
            if payload.context_policy is not None:
                fields["context_policy_json"] = dumps_json(payload.context_policy)
            if payload.fallback_policy is not None:
                fields["fallback_policy_json"] = dumps_json(payload.fallback_policy)
            if payload.canary_percentage is not None:
                fields["canary_percentage"] = payload.canary_percentage
            if reopen_for_revalidation:
                # Configuration is immutable once approved; changing it while
                # active/paused reopens the assignment for a fresh validate ->
                # approve cycle, which produces a new immutable version — the
                # prior version's evidence is never deleted or overwritten.
                fields["status"] = "draft"
            self.repository.update_assignment(connection, assignment["id"], fields)
            self._audit(connection, "inference_assignment_updated", admin_id, public_id)
            return public_row(self.repository.assignment(connection, public_id))

    def validate_assignment(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            assignment = self.repository.assignment(connection, public_id)
            if assignment["status"] not in {"draft", "rejected"}:
                raise ValidationError("assignment must be draft (or rejected) to validate")
            context_policy = loads_json(assignment["context_policy_json"])
            result, facts = self._eligibility_for(
                connection,
                scope=assignment["scope_key"],
                release_public_id=assignment["release_public_id"],
                acknowledge_evaluation_warning=bool(
                    context_policy.get("acknowledge_evaluation_warning")
                ),
                acknowledge_missing_human_review=bool(
                    context_policy.get("acknowledge_missing_human_review")
                ),
            )
            compatibility_row = self.repository.latest_compatibility(
                connection,
                assignment["model_release_id"],
                assignment["inference_runtime_profile_id"],
            )
            compatibility_checksum = (
                compatibility_row["compatibility_checksum_sha256"] if compatibility_row else ""
            )
            eligibility_checksum = self._checksum(
                {"blocking": result.blocking_reasons, "warnings": result.warnings}
            )
            new_status = "validating" if result.eligible else "rejected"
            self.repository.update_assignment(connection, assignment["id"], {"status": new_status})
            self.repository.record_event(
                connection,
                {
                    "model_assignment_id": assignment["id"],
                    "event_type": "validated" if result.eligible else "rejected",
                    "details_json": dumps_json(
                        {"blocking_reasons": result.blocking_reasons, "warnings": result.warnings}
                    ),
                    "actor_admin_public_id": admin_id,
                },
            )
            self._audit(
                connection, "inference_assignment_validated", admin_id, public_id,
                eligible=result.eligible,
            )
            return {
                "eligible": result.eligible,
                "blocking_reasons": result.blocking_reasons,
                "warnings": result.warnings,
                "eligibility_checksum_sha256": eligibility_checksum,
                "compatibility_checksum_sha256": compatibility_checksum,
                "assignment": public_row(self.repository.assignment(connection, public_id)),
            }

    def approve_assignment(
        self, public_id: str, payload: AssignmentApprovalCreate, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            assignment = self.repository.assignment(connection, public_id)
            if assignment["status"] != "validating":
                raise ValidationError("assignment must be validating to record an approval")
            context_policy = loads_json(assignment["context_policy_json"])
            result, facts = self._eligibility_for(
                connection,
                scope=assignment["scope_key"],
                release_public_id=assignment["release_public_id"],
                acknowledge_evaluation_warning=bool(
                    context_policy.get("acknowledge_evaluation_warning")
                ),
                acknowledge_missing_human_review=bool(
                    context_policy.get("acknowledge_missing_human_review")
                ),
            )
            violations = validate_approval_submission(
                decision=payload.decision,
                comment=payload.comment,
                candidate_status_is_blocked=not result.eligible,
                is_self_approval=True,
                policy=ApprovalPolicy(allow_self_approval=True),
            )
            if violations:
                raise ValidationError("; ".join(violations))

            compatibility_row = self.repository.latest_compatibility(
                connection,
                assignment["model_release_id"],
                assignment["inference_runtime_profile_id"],
            )
            eligibility_checksum = self._checksum(
                {"blocking": result.blocking_reasons, "warnings": result.warnings}
            )
            compatibility_checksum = (
                compatibility_row["compatibility_checksum_sha256"] if compatibility_row else ""
            )
            self.repository.record_approval(
                connection,
                {
                    "model_assignment_id": assignment["id"],
                    "admin_public_id": admin_id,
                    "role": payload.role,
                    "decision": payload.decision,
                    "comment": payload.comment,
                    "eligibility_checksum_sha256": eligibility_checksum,
                    "compatibility_checksum_sha256": compatibility_checksum,
                },
            )
            if payload.decision in {"reject", "request_changes"}:
                self.repository.update_assignment(
                    connection, assignment["id"], {"status": "rejected"}
                )
                self.repository.record_event(
                    connection,
                    {
                        "model_assignment_id": assignment["id"],
                        "event_type": "rejected",
                        "actor_admin_public_id": admin_id,
                    },
                )
                return public_row(self.repository.assignment(connection, public_id))

            required_roles = (
                self.settings.inference_required_public_approval_roles_list
                if assignment["scope_key"] == "public_chat"
                else ("release",)
            )
            approvals = [
                dict(row)
                for row in self.repository.approvals_for_assignment(connection, assignment["id"])
            ]
            policy_result = is_policy_satisfied(
                approvals, ApprovalPolicy(required_roles=required_roles)
            )
            if policy_result["satisfied"]:
                version_public_id = self.repository.create_version(
                    connection,
                    {
                        "model_assignment_id": assignment["id"],
                        "model_release_id": assignment["model_release_id"],
                        "inference_runtime_profile_id": assignment["inference_runtime_profile_id"],
                        "generation_config_json": assignment["generation_config_json"],
                        "context_policy_json": assignment["context_policy_json"],
                        "fallback_policy_json": assignment["fallback_policy_json"],
                        "canary_percentage": assignment["canary_percentage"],
                        "eligibility_checksum_sha256": eligibility_checksum,
                        "compatibility_checksum_sha256": compatibility_checksum,
                        "approval_checksum_sha256": self._checksum(policy_result),
                        "created_by_admin_public_id": admin_id,
                    },
                )
                self.repository.update_assignment(
                    connection,
                    assignment["id"],
                    {"status": "approved", "current_version_public_id": version_public_id},
                )
                self.repository.record_event(
                    connection,
                    {
                        "model_assignment_id": assignment["id"],
                        "event_type": "approved",
                        "actor_admin_public_id": admin_id,
                    },
                )
            self._audit(
                connection, "inference_assignment_approval_recorded", admin_id, public_id,
                satisfied=policy_result["satisfied"],
            )
            return public_row(self.repository.assignment(connection, public_id))

    def activate_assignment(
        self, public_id: str, admin_id: str, *, explicit_activation_confirmed: bool = False
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            assignment = self.repository.assignment(connection, public_id)
            if assignment["status"] not in {"approved", "paused"}:
                raise ValidationError("assignment must be approved or paused to activate")

            if assignment["scope_key"] == "public_chat":
                gate_result = self._public_activation_gate(
                    connection, assignment, explicit_activation_confirmed
                )
                if not gate_result.activated:
                    self.repository.record_event(
                        connection,
                        {
                            "model_assignment_id": assignment["id"],
                            "event_type": "rejected",
                            "details_json": dumps_json({"reasons": gate_result.rejection_reasons}),
                            "actor_admin_public_id": admin_id,
                        },
                    )
                    return {
                        "activated": False,
                        "rejection_reasons": gate_result.rejection_reasons,
                        "assignment": public_row(self.repository.assignment(connection, public_id)),
                    }

            self.repository.update_assignment(connection, assignment["id"], {"status": "active"})
            self.repository.record_event(
                connection,
                {
                    "model_assignment_id": assignment["id"],
                    "event_type": "activated",
                    "actor_admin_public_id": admin_id,
                },
            )
            self._audit(connection, "inference_assignment_activated", admin_id, public_id)
            return {
                "activated": True,
                "rejection_reasons": [],
                "assignment": public_row(self.repository.assignment(connection, public_id)),
            }

    def _public_activation_gate(self, connection, assignment, explicit_activation_confirmed: bool):
        context_policy = loads_json(assignment["context_policy_json"])
        result, facts = self._eligibility_for(
            connection,
            scope="public_chat",
            release_public_id=assignment["release_public_id"],
            acknowledge_evaluation_warning=bool(
                context_policy.get("acknowledge_evaluation_warning")
            ),
        )
        compatibility_row = self.repository.latest_compatibility(
            connection, assignment["model_release_id"], assignment["inference_runtime_profile_id"]
        )
        canary_row = self.repository.latest_canary_run(connection, assignment["id"])
        canary_metrics = loads_json(canary_row["metrics_json"]) if canary_row else {}
        requests = self.repository.requests_for_assignment(connection, assignment["id"])
        diagnostics_ok = any(
            r["scope"] == "admin_diagnostic" and r["status"] == "completed" for r in requests
        )
        approvals = [
            dict(row)
            for row in self.repository.approvals_for_assignment(connection, assignment["id"])
        ]
        policy_result = is_policy_satisfied(
            approvals,
            ApprovalPolicy(required_roles=self.settings.inference_required_public_approval_roles_list),
        )
        release = facts["release"]
        rollback_target_available = self.repository.latest_version(
            connection, assignment["id"]
        ) is not None
        thresholds = PublicActivationThresholds(
            max_prompt_leakage_rate=self.settings.inference_canary_max_prompt_leakage_rate,
            max_role_leakage_rate=self.settings.inference_canary_max_role_leakage_rate,
            max_duplicate_output_rate=self.settings.inference_canary_max_duplicate_rate,
        )
        return assess_public_activation_gate(
            scope="public_chat",
            assignment_eligibility=result,
            deployment_eligibility=release["deployment_eligibility"],
            evaluation_status=facts["evaluation_status"],
            has_unresolved_safety_issue=facts["has_blocking_release_issue"],
            prompt_leakage_rate=canary_metrics.get("prompt_leakage_rate"),
            role_leakage_rate=canary_metrics.get("role_leakage_rate"),
            duplicate_output_rate=canary_metrics.get("repetition_warning_rate"),
            human_review_coverage=canary_metrics.get("human_review_coverage"),
            required_approval_roles_satisfied=policy_result["satisfied"],
            runtime_compatibility_status=(
                compatibility_row["status"] if compatibility_row else "not_assessed"
            ),
            runtime_health_status="healthy" if diagnostics_ok else "not_checked",
            admin_diagnostics_succeeded=diagnostics_ok,
            canary_succeeded=bool(canary_row and canary_row["run_status"] == "completed"),
            canary_within_thresholds=not canary_metrics.get("stop_reasons"),
            rollback_target_available=rollback_target_available,
            fallback_policy_configured=bool(loads_json(assignment["fallback_policy_json"])),
            explicit_activation_confirmed=explicit_activation_confirmed,
            thresholds=thresholds,
        )

    def pause_assignment(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            assignment = self.repository.assignment(connection, public_id)
            if assignment["status"] != "active":
                raise ValidationError("assignment must be active to pause")
            self.repository.update_assignment(connection, assignment["id"], {"status": "paused"})
            self.repository.record_event(
                connection,
                {
                    "model_assignment_id": assignment["id"],
                    "event_type": "paused",
                    "actor_admin_public_id": admin_id,
                },
            )
            self._audit(connection, "inference_assignment_paused", admin_id, public_id)
            return public_row(self.repository.assignment(connection, public_id))

    def resume_assignment(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            assignment = self.repository.assignment(connection, public_id)
            if assignment["status"] != "paused":
                raise ValidationError("assignment must be paused to resume")
            self.repository.update_assignment(connection, assignment["id"], {"status": "active"})
            self.repository.record_event(
                connection,
                {
                    "model_assignment_id": assignment["id"],
                    "event_type": "resumed",
                    "actor_admin_public_id": admin_id,
                },
            )
            self._audit(connection, "inference_assignment_resumed", admin_id, public_id)
            return public_row(self.repository.assignment(connection, public_id))

    def versions(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            assignment = self.repository.assignment(connection, public_id)
            rows = self.repository.versions_for_assignment(connection, assignment["id"])
            return {"items": [public_row(row) for row in rows]}

    def events(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            assignment = self.repository.assignment(connection, public_id)
            rows = self.repository.events_for_assignment(connection, assignment["id"])
            return {"items": [public_row(row) for row in rows]}

    # --- runtime instance resolution -----------------------------------------------------

    def _resolve_instance_for_assignment(self, connection, assignment) -> Any:
        """Always returns the instance's full joined row (with profile_* fields
        and the internal `id`) — never the public-row-shaped dict, so every
        caller can rely on the same shape regardless of whether the instance
        already existed or was just created."""

        existing = [
            row
            for row in self.repository.list_instances(connection)
            if row["inference_runtime_profile_id"] == assignment["inference_runtime_profile_id"]
        ]
        if existing:
            instance_public_id = existing[0]["public_id"]
        else:
            instance_public_id = self.repository.create_instance(
                connection, assignment["inference_runtime_profile_id"], {}
            )
        return self.repository.instance(connection, instance_public_id)

    def _ensure_loaded(self, connection, assignment, admin_id: str) -> Any:
        instance = self._resolve_instance_for_assignment(connection, assignment)
        if (
            instance["status"] == "ready"
            and instance["loaded_release_public_id"] == assignment["release_public_id"]
        ):
            return instance
        self.runtime_service.load_instance_using_connection(
            connection, instance["public_id"], assignment["release_public_id"], admin_id
        )
        return self.repository.instance(connection, instance["public_id"])

    # --- admin diagnostic generation -----------------------------------------------------

    def diagnostic_generate(
        self, public_id: str, payload: DiagnosticGenerateRequest, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            assignment = self.repository.assignment(connection, public_id)
            if assignment["scope_key"] != "admin_diagnostic":
                raise ValidationError("this assignment is not an admin_diagnostic assignment")
            if assignment["status"] != "active":
                raise ValidationError("assignment must be active to generate diagnostics")
            instance = self._ensure_loaded(connection, assignment, admin_id)
            context_policy = loads_json(assignment["context_policy_json"])
            context = build_context(
                system_prompt=context_policy.get("system_prompt", ""),
                history=[],
                latest_user_message=payload.prompt,
                bos_token="<bos>",
                system_prefix="<system>",
                user_prefix="<user>",
                assistant_prefix="<assistant>",
                encode_fn=lambda text: text.split(),
                maximum_context_length=instance["profile_maximum_context_length"],
                truncation_policy=context_policy.get("truncation_policy", "reject"),
            )
            if context["rejected"]:
                raise ValidationError("prompt exceeds the runtime profile context length")

            maximum_new_tokens = min(
                payload.maximum_new_tokens or instance["profile_maximum_new_tokens"],
                instance["profile_maximum_new_tokens"],
            )
            result = self.runtime_service.run_generation(
                instance["public_id"],
                prompt_text=context["prompt_text"],
                maximum_new_tokens=maximum_new_tokens,
                timeout_seconds=instance["profile_request_timeout_seconds"],
                system_text=context_policy.get("system_prompt", ""),
            )
            self._record_request_result(
                connection,
                instance_id=instance["id"],
                assignment=assignment,
                scope="admin_diagnostic",
                prompt_text=context["prompt_text"],
                result=result,
            )
            self._audit(connection, "inference_diagnostic_generated", admin_id, public_id)
            return {
                "disclaimer": DIAGNOSTIC_DISCLAIMER,
                "generated_text": result["generated_text"],
                "stop_reason": result["stop_reason"],
                "input_token_count": result["prompt_token_count"],
                "output_token_count": result["output_token_count"],
                "runtime_milliseconds": result["runtime_milliseconds"],
                "role_token_leakage": result["role_token_leakage"],
                "prompt_leakage": result["prompt_leakage"],
                "unicode_valid": result["unicode_valid"],
            }

    def _record_request_result(
        self, connection, *, instance_id, assignment, scope: str, prompt_text: str, result: dict,
        session_id: int | None = None,
    ) -> None:
        prompt_checksum = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
        status = "completed" if result["stop_reason"] not in {"timeout", "invalid_token"} else (
            "timed_out" if result["stop_reason"] == "timeout" else "failed"
        )
        request_public_id = self.repository.record_request(
            connection,
            {
                "inference_runtime_instance_id": instance_id,
                "model_assignment_id": assignment["id"],
                "scope": scope,
                "inference_session_id": session_id,
                "prompt_checksum_sha256": prompt_checksum,
                "input_token_count": result["prompt_token_count"],
                "maximum_new_token_count": result["output_token_count"],
                "status": status,
                "runtime_milliseconds": result["runtime_milliseconds"],
                "stop_reason": result["stop_reason"],
            },
        )
        request_row = connection.execute(
            "SELECT id FROM inference_requests WHERE public_id=?", (request_public_id,)
        ).fetchone()
        output_checksum = hashlib.sha256(result["generated_text"].encode("utf-8")).hexdigest()
        self.repository.record_result(
            connection,
            {
                "inference_request_id": request_row["id"],
                "output_checksum_sha256": output_checksum,
                "generated_token_count": result["output_token_count"],
                "stop_reason": result["stop_reason"],
                "runtime_milliseconds": result["runtime_milliseconds"],
                "role_token_leakage_flag": result["role_token_leakage"],
                "prompt_leakage_flag": result["prompt_leakage"],
                "unicode_valid_flag": result["unicode_valid"],
                "model_release_public_id": result["release_public_id"],
            },
        )

    # --- admin chat lab -----------------------------------------------------

    def create_session(
        self, public_id: str, payload: ChatLabSessionCreate, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            assignment = self.repository.assignment(connection, public_id)
            if assignment["scope_key"] != "admin_chat_lab":
                raise ValidationError("this assignment is not an admin_chat_lab assignment")
            if assignment["status"] != "active":
                raise ValidationError("assignment must be active to open a chat-lab session")
            instance = self._ensure_loaded(connection, assignment, admin_id)
            session_public_id = self.repository.create_session(
                connection,
                {
                    "model_assignment_id": assignment["id"],
                    "inference_runtime_instance_id": instance["id"],
                    "scope": "admin_chat_lab",
                    "max_turns": payload.max_turns,
                    "created_by_admin_public_id": admin_id,
                },
            )
            self._audit(connection, "inference_chat_lab_session_created", admin_id, public_id)
            return public_row(self.repository.session(connection, session_public_id))

    def get_session(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.session(connection, public_id))

    def post_message(self, session_public_id: str, message: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session = self.repository.session(connection, session_public_id)
            if session["status"] != "active":
                raise ValidationError("session is not active")
            assignment = connection.execute(
                "SELECT * FROM inference_model_assignments WHERE id=?",
                (session["model_assignment_id"],),
            ).fetchone()
            if session["turn_count"] >= session["max_turns"]:
                self.repository.update_session(connection, session["id"], {"status": "expired"})
                raise ValidationError("session has reached its maximum turn count")
            instance_public_id = connection.execute(
                "SELECT public_id FROM inference_runtime_instances WHERE id=?",
                (session["inference_runtime_instance_id"],),
            ).fetchone()["public_id"]
            instance = self.repository.instance(connection, instance_public_id)
            history_rows = self.repository.messages_for_session(connection, session["id"])
            history: list[ConversationTurn] = []
            for _row in history_rows:
                history.append(ConversationTurn("user", "(previous user turn)"))
                history.append(ConversationTurn("assistant", "(previous assistant turn)"))
            context = build_context(
                system_prompt="",
                history=history,
                latest_user_message=message,
                bos_token="<bos>",
                system_prefix="<system>",
                user_prefix="<user>",
                assistant_prefix="<assistant>",
                encode_fn=lambda text: text.split(),
                maximum_context_length=instance["profile_maximum_context_length"],
                truncation_policy="truncate_oldest_history",
            )
            release_public_id = connection.execute(
                "SELECT public_id FROM model_releases WHERE id=?",
                (assignment["model_release_id"],),
            ).fetchone()["public_id"]
            if instance["loaded_release_public_id"] != release_public_id:
                self.runtime_service.load_instance_using_connection(
                    connection, instance["public_id"], release_public_id, admin_id
                )
                instance = self.repository.instance(connection, instance_public_id)
            result = self.runtime_service.run_generation(
                instance["public_id"],
                prompt_text=context["prompt_text"],
                maximum_new_tokens=instance["profile_maximum_new_tokens"],
                timeout_seconds=instance["profile_request_timeout_seconds"],
            )
            self._record_request_result(
                connection,
                instance_id=instance["id"],
                assignment=assignment,
                scope="admin_chat_lab",
                prompt_text=context["prompt_text"],
                result=result,
                session_id=session["id"],
            )
            self.repository.update_session(
                connection, session["id"], {"turn_count": session["turn_count"] + 1}
            )
            return {
                "generated_text": result["generated_text"],
                "stop_reason": result["stop_reason"],
                "role_token_leakage": result["role_token_leakage"],
                "unicode_valid": result["unicode_valid"],
            }

    def close_session(self, session_public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session = self.repository.session(connection, session_public_id)
            self.repository.update_session(connection, session["id"], {"status": "closed"})
            self._audit(
                connection, "inference_chat_lab_session_closed", admin_id, session_public_id
            )
            return public_row(self.repository.session(connection, session_public_id))

    # --- canary -----------------------------------------------------

    def start_canary(
        self, public_id: str, payload: CanaryStartRequest, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            assignment = self.repository.assignment(connection, public_id)
            if assignment["scope_key"] != "internal_canary":
                raise ValidationError("this assignment is not an internal_canary assignment")
            if assignment["status"] != "active":
                raise ValidationError("assignment must be active to start a canary")
            run_public_id = self.repository.record_canary_run(
                connection,
                {
                    "model_assignment_id": assignment["id"],
                    "run_status": "running",
                    "percentage": payload.percentage,
                    "max_request_count": payload.max_request_count,
                    "created_by_admin_public_id": admin_id,
                },
            )
            self.repository.record_event(
                connection,
                {
                    "model_assignment_id": assignment["id"],
                    "event_type": "canary_started",
                    "actor_admin_public_id": admin_id,
                },
            )
            self._audit(connection, "inference_canary_started", admin_id, public_id)
            return public_row(connection.execute(
                "SELECT * FROM inference_canary_runs WHERE public_id=?", (run_public_id,)
            ).fetchone())

    def execute_canary(
        self, public_id: str, fixture_prompts: list[str], admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            assignment = self.repository.assignment(connection, public_id)
            run = self.repository.latest_canary_run(connection, assignment["id"])
            if not run or run["run_status"] not in {"running", "started"}:
                raise ValidationError("no running canary for this assignment")
            instance = self._ensure_loaded(connection, assignment, admin_id)
            results: list[dict[str, Any]] = []
            remaining = max(0, run["max_request_count"] - run["requests_executed"])
            for index, prompt in enumerate(fixture_prompts[:remaining]):
                routing_key = f"{run['public_id']}:{index}"
                use_model = stable_routing_key(routing_key, run["percentage"])
                if use_model:
                    generation = self.runtime_service.run_generation(
                        instance["public_id"],
                        prompt_text=prompt,
                        maximum_new_tokens=instance["profile_maximum_new_tokens"],
                        timeout_seconds=instance["profile_request_timeout_seconds"],
                    )
                    outcome = {
                        "used_model": True,
                        "success": generation["stop_reason"] not in {"invalid_token"},
                        "timed_out": generation["stop_reason"] == "timeout",
                        "latency_ms": generation["runtime_milliseconds"],
                        "input_tokens": generation["prompt_token_count"],
                        "output_tokens": generation["output_token_count"],
                        "role_leakage": generation["role_token_leakage"],
                        "prompt_leakage": generation["prompt_leakage"],
                        "duplicate_output": False,
                        "unicode_valid": generation["unicode_valid"],
                        "stop_reason": generation["stop_reason"],
                    }
                else:
                    outcome = {
                        "used_model": False,
                        "success": True,
                        "timed_out": False,
                        "latency_ms": 0,
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "role_leakage": False,
                        "prompt_leakage": False,
                        "duplicate_output": False,
                        "unicode_valid": True,
                        "stop_reason": "fallback_routed",
                    }
                self.repository.record_canary_result(
                    connection,
                    {"inference_canary_run_id": run["id"], "routing_key": routing_key, **outcome},
                )
                results.append(outcome)

            all_results = [
                dict(row) for row in self.repository.results_for_canary_run(connection, run["id"])
            ]
            metrics = compute_canary_metrics(all_results)
            thresholds = CanaryThresholds(
                max_failure_rate=self.settings.inference_canary_max_failure_rate,
                max_timeout_rate=self.settings.inference_canary_max_timeout_rate,
                max_role_leakage_rate=self.settings.inference_canary_max_role_leakage_rate,
                max_prompt_leakage_rate=self.settings.inference_canary_max_prompt_leakage_rate,
                max_duplicate_rate=self.settings.inference_canary_max_duplicate_rate,
            )
            stop_assessment = assess_canary_stop(metrics, thresholds)
            reached_max = len(all_results) >= run["max_request_count"]
            if stop_assessment.should_stop or reached_max:
                # inference_canary_runs is append-only: a terminal snapshot is a
                # new row, never an UPDATE of the "running" row results are
                # attached to.
                terminal_status = "paused" if stop_assessment.should_stop else "completed"
                self.repository.record_canary_run(
                    connection,
                    {
                        "model_assignment_id": assignment["id"],
                        "run_status": terminal_status,
                        "percentage": run["percentage"],
                        "max_request_count": run["max_request_count"],
                        "requests_executed": len(all_results),
                        "stop_reason": (
                            ",".join(stop_assessment.reasons) if stop_assessment.reasons else None
                        ),
                        "metrics_json": dumps_json(
                            {**metrics, "stop_reasons": stop_assessment.reasons}
                        ),
                        "created_by_admin_public_id": admin_id,
                    },
                )
            if stop_assessment.should_stop:
                self.repository.record_event(
                    connection,
                    {
                        "model_assignment_id": assignment["id"],
                        "event_type": "canary_stopped",
                        "details_json": dumps_json({"reasons": stop_assessment.reasons}),
                        "actor_admin_public_id": admin_id,
                    },
                )
            self._audit(connection, "inference_canary_executed", admin_id, public_id)
            return {
                "metrics": metrics,
                "stop_assessment": {
                    "should_stop": stop_assessment.should_stop,
                    "reasons": stop_assessment.reasons,
                },
                "requests_executed": len(all_results),
            }

    def stop_canary(self, public_id: str, reason: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            assignment = self.repository.assignment(connection, public_id)
            run = self.repository.latest_canary_run(connection, assignment["id"])
            if not run:
                raise NotFoundError("no canary run found for this assignment")
            new_run_public_id = self.repository.record_canary_run(
                connection,
                {
                    "model_assignment_id": assignment["id"],
                    "run_status": "stopped",
                    "percentage": run["percentage"],
                    "max_request_count": run["max_request_count"],
                    "requests_executed": run["requests_executed"],
                    "stop_reason": reason,
                    "metrics_json": run["metrics_json"],
                    "created_by_admin_public_id": admin_id,
                },
            )
            self.repository.record_event(
                connection,
                {
                    "model_assignment_id": assignment["id"],
                    "event_type": "canary_stopped",
                    "details_json": dumps_json({"reasons": [reason]}),
                    "actor_admin_public_id": admin_id,
                },
            )
            self._audit(connection, "inference_canary_stopped", admin_id, public_id, reason=reason)
            return public_row(
                connection.execute(
                    "SELECT * FROM inference_canary_runs WHERE public_id=?", (new_run_public_id,)
                ).fetchone()
            )

    def canary_results(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            assignment = self.repository.assignment(connection, public_id)
            runs = self.repository.canary_runs_for_assignment(connection, assignment["id"])
            return {"items": [public_row(row) for row in runs]}

    # --- rollback -----------------------------------------------------

    def rollback_preview(
        self, public_id: str, payload: RollbackPreviewRequest, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            assignment = self.repository.assignment(connection, public_id)
            target_version = self.repository.version(connection, payload.target_version_public_id)
            if target_version["model_assignment_id"] != assignment["id"]:
                raise ValidationError("target version does not belong to this assignment")
            target_release = connection.execute(
                "SELECT * FROM model_releases WHERE id=?", (target_version["model_release_id"],)
            ).fetchone()
            eligible = target_release["status"] == "released" and target_release[
                "deployment_eligibility"
            ] in {"deployable", "deployable_with_warnings"}
            self._audit(
                connection, "inference_rollback_previewed", admin_id, public_id,
                target_version_public_id=payload.target_version_public_id, eligible=eligible,
            )
            return {
                "eligible": eligible,
                "target_version": public_row(target_version),
                "current_version_public_id": assignment["current_version_public_id"],
            }

    def rollback_execute(
        self, public_id: str, payload: RollbackPreviewRequest, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            assignment = self.repository.assignment(connection, public_id)
            target_version = self.repository.version(connection, payload.target_version_public_id)
            if target_version["model_assignment_id"] != assignment["id"]:
                raise ValidationError("target version does not belong to this assignment")
            target_release = connection.execute(
                "SELECT * FROM model_releases WHERE id=?", (target_version["model_release_id"],)
            ).fetchone()
            target_deployable = target_release["deployment_eligibility"] in {
                "deployable",
                "deployable_with_warnings",
            }
            if target_release["status"] != "released" or not target_deployable:
                self.repository.record_event(
                    connection,
                    {
                        "model_assignment_id": assignment["id"],
                        "event_type": "rollback_failed",
                        "actor_admin_public_id": admin_id,
                    },
                )
                raise ValidationError("rollback target is not eligible")

            self.repository.record_event(
                connection,
                {
                    "model_assignment_id": assignment["id"],
                    "event_type": "rollback_started",
                    "actor_admin_public_id": admin_id,
                },
            )
            instance = self._resolve_instance_for_assignment(connection, assignment)
            fallback_decision = decide_fallback(
                "placeholder", previous_assignment_version_available=True
            )
            try:
                self.runtime_service.load_instance_using_connection(
                    connection, instance["public_id"], target_release["public_id"], admin_id
                )
                load_failed = False
            except ValidationError:
                load_failed = True
                self.repository.record_failure(
                    connection,
                    {
                        "inference_runtime_instance_id": instance["id"],
                        "model_assignment_id": assignment["id"],
                        "failure_code": "model_load_failed",
                        "failure_summary": "rollback target failed to load",
                    },
                )

            new_status = "active" if not load_failed else "paused"
            self.repository.update_assignment(
                connection,
                assignment["id"],
                {
                    "status": new_status,
                    "current_version_public_id": target_version["public_id"],
                    "model_release_id": target_version["model_release_id"],
                    "inference_runtime_profile_id": target_version["inference_runtime_profile_id"],
                    "generation_config_json": target_version["generation_config_json"],
                    "context_policy_json": target_version["context_policy_json"],
                    "fallback_policy_json": target_version["fallback_policy_json"],
                    "canary_percentage": target_version["canary_percentage"],
                },
            )
            self.repository.record_event(
                connection,
                {
                    "model_assignment_id": assignment["id"],
                    "event_type": "rollback_failed" if load_failed else "rollback_completed",
                    "details_json": dumps_json(
                        build_fallback_event(
                            assignment_public_id=public_id,
                            decision=fallback_decision,
                            failure_code="model_load_failed" if load_failed else "none",
                        )
                    ),
                    "actor_admin_public_id": admin_id,
                },
            )
            self._audit(
                connection, "inference_rollback_executed", admin_id, public_id, failed=load_failed,
            )
            return {
                "rolled_back": not load_failed,
                "current_version_public_id": target_version["public_id"],
                "assignment": public_row(self.repository.assignment(connection, public_id)),
            }

    # --- runtime manifest -----------------------------------------------------

    def generate_manifest(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            assignment = self.repository.assignment(connection, public_id)
            release = self.release_repository.release(connection, assignment["release_public_id"])
            candidate = self.release_repository.candidate(
                connection, release["model_release_candidate_public_id"]
            )
            compatibility_row = self.repository.latest_compatibility(
                connection,
                assignment["model_release_id"],
                assignment["inference_runtime_profile_id"],
            )
            version = self.repository.latest_version(connection, assignment["id"])
            approvals = [
                dict(row)
                for row in self.repository.approvals_for_assignment(connection, assignment["id"])
            ]
            canary_run = self.repository.latest_canary_run(connection, assignment["id"])
            release_manifest_row = self.release_repository.latest_manifest(
                connection, candidate["id"]
            )

            manifest = {
                "assignment_public_id": public_id,
                "scope": assignment["scope_key"],
                "release_public_id": release["public_id"],
                "release_manifest_checksum_sha256": (
                    release_manifest_row["manifest_checksum_sha256"]
                    if release_manifest_row
                    else None
                ),
                "checkpoint_checksum_sha256": candidate["checkpoint_model_checksum_sha256"],
                "tokenizer_checksum_sha256": candidate["tokenizer_model_checksum_sha256"],
                "model_config_checksum_sha256": candidate["core_model_config_checksum_sha256"],
                "compatibility_status": compatibility_row["status"] if compatibility_row else None,
                "generation_config": loads_json(assignment["generation_config_json"]),
                "assignment_version_public_id": version["public_id"] if version else None,
                "canary_configuration": {
                    "percentage": canary_run["percentage"] if canary_run else 0,
                    "max_request_count": canary_run["max_request_count"] if canary_run else 0,
                },
                "fallback_policy": loads_json(assignment["fallback_policy_json"]),
                "activation_approvals": [
                    {"role": a["role"], "decision": a["decision"]} for a in approvals
                ],
                "known_limitations": [
                    "runtime existence does not imply model quality",
                    "public chat activation requires a separate explicit gate",
                ],
                "software_versions": {"phase": 15},
                "created_at": None,
            }
            concerns = scan_for_sensitive_content(manifest)
            if concerns:
                raise ValidationError(f"runtime manifest failed sensitive-content scan: {concerns}")
            checksum = manifest_checksum(manifest)
            manifest_public_id = self.repository.record_manifest(
                connection, assignment["id"], dumps_json(manifest), checksum
            )
            self._audit(connection, "inference_runtime_manifest_generated", admin_id, public_id)
            return public_row(
                connection.execute(
                    "SELECT * FROM inference_runtime_manifests WHERE public_id=?",
                    (manifest_public_id,),
                ).fetchone()
            )

    def verify_manifest(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            assignment = self.repository.assignment(connection, public_id)
            row = self.repository.latest_manifest(connection, assignment["id"])
            if not row:
                raise NotFoundError("no runtime manifest recorded for this assignment")
            recomputed = hashlib.sha256(row["manifest_json"].encode("utf-8")).hexdigest()
            return {
                "matches": recomputed == row["manifest_checksum_sha256"],
                "manifest_checksum_sha256": row["manifest_checksum_sha256"],
            }

    # --- audit -----------------------------------------------------

    def _audit(
        self, connection, event: str, admin_id: str, resource_id: str, **metadata: Any
    ) -> None:
        if not self.settings.audit_enabled:
            return
        connection.execute(
            """INSERT INTO audit_logs(action,actor,details,public_id,event_type,actor_type,
            actor_reference,resource_type,resource_public_id,outcome,metadata_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                event, "admin", "{}", str(uuid4()), event, "admin", admin_id,
                "inference_assignment", resource_id, "success", dumps_json(metadata),
            ),
        )
