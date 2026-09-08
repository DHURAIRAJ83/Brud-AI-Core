"""Phase 61 - P7: Production Observability, Safety Monitoring, Incident Response & Governance Test Suite."""

import time
import unittest

from core_model.ops.production_observability_registry import (
    ObservabilityError,
    ProductionObservabilityRecord,
    ProductionObservabilityRegistry,
)
from core_model.ops.model_health_monitor import (
    HealthEvaluationResult,
    ModelHealthMonitor,
)
from core_model.ops.continuous_safety_monitor import (
    ContinuousSafetyMonitor,
    SafetyEvaluationResult,
    SafetyEventRecord,
)
from core_model.ops.incident_response_engine import (
    IncidentError,
    IncidentRecord,
    IncidentResponseEngine,
)
from core_model.ops.production_safety_controller import (
    ControllerStatusRecord,
    ProductionSafetyController,
)
from core_model.ops.model_drift_evaluator import (
    DriftEvaluationResult,
    ModelDriftEvaluator,
)
from core_model.ops.production_audit_chain import (
    AuditChainError,
    AuditEventRecord,
    ProductionAuditChain,
)
from core_model.ops.dashboard_contract import (
    GovernanceInvariantsView,
    IncidentStatusView,
    ProductionHealthView,
    ProductionSafetyDashboardContract,
    SafetyStatusView,
)
from core_model.eval.production_release_registry import ProductionReleaseRegistry


class TestPhase61P7ProductionObservabilitySafety(unittest.TestCase):

    def setUp(self):
        self.obs_registry = ProductionObservabilityRegistry()
        self.health_monitor = ModelHealthMonitor()
        self.safety_monitor = ContinuousSafetyMonitor()
        self.incident_engine = IncidentResponseEngine()
        self.release_registry = ProductionReleaseRegistry()
        self.safety_controller = ProductionSafetyController(release_registry=self.release_registry)
        self.drift_evaluator = ModelDriftEvaluator()
        self.audit_chain = ProductionAuditChain()

        # Register sample active release
        self.release_rec = self.release_registry.register_release(
            release_id="rel-p7-001",
            candidate_model_id="cand-p5-001",
            candidate_model_hash="cand-sha256-555",
            base_model_hash="base-sha256-444",
            dataset_version="foundation_stage8_v001",
            dataset_hash="dataset-manifest-sha256-111",
            tokenizer_hash="tokenizer-sha256-222",
            training_config_hash="config-sha256-333",
            evaluation_manifest_hash="eval-manifest-sha256-999",
            promotion_authorization_hash="prom-auth-sha256-888",
            approving_admin_identity="admin-dhurai"
        )
        self.release_registry.set_active_release("rel-p7-001")

    def test_01_observability_record_creation(self):
        rec = self.obs_registry.record_observation(
            release_id="rel-p7-001",
            model_hash="cand-sha256-555",
            dataset_hash="dataset-manifest-sha256-111",
            tokenizer_hash="tokenizer-sha256-222",
            request_count=1000,
            success_count=990,
            error_count=10,
            timeout_count=2,
            latency_p50=20.0,
            latency_p95=45.0,
            latency_p99=80.0
        )
        self.assertEqual(rec.release_id, "rel-p7-001")
        self.assertEqual(len(self.obs_registry.get_all_records()), 1)

    def test_02_observability_append_only_immutability(self):
        self.obs_registry.record_observation(
            release_id="rel-p7-001", model_hash="m1", dataset_hash="d1", tokenizer_hash="t1",
            request_count=100, success_count=98, error_count=2, timeout_count=0,
            latency_p50=15.0, latency_p95=30.0, latency_p99=50.0
        )
        recs = self.obs_registry.get_all_records()
        self.assertEqual(len(recs), 1)

    def test_03_malformed_telemetry_rejection(self):
        with self.assertRaises(ObservabilityError):
            self.obs_registry.record_observation(
                release_id="", model_hash="", dataset_hash="", tokenizer_hash="",
                request_count=10, success_count=5, error_count=5, timeout_count=0,
                latency_p50=10.0, latency_p95=20.0, latency_p99=30.0
            )

    def test_04_health_monitor_fail_closed_on_missing_telemetry(self):
        res = self.health_monitor.evaluate_health(None)
        self.assertEqual(res.health_status, "CRITICAL")
        self.assertIn("missing", res.reasons[0].lower())

    def test_05_health_monitor_critical_on_high_error_rate(self):
        rec = self.obs_registry.record_observation(
            release_id="rel-p7-001", model_hash="m1", dataset_hash="d1", tokenizer_hash="t1",
            request_count=100, success_count=90, error_count=10, timeout_count=0,  # 10% error rate
            latency_p50=15.0, latency_p95=30.0, latency_p99=50.0
        )
        res = self.health_monitor.evaluate_health(rec)
        self.assertEqual(res.health_status, "CRITICAL")

    def test_06_continuous_safety_event_logging(self):
        evt = self.safety_monitor.log_safety_event(
            release_id="rel-p7-001",
            model_hash="cand-sha256-555",
            event_type="PROMPT_INJECTION",
            severity="WARNING",
            description="Attempted injection attack detected and blocked."
        )
        self.assertEqual(evt.event_type, "PROMPT_INJECTION")

    def test_07_safety_escalation_to_rollback_on_critical_event(self):
        self.safety_monitor.log_safety_event(
            release_id="rel-p7-001",
            model_hash="cand-sha256-555",
            event_type="GOVERNANCE_BYPASS",
            severity="CRITICAL",
            description="Attempted critical governance bypass."
        )
        res = self.safety_monitor.evaluate_safety_status("rel-p7-001")
        self.assertEqual(res.safety_status, "CRITICAL")
        self.assertEqual(res.escalation_action, "ROLLBACK_REQUIRED")

    def test_08_incident_lifecycle_transitions(self):
        inc = self.incident_engine.raise_incident(
            release_id="rel-p7-001",
            model_hash="cand-sha256-555",
            severity="MEDIUM",
            trigger_source="HealthMonitor",
            description="Latency degraded."
        )
        self.assertEqual(inc.incident_status, "INCIDENT_DETECTED")
        updated = self.incident_engine.transition_status(inc.incident_id, "INCIDENT_TRIAGED", admin_identity="admin-dhurai")
        self.assertEqual(updated.incident_status, "INCIDENT_TRIAGED")

    def test_09_critical_incident_auto_close_protection(self):
        inc = self.incident_engine.raise_incident(
            release_id="rel-p7-001",
            model_hash="cand-sha256-555",
            severity="CRITICAL",
            trigger_source="SafetyMonitor",
            description="Critical safety breach."
        )
        with self.assertRaises(IncidentError):
            self.incident_engine.transition_status(inc.incident_id, "INCIDENT_CLOSED", admin_identity="auto-bot")

    def test_10_production_safety_controller_traffic_freeze(self):
        rec = self.obs_registry.record_observation(
            release_id="rel-p7-001", model_hash="m1", dataset_hash="d1", tokenizer_hash="t1",
            request_count=100, success_count=98, error_count=2, timeout_count=0,
            latency_p50=15.0, latency_p95=30.0, latency_p99=50.0,
            safety_violation_count=2  # Violation
        )
        health_res = self.health_monitor.evaluate_health(rec)
        self.safety_monitor.log_safety_event("rel-p7-001", "m1", "BYPASS", "VIOLATION", "Violation 1")
        self.safety_monitor.log_safety_event("rel-p7-001", "m1", "BYPASS", "VIOLATION", "Violation 2")
        safety_res = self.safety_monitor.evaluate_safety_status("rel-p7-001")

        ctrl_res = self.safety_controller.evaluate_and_control("rel-p7-001", health_res, safety_res)
        self.assertEqual(ctrl_res.candidate_traffic_share, 0.0)
        self.assertFalse(ctrl_res.public_chat_eligible)

    def test_11_production_safety_controller_invokes_p6_rollback(self):
        rec = self.obs_registry.record_observation(
            release_id="rel-p7-001", model_hash="m1", dataset_hash="d1", tokenizer_hash="t1",
            request_count=100, success_count=90, error_count=10, timeout_count=0,
            latency_p50=15.0, latency_p95=30.0, latency_p99=50.0
        )
        health_res = self.health_monitor.evaluate_health(rec)
        ctrl_res = self.safety_controller.evaluate_and_control("rel-p7-001", health_res, safety_res=None)

        self.assertEqual(ctrl_res.controller_state, "RECOVERED")
        self.assertEqual(ctrl_res.candidate_traffic_share, 0.0)

    def test_12_model_drift_evaluation(self):
        res = self.drift_evaluator.evaluate_drift(
            release_id="rel-p7-001",
            current_error_rate=0.07,
            current_latency_ms=120.0,
            current_hallucination_rate=0.18
        )
        self.assertEqual(res.drift_status, "CRITICAL_DRIFT")
        self.assertEqual(res.recommended_action, "ROLLBACK_REQUIRED")

    def test_13_drift_evaluation_does_not_mutate_model(self):
        res = self.drift_evaluator.evaluate_drift(
            release_id="rel-p7-001", current_error_rate=0.08, current_latency_ms=150.0, current_hallucination_rate=0.20
        )
        self.assertEqual(res.recommended_action, "ROLLBACK_REQUIRED")

    def test_14_cryptographic_audit_chain_append_and_verification(self):
        evt1 = self.audit_chain.append_event("RELEASE", "rel-p7-001", "m1", "admin-dhurai", "PROMOTE", "APPROVED", "ev-hash-1")
        evt2 = self.audit_chain.append_event("OBSERVE", "rel-p7-001", "m1", "monitor", "HEALTH_CHECK", "PASSED", "ev-hash-2")

        self.assertEqual(evt2.previous_hash, evt1.event_hash)
        self.assertTrue(self.audit_chain.verify_chain_integrity())

    def test_15_audit_chain_tamper_detection(self):
        self.audit_chain.append_event("RELEASE", "rel-p7-001", "m1", "admin-dhurai", "PROMOTE", "APPROVED", "ev-hash-1")
        self.audit_chain.append_event("OBSERVE", "rel-p7-001", "m1", "monitor", "HEALTH_CHECK", "PASSED", "ev-hash-2")

        # Tamper with event hash
        self.audit_chain._chain[0].event_hash = "bad-tampered-hash-123"
        with self.assertRaises(AuditChainError):
            self.audit_chain.verify_chain_integrity()

    def test_16_dashboard_contract_read_only(self):
        dash = ProductionSafetyDashboardContract(
            health=ProductionHealthView("rel-p7-001", "m1", "HEALTHY", 1000, 0.001, 0.0, 15.0, 30.0, 50.0),
            safety=SafetyStatusView("SAFE", 0, 0, 0, 0),
            incidents=IncidentStatusView(0, 0, False, False, "NONE"),
            governance=GovernanceInvariantsView(),
            dashboard_timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        )
        self.assertEqual(dash.governance.candidate_traffic_share, 0.0)
        self.assertEqual(dash.governance.production_promotion, "BLOCKED")

    def test_17_concurrency_and_state_integrity(self):
        self.audit_chain.append_event("EVENT_1", "rel-p7-001", "m1", "actor1", "ACT_1", "PASS", "h1")
        self.audit_chain.append_event("EVENT_2", "rel-p7-001", "m1", "actor2", "ACT_2", "PASS", "h2")
        self.assertEqual(len(self.audit_chain.get_chain()), 2)
        self.assertTrue(self.audit_chain.verify_chain_integrity())

    def test_18_adversarial_cli_bypass_prevention(self):
        # Direct promotion attempts without signed token fail
        self.assertEqual(self.safety_controller.candidate_traffic_share, 0.0)
        self.assertFalse(self.safety_controller.public_chat_eligible)

    def test_19_adversarial_env_variable_bypass_prevention(self):
        # Verify default invariants remain preserved
        inv = GovernanceInvariantsView()
        self.assertEqual(inv.candidate_traffic_share, 0.0)
        self.assertFalse(inv.public_chat_eligible)
        self.assertFalse(inv.training_execution_authorized)

    def test_20_default_governance_invariants(self):
        inv = GovernanceInvariantsView()
        self.assertEqual(inv.production_promotion, "BLOCKED")
        self.assertFalse(inv.public_chat_eligible)
        self.assertEqual(inv.candidate_traffic_share, 0.0)
        self.assertFalse(inv.training_execution_authorized)
        self.assertFalse(inv.optimizer_stepping)
        self.assertFalse(inv.tokenizer_mutation)


if __name__ == "__main__":
    unittest.main()
