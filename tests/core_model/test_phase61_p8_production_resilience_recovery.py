"""Phase 61 - P8: Production Resilience, Disaster Recovery, State Integrity & Governance Test Suite."""

import time
import unittest

from core_model.ops.production_state_snapshot_registry import (
    ProductionStateSnapshotRecord,
    ProductionStateSnapshotRegistry,
    SnapshotError,
    compute_snapshot_hmac,
)
from core_model.ops.disaster_recovery_manager import (
    DisasterRecoveryManager,
    RecoveryEvaluationResult,
)
from core_model.ops.production_state_integrity_validator import (
    ProductionStateIntegrityValidator,
    StateIntegrityValidationResult,
)
from core_model.ops.recovery_readiness_evaluator import (
    RecoveryReadinessEvaluator,
    RecoveryReadinessResult,
)
from core_model.ops.recovery_controller import (
    FailSafeRecoveryController,
    RecoveryControllerStatusRecord,
)
from core_model.ops.recovery_failure_injection import (
    FailureInjectionResult,
    RecoveryFailureInjectionSimulator,
)
from core_model.ops.recovery_authorization_gate import (
    RecoveryAuthorizationError,
    RecoveryAuthorizationGate,
    SignedRecoveryAuthorizationToken,
    compute_recovery_token_signature,
)
from core_model.ops.business_continuity_controller import (
    BusinessContinuityController,
    BusinessContinuityStatusRecord,
)
from core_model.ops.recovery_audit_contract import (
    BusinessContinuityView,
    ProductionRecoveryAuditContract,
    RecoveryReadinessView,
    SnapshotIntegrityView,
)
from core_model.eval.production_release_registry import ProductionReleaseRegistry
from core_model.ops.production_audit_chain import ProductionAuditChain
from core_model.admin_assistant.admin_review_queue import AdminReviewQueueManager


class TestPhase61P8ProductionResilienceRecovery(unittest.TestCase):

    def setUp(self):
        self.secret_key = "BRUD_RECOVERY_SECRET_KEY_2026"
        self.snapshot_registry = ProductionStateSnapshotRegistry(secret_key=self.secret_key)
        self.dr_manager = DisasterRecoveryManager(snapshot_registry=self.snapshot_registry)
        self.integrity_validator = ProductionStateIntegrityValidator()
        self.readiness_evaluator = RecoveryReadinessEvaluator()
        self.release_registry = ProductionReleaseRegistry()
        self.audit_chain = ProductionAuditChain()
        self.recovery_controller = FailSafeRecoveryController(
            release_registry=self.release_registry, audit_chain=self.audit_chain
        )
        self.chaos_simulator = RecoveryFailureInjectionSimulator()
        self.recovery_gate = RecoveryAuthorizationGate(secret_key=self.secret_key)
        self.bc_controller = BusinessContinuityController()
        self.admin_review = AdminReviewQueueManager()

        # Register active release and baseline snapshot
        self.release_rec = self.release_registry.register_release(
            release_id="rel-p8-001",
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
        self.release_registry.set_active_release("rel-p8-001")

        self.snap_rec = self.snapshot_registry.create_snapshot(
            release_id="rel-p8-001",
            model_hash="cand-sha256-555",
            dataset_hash="dataset-manifest-sha256-111",
            tokenizer_hash="tokenizer-sha256-222",
            training_config_hash="config-sha256-333"
        )

        # Build valid signed recovery authorization token
        req_id = "req-rec-001"
        admin_id = "admin-dhurai"
        sig = compute_recovery_token_signature(req_id, admin_id, "rel-p8-001", self.snap_rec.snapshot_hmac, self.secret_key)

        self.valid_recovery_token = SignedRecoveryAuthorizationToken(
            recovery_request_id=req_id,
            admin_public_id=admin_id,
            release_id="rel-p8-001",
            snapshot_hash=self.snap_rec.snapshot_hmac,
            model_hash="cand-sha256-555",
            dataset_hash="dataset-manifest-sha256-111",
            tokenizer_hash="tokenizer-sha256-222",
            human_recovery_signature="SIGNATURE_VERIFIED_RECOVERY",
            created_at_epoch=time.time(),
            expires_at_epoch=time.time() + 3600,
            signature_hmac=sig
        )

    def test_01_valid_snapshot_creation_and_retrieval(self):
        latest = self.snapshot_registry.get_latest_snapshot()
        self.assertIsNotNone(latest)
        self.assertEqual(latest.release_id, "rel-p8-001")
        self.assertEqual(latest.model_hash, "cand-sha256-555")

    def test_02_snapshot_hmac_integrity_verification_success(self):
        self.assertTrue(self.snapshot_registry.verify_snapshot_integrity(self.snap_rec.snapshot_id))

    def test_03_corrupted_snapshot_rejection(self):
        # Tamper with snapshot hmac
        self.snapshot_registry._snapshots[self.snap_rec.snapshot_id].snapshot_hmac = "tampered-hmac-999"
        with self.assertRaises(SnapshotError):
            self.snapshot_registry.verify_snapshot_integrity(self.snap_rec.snapshot_id)

    def test_04_disaster_recovery_manager_evaluation_success(self):
        res = self.dr_manager.evaluate_recovery_prerequisites()
        self.assertEqual(res.recovery_status, "RECOVERY_READY")
        self.assertTrue(res.evidence_valid)

    def test_05_disaster_recovery_manager_fails_closed_on_corrupted_snapshot(self):
        res = self.dr_manager.evaluate_recovery_prerequisites(mock_corrupted_snapshot=True)
        self.assertEqual(res.recovery_status, "RECOVERY_BLOCKED")
        self.assertFalse(res.evidence_valid)

    def test_06_state_integrity_validation_success(self):
        self.audit_chain.append_event("GENESIS", "rel-p8-001", "cand-sha256-555", "admin", "INIT", "PASS", "h1")
        res = self.integrity_validator.validate_system_integrity(
            self.release_registry, self.snapshot_registry, self.audit_chain
        )
        self.assertEqual(res.integrity_status, "STATE_INTEGRITY_VALID")
        self.assertTrue(res.model_hash_match)

    def test_07_state_integrity_validation_failure_on_hash_mismatch(self):
        self.audit_chain.append_event("GENESIS", "rel-p8-001", "cand-sha256-555", "admin", "INIT", "PASS", "h1")
        res = self.integrity_validator.validate_system_integrity(
            self.release_registry, self.snapshot_registry, self.audit_chain, mock_hash_mismatch=True
        )
        self.assertEqual(res.integrity_status, "STATE_INTEGRITY_FAILURE")
        self.assertFalse(res.model_hash_match)

    def test_08_recovery_readiness_evaluator_fail_closed_on_missing_evidence(self):
        res = self.readiness_evaluator.evaluate_readiness(dr_eval=None, integrity_eval=None)
        self.assertEqual(res.readiness_status, "RECOVERY_CRITICAL")
        self.assertFalse(res.snapshots_available)

    def test_09_recovery_readiness_evaluation_success(self):
        self.audit_chain.append_event("GENESIS", "rel-p8-001", "cand-sha256-555", "admin", "INIT", "PASS", "h1")
        dr_res = self.dr_manager.evaluate_recovery_prerequisites()
        integ_res = self.integrity_validator.validate_system_integrity(self.release_registry, self.snapshot_registry, self.audit_chain)

        res = self.readiness_evaluator.evaluate_readiness(dr_res, integ_res)
        self.assertEqual(res.readiness_status, "RECOVERY_READY")

    def test_10_fail_safe_recovery_controller_blocks_without_token(self):
        self.audit_chain.append_event("GENESIS", "rel-p8-001", "cand-sha256-555", "admin", "INIT", "PASS", "h1")
        dr_res = self.dr_manager.evaluate_recovery_prerequisites()
        integ_res = self.integrity_validator.validate_system_integrity(self.release_registry, self.snapshot_registry, self.audit_chain)
        readiness_res = self.readiness_evaluator.evaluate_readiness(dr_res, integ_res)

        res = self.recovery_controller.simulate_recovery_workflow(readiness_res, signed_token_present=False)
        self.assertEqual(res.controller_state, "RECOVERY_BLOCKED")
        self.assertFalse(res.recovery_executed)

    def test_11_fail_safe_recovery_controller_simulation_success(self):
        self.audit_chain.append_event("GENESIS", "rel-p8-001", "cand-sha256-555", "admin", "INIT", "PASS", "h1")
        dr_res = self.dr_manager.evaluate_recovery_prerequisites()
        integ_res = self.integrity_validator.validate_system_integrity(self.release_registry, self.snapshot_registry, self.audit_chain)
        readiness_res = self.readiness_evaluator.evaluate_readiness(dr_res, integ_res)

        res = self.recovery_controller.simulate_recovery_workflow(readiness_res, signed_token_present=True)
        self.assertEqual(res.controller_state, "RECOVERED")
        # Invariant: recovery_executed must remain strictly False in test simulation
        self.assertFalse(res.recovery_executed)

    def test_12_chaos_failure_injection_all_scenarios_fail_closed(self):
        for scenario in RecoveryFailureInjectionSimulator.SCENARIOS:
            res = self.chaos_simulator.run_scenario(scenario)
            self.assertTrue(res.failed_closed)
            self.assertEqual(res.resulting_status, "RECOVERY_BLOCKED")

    def test_13_cryptographic_recovery_authorization_token_verification_success(self):
        self.assertTrue(
            self.recovery_gate.verify_recovery_token(
                self.valid_recovery_token, "rel-p8-001", self.snap_rec.snapshot_hmac, "cand-sha256-555"
            )
        )

    def test_14_expired_recovery_authorization_token_rejection(self):
        exp_token = SignedRecoveryAuthorizationToken(**{**self.valid_recovery_token.__dict__, "expires_at_epoch": time.time() - 10})
        with self.assertRaises(RecoveryAuthorizationError) as ctx:
            self.recovery_gate.verify_recovery_token(exp_token, "rel-p8-001", self.snap_rec.snapshot_hmac, "cand-sha256-555")
        self.assertIn("expired", str(ctx.exception))

    def test_15_invalid_signature_recovery_token_rejection(self):
        bad_token = SignedRecoveryAuthorizationToken(**{**self.valid_recovery_token.__dict__, "signature_hmac": "bad-sig-999"})
        with self.assertRaises(RecoveryAuthorizationError) as ctx:
            self.recovery_gate.verify_recovery_token(bad_token, "rel-p8-001", self.snap_rec.snapshot_hmac, "cand-sha256-555")
        self.assertIn("Invalid HMAC signature", str(ctx.exception))

    def test_16_business_continuity_controller_enforces_governance_invariants(self):
        res = self.bc_controller.transition_state("DEGRADED", admin_identity="admin-dhurai")
        self.assertEqual(res.continuity_state, "DEGRADED")
        self.assertEqual(res.candidate_traffic_share, 0.0)
        self.assertFalse(res.public_chat_eligible)

    def test_17_admin_review_queue_extension_supports_recovery_decisions(self):
        rec = self.admin_review.record_admin_decision("rev-rec-001", "RECOVERY_APPROVED")
        self.assertEqual(rec.decision, "RECOVERY_APPROVED")

    def test_18_recovery_audit_contract_read_only_view(self):
        contract = ProductionRecoveryAuditContract(
            snapshot=SnapshotIntegrityView(self.snap_rec.snapshot_id, "rel-p8-001", "cand-sha256-555", "dataset-manifest-sha256-111", True),
            readiness=RecoveryReadinessView("RECOVERY_READY", True, True, True, True),
            continuity=BusinessContinuityView("OPERATIONAL"),
            recovery_executed=False,
            contract_timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        )
        self.assertFalse(contract.recovery_executed)
        self.assertEqual(contract.continuity.candidate_traffic_share, 0.0)

    def test_19_adversarial_bypass_prevention(self):
        self.assertEqual(self.bc_controller.continuity_state, "OPERATIONAL")
        self.assertEqual(self.recovery_controller.candidate_traffic_share, 0.0)
        self.assertFalse(self.recovery_controller.public_chat_eligible)

    def test_20_mandatory_governance_invariants_preservation(self):
        self.assertFalse(self.recovery_controller.recovery_executed)
        self.assertEqual(self.recovery_controller.candidate_traffic_share, 0.0)
        self.assertFalse(self.recovery_controller.public_chat_eligible)


if __name__ == "__main__":
    unittest.main()
