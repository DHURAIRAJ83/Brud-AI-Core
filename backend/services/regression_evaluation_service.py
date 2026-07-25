"""Phase 18 regression suites, fixtures, runs, results, model
comparisons, improvement reports, and the feedback manifest.

Regression fixtures are evaluation-only evidence. This service never
writes a regression fixture into ``dataset_records`` or any training
pipeline -- it only ever executes fixtures against the existing Phase
15 controlled inference runtime and records pass/fail evidence.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any

from backend.core.config import Settings
from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import ValidationError
from backend.database.repositories.feedback import FeedbackRepository, public_row
from backend.database.repositories.inference_runtime import InferenceRuntimeRepository
from backend.models.feedback import (
    ImprovementReportCreate,
    RegressionFixtureCreate,
    RegressionRunCompareRequest,
    RegressionRunCreate,
    RegressionSuiteCreate,
)
from backend.services.model_assignment_service import ModelAssignmentService
from core_model.feedback import REGRESSION_CATEGORIES
from core_model.feedback.comparison import assess_compatibility, classify_comparison_result
from core_model.feedback.improvement_metrics import category_regression_rate, regression_rates
from core_model.feedback.regression_fixture import build_regression_fixture, evaluate_fixture_result

RAG_DIAGNOSTIC_SCOPE = "admin_diagnostic"


def _checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class RegressionEvaluationService:
    def __init__(
        self,
        repository: FeedbackRepository,
        inference_repository: InferenceRuntimeRepository,
        assignment_service: ModelAssignmentService,
        settings: Settings,
    ) -> None:
        self.repository = repository
        self.inference_repository = inference_repository
        self.assignment_service = assignment_service
        self.settings = settings

    # --- regression suites -----------------------------------------------------

    def create_suite(self, payload: RegressionSuiteCreate, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            public_id = self.repository.create_regression_suite(
                connection,
                {
                    "name": payload.name,
                    "description": payload.description,
                    "created_by_admin_public_id": admin_id,
                },
            )
            return public_row(self.repository.regression_suite(connection, public_id))

    def list_suites(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_regression_suites(connection)
            return {"items": [public_row(row) for row in rows]}

    def get_suite(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.regression_suite(connection, public_id))

    def add_fixture(
        self, suite_public_id: str, payload: RegressionFixtureCreate, admin_id: str
    ) -> dict[str, Any]:
        if not self.settings.feedback_allow_regression_fixtures:
            raise ValidationError("regression fixture creation is disabled by settings")
        if payload.category not in REGRESSION_CATEGORIES:
            raise ValidationError("unsupported regression category")
        with self.repository.transaction() as connection:
            suite = self.repository.regression_suite(connection, suite_public_id)
            if suite["lifecycle_status"] not in {"draft", "validated"}:
                raise ValidationError("fixtures may only be added to a draft/validated suite")
            fixture = build_regression_fixture(
                category=payload.category,
                language=payload.language,
                input_text=payload.input_text,
                controlled_context=payload.controlled_context,
                expected_behavior=payload.expected_behavior,
                forbidden_behavior=payload.forbidden_behavior,
                expected_citations=payload.expected_citations,
                expected_memory_behavior=payload.expected_memory_behavior,
                severity=payload.severity,
                source_feedback_event_public_ids=payload.source_feedback_event_public_ids,
            )
            if fixture["blocked"]:
                raise ValidationError("fixture content blocked by privacy scan")
            public_id = self.repository.create_regression_fixture(
                connection,
                suite["id"],
                {
                    "category": fixture["category"],
                    "language": fixture["language"],
                    "input_text": fixture["input_text"],
                    "controlled_context_json": dumps_json(fixture["controlled_context"]),
                    "expected_behavior": fixture["expected_behavior"],
                    "forbidden_behavior": fixture["forbidden_behavior"],
                    "expected_citations_json": dumps_json(fixture["expected_citations"]),
                    "expected_memory_behavior_json": dumps_json(
                        fixture["expected_memory_behavior"]
                    ),
                    "severity": fixture["severity"],
                    "source_feedback_event_ids_json": dumps_json(
                        fixture["source_feedback_event_public_ids"]
                    ),
                    "checksum_sha256": fixture["checksum_sha256"],
                },
            )
            return public_row(self.repository.fixture(connection, public_id))

    def validate_suite(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            suite = self.repository.regression_suite(connection, public_id)
            fixtures = self.repository.fixtures_for_suite(connection, suite["id"])
            if not fixtures:
                raise ValidationError("suite must have at least one fixture to validate")
            checksum = _checksum("|".join(sorted(row["checksum_sha256"] for row in fixtures)))
            self.repository.update_regression_suite(
                connection, suite["id"],
                {"lifecycle_status": "validated", "checksum_sha256": checksum},
            )
            return public_row(self.repository.regression_suite(connection, public_id))

    def activate_suite(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            suite = self.repository.regression_suite(connection, public_id)
            if suite["lifecycle_status"] != "validated":
                raise ValidationError("suite must be validated before activation")
            self.repository.update_regression_suite(
                connection, suite["id"], {"lifecycle_status": "active"}
            )
            return public_row(self.repository.regression_suite(connection, public_id))

    # --- regression runs -----------------------------------------------------

    def create_run(
        self, suite_public_id: str, payload: RegressionRunCreate, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            suite = self.repository.regression_suite(connection, suite_public_id)
            if suite["lifecycle_status"] != "active":
                raise ValidationError("suite must be active to run")
            assignment = self.inference_repository.assignment(
                connection, payload.model_assignment_public_id
            )
            if assignment["scope_key"] != RAG_DIAGNOSTIC_SCOPE:
                raise ValidationError("regression runs require an admin_diagnostic assignment")
            if assignment["status"] != "active":
                raise ValidationError("assignment must be active for a regression run")
            active_runs = self.repository.count_active_regression_runs(connection)
            if active_runs >= self.settings.feedback_max_active_regression_runs:
                raise ValidationError("maximum concurrent regression runs reached")
            config_checksum = _checksum(
                f"{assignment['public_id']}|{assignment['runtime_profile_public_id']}"
            )
            public_id = self.repository.create_regression_run(
                connection,
                {
                    "suite_id": suite["id"],
                    "model_assignment_id": assignment["id"],
                    "generation_configuration_checksum_sha256": config_checksum,
                    "created_by_admin_public_id": admin_id,
                },
            )
            return public_row(self.repository.regression_run(connection, public_id))

    def get_run(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.regression_run(connection, public_id))

    def execute_run(self, run_public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            run = self.repository.regression_run(connection, run_public_id)
            if run["status"] != "draft":
                raise ValidationError("run must be draft to execute")
            assignment_row = connection.execute(
                "SELECT public_id FROM inference_model_assignments WHERE id=?",
                (run["model_assignment_id"],),
            ).fetchone()
            fixtures = [
                dict(row)
                for row in self.repository.fixtures_for_suite(connection, run["suite_id"])
            ]
            self.repository.update_regression_run(
                connection, run["id"], {"status": "running", "started_at": "CURRENT_TIMESTAMP"}
            )

        instance = self.assignment_service.ensure_instance_loaded(
            assignment_row["public_id"], admin_id
        )

        results: list[dict[str, Any]] = []
        for fixture in fixtures:
            controlled_context = loads_json(fixture["controlled_context_json"])
            try:
                generation = self.assignment_service.runtime_service.run_generation(
                    instance["public_id"],
                    prompt_text=fixture["input_text"],
                    maximum_new_tokens=instance["profile_maximum_new_tokens"],
                    timeout_seconds=instance["profile_request_timeout_seconds"],
                    system_text=dumps_json(controlled_context),
                )
                generated_text = generation["generated_text"]
                forbidden_observed = bool(
                    fixture["forbidden_behavior"]
                    and fixture["forbidden_behavior"].lower() in generated_text.lower()
                ) or generation["role_token_leakage"] or generation["prompt_leakage"]
                matches_expected = bool(generated_text.strip()) and not forbidden_observed
                outcome = evaluate_fixture_result(
                    actual_behavior_matches_expected=matches_expected,
                    forbidden_behavior_observed=forbidden_observed,
                )
            except ValidationError as exc:
                outcome = {"passed": False, "failure_reason": f"generation_failed:{exc}"}
            results.append({"fixture_id": fixture["id"], **outcome})

        with self.repository.transaction() as connection:
            for result in results:
                self.repository.record_regression_result(
                    connection,
                    {
                        "run_id": run["id"],
                        "fixture_id": result["fixture_id"],
                        "passed": result["passed"],
                        "failure_reason": result.get("failure_reason"),
                    },
                )
            self.repository.update_regression_run(
                connection, run["id"], {"status": "completed", "ended_at": "CURRENT_TIMESTAMP"}
            )
            return public_row(self.repository.regression_run(connection, run_public_id))

    def get_results(self, run_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            run = self.repository.regression_run(connection, run_public_id)
            rows = self.repository.results_for_run(connection, run["id"])
            return {"items": [public_row(row) for row in rows]}

    def get_metrics(self, run_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            run = self.repository.regression_run(connection, run_public_id)
            results = self.repository.results_for_run(connection, run["id"])
            total = len(results)
            passed = sum(1 for row in results if row["passed"])
            return {
                "run_public_id": run_public_id,
                "total_fixtures": total,
                "passed": passed,
                "failed": total - passed,
                "pass_rate": (passed / total) if total else None,
            }

    def _run_pass_map(self, connection, run_id: int) -> dict[int, bool]:
        rows = self.repository.results_for_run(connection, run_id)
        return {row["fixture_id"]: bool(row["passed"]) for row in rows}

    def compare_runs(self, payload: RegressionRunCompareRequest, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            left_run = self.repository.regression_run(connection, payload.left_run_public_id)
            right_run = self.repository.regression_run(connection, payload.right_run_public_id)
            if left_run["suite_id"] != right_run["suite_id"]:
                raise ValidationError("runs must belong to the same regression suite")

            left_config = {
                "regression_suite_checksum": left_run["suite_checksum"],
                "generation_configuration_checksum": (
                    left_run["generation_configuration_checksum_sha256"]
                ),
            }
            right_config = {
                "regression_suite_checksum": right_run["suite_checksum"],
                "generation_configuration_checksum": (
                    right_run["generation_configuration_checksum_sha256"]
                ),
            }
            compatibility = assess_compatibility(left_config, right_config)

            fixtures = {
                row["id"]: row["category"]
                for row in self.repository.fixtures_for_suite(connection, left_run["suite_id"])
            }
            left_map = self._run_pass_map(connection, left_run["id"])
            right_map = self._run_pass_map(connection, right_run["id"])
            rates = regression_rates(baseline_results=left_map, candidate_results=right_map)
            comparison_result = classify_comparison_result(
                compatibility=compatibility,
                fixed_failure_rate=rates["fixed_failure_rate"],
                new_regression_rate=rates["new_regression_rate"],
                persistent_failure_rate=rates["persistent_failure_rate"],
            )
            category_rates = {
                category: category_regression_rate(
                    baseline_results=left_map, candidate_results=right_map,
                    fixture_categories=fixtures, category=category,
                )
                for category in REGRESSION_CATEGORIES
            }
            comparison_public_id = self.repository.create_comparison(
                connection,
                {
                    "regression_suite_id": left_run["suite_id"],
                    "left_run_id": left_run["id"],
                    "right_run_id": right_run["id"],
                    "compatibility": compatibility,
                    "comparison_result": comparison_result,
                    "fixed_failure_rate": rates["fixed_failure_rate"],
                    "persistent_failure_rate": rates["persistent_failure_rate"],
                    "new_regression_rate": rates["new_regression_rate"],
                    "language_regression_rate": category_rates.get("language_regression"),
                    "citation_regression_rate": category_rates.get("citation_regression"),
                    "safety_regression_rate": category_rates.get("safety_regression"),
                    "memory_regression_rate": category_rates.get("memory_regression"),
                    "privacy_regression_rate": category_rates.get("privacy_regression"),
                    "created_by_admin_public_id": admin_id,
                },
            )
            return public_row(self.repository.comparison(connection, comparison_public_id))

    def get_comparison(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.comparison(connection, public_id))

    # --- improvement reports -----------------------------------------------------

    def create_improvement_report(
        self, payload: ImprovementReportCreate, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            policy_id = None
            if payload.feedback_policy_public_id:
                policy_id = self.repository.policy(
                    connection, payload.feedback_policy_public_id
                )["id"]
            regression_run_id = None
            if payload.regression_run_public_id:
                regression_run_id = self.repository.regression_run(
                    connection, payload.regression_run_public_id
                )["id"]
            comparison_id = None
            comparison_row = None
            if payload.comparison_public_id:
                comparison_row = self.repository.comparison(
                    connection, payload.comparison_public_id
                )
                comparison_id = comparison_row["id"]

            events = self.repository.list_events(connection)
            total_events = len(events)
            positive = sum(1 for row in events if row["feedback_type"] == "thumbs_up")
            negative = sum(1 for row in events if row["feedback_type"] == "thumbs_down")
            critical = sum(1 for row in events if row["severity"] == "critical")
            privacy_blocked = sum(1 for row in events if row["privacy_status"] == "blocked")
            safety_blocked = sum(1 for row in events if row["safety_status"] == "blocked")
            candidates = self.repository.list_candidates(connection)
            approved = sum(
                1 for row in candidates if row["status"] in {"approved", "approved_with_warnings"}
            )

            report = {
                "feedback_submission_count": total_events,
                "positive_feedback_count": positive,
                "negative_feedback_count": negative,
                "critical_issue_count": critical,
                "privacy_blocked_count": privacy_blocked,
                "safety_blocked_count": safety_blocked,
                "dataset_candidate_count": len(candidates),
                "dataset_candidate_approved_count": approved,
                "regression_comparison": (
                    {
                        "result": comparison_row["comparison_result"],
                        "compatibility": comparison_row["compatibility"],
                    }
                    if comparison_row
                    else None
                ),
                "known_limitations": [
                    "Thumbs-up/down rates are not a measure of factual accuracy.",
                    "Regression comparisons require compatible generation configuration.",
                ],
            }
            report_json = dumps_json(report)
            report_checksum = _checksum(report_json)
            public_id = self.repository.create_improvement_report(
                connection,
                {
                    "feedback_policy_id": policy_id,
                    "regression_run_id": regression_run_id,
                    "comparison_id": comparison_id,
                    "report_json": report_json,
                    "report_checksum_sha256": report_checksum,
                    "created_by_admin_public_id": admin_id,
                },
            )
            return public_row(self.repository.improvement_report(connection, public_id))

    def get_improvement_report(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.improvement_report(connection, public_id))

    # --- manifest -----------------------------------------------------

    def generate_manifest(self, policy_public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            policy = self.repository.policy(connection, policy_public_id)
            events = self.repository.list_events(connection)
            candidates = self.repository.list_candidates(connection)
            suites = self.repository.list_regression_suites(connection)
            manifest = {
                "feedback_policy_public_id": policy_public_id,
                "feedback_policy_checksum": _checksum(policy["name"] + policy["lifecycle_status"]),
                "feedback_counts_by_type": _count_by(events, "feedback_type"),
                "feedback_counts_by_classification": {},
                "privacy_finding_summary": _count_by(events, "privacy_status"),
                "safety_finding_summary": _count_by(events, "safety_status"),
                "review_rubric_version": "1",
                "candidate_checksums": sorted(
                    row["public_id"] for row in candidates if row["current_version_id"]
                ),
                "deduplication_configuration": {
                    "near_duplicate_threshold": self.settings.feedback_near_duplicate_threshold
                },
                "contamination_configuration": {
                    "block_test_leakage": self.settings.feedback_block_test_leakage,
                    "block_evaluation_leakage": self.settings.feedback_block_evaluation_leakage,
                    "block_regression_leakage": self.settings.feedback_block_regression_leakage,
                },
                "regression_suite_checksum": (
                    suites[0]["checksum_sha256"]
                    if suites and suites[0]["checksum_sha256"]
                    else None
                ),
                "model_comparison_results": [],
                "improvement_report_checksum": None,
                "known_limitations": [
                    "Feedback ratings alone do not prove model correctness.",
                    "Regression fixtures are evaluation-only and never enter training data.",
                ],
                "software_versions": {"schema_version": 18},
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            manifest_json = dumps_json(manifest)
            checksum = _checksum(manifest_json)
            self.repository.create_manifest(
                connection,
                {
                    "feedback_policy_id": policy["id"],
                    "manifest_json": manifest_json,
                    "manifest_checksum_sha256": checksum,
                },
            )
            return public_row(self.repository.latest_manifest_for_policy(connection, policy["id"]))

    def verify_manifest(self, policy_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            policy = self.repository.policy(connection, policy_public_id)
            manifest_row = self.repository.latest_manifest_for_policy(connection, policy["id"])
            if not manifest_row:
                raise ValidationError("no manifest generated for this policy yet")
            recomputed = _checksum(manifest_row["manifest_json"])
            return {
                "matches": recomputed == manifest_row["manifest_checksum_sha256"],
                "manifest_public_id": manifest_row["public_id"],
            }


def _count_by(rows: list[Any], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = row[field]
        counts[key] = counts.get(key, 0) + 1
    return counts
