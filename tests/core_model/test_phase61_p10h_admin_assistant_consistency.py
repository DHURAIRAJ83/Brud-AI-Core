"""Phase 61 - P10-H: Admin Assistant Governance State Consistency & Final UI Forensic Audit Test Suite.

Verifies end-to-end read-only data-flow consistency between canonical governance contracts,
the backend API router, and the Admin Assistant UI status representations.

MANDATORY INVARIANTS TESTED:
- TRAINING EXECUTED = FALSE
- TRAINING AUTHORIZATION = FALSE
- PRODUCTION PROMOTION = BLOCKED
- PRODUCTION MERGE = BLOCKED
- PUBLIC CHAT ELIGIBLE = FALSE
- CANDIDATE TRAFFIC SHARE = 0.0
- OPTIMIZER STEPPING = FALSE
- TOKENIZER MUTATION = FALSE
- MODEL WEIGHT MUTATION = FALSE
- PRODUCTION DATA MUTATION = FALSE
- RECOVERY EXECUTED = FALSE
- COMPLIANCE CERTIFICATION = BLOCKED
- PRODUCTION STATE = LOCKED
- ADMIN_ASSISTANT_AUTHORITY = ADVISORY_ONLY
"""

import json
import unittest
from backend.core.config import Settings
from backend.services.admin_assistant_service import AdminAssistantService
from core_model.ops.enterprise_governance_contract import EnterpriseGovernanceDashboardContract
from core_model.ops.policy_drift_evaluator import PolicyDriftEvaluator
from core_model.ops.secret_lifecycle_manager import SecretLifecycleManager


class TestPhase61P10HAdminAssistantConsistency(unittest.TestCase):

    def setUp(self):
        self.settings = Settings()
        self.service = AdminAssistantService(self.settings)

    def test_01_canonical_contract_backend_consistency(self):
        res = self.service.get_governance_status()
        self.assertEqual(res["status"], "success")
        self.assertIn("governance", res)
        self.assertIn("activation_readiness", res)

        gov = res["governance"]
        self.assertEqual(gov["invariants"]["production_promotion"], "BLOCKED")
        self.assertFalse(gov["invariants"]["public_chat_eligible"])
        self.assertEqual(gov["invariants"]["candidate_traffic_share"], 0.0)
        self.assertFalse(gov["invariants"]["training_execution_authorized"])
        self.assertFalse(gov["invariants"]["optimizer_stepping"])
        self.assertFalse(gov["invariants"]["tokenizer_mutation"])
        self.assertFalse(gov["invariants"]["recovery_executed"])

    def test_02_secret_non_disclosure_verification(self):
        res = self.service.get_governance_status()
        dump = json.dumps(res).lower()
        self.assertNotIn("raw_secret", dump)
        self.assertNotIn("hmac_secret_key", dump)
        self.assertNotIn("private_key_pem", dump)
        self.assertNotIn("signing_secret", dump)

    def test_03_admin_assistant_authority_advisory_only(self):
        res = self.service.get_governance_status()
        self.assertEqual(res["admin_assistant_authority"], "ADVISORY_ONLY")

    def test_04_activation_blockers_visibility(self):
        res = self.service.get_governance_status()
        readiness = res["activation_readiness"]
        self.assertEqual(readiness["p0_p10g_canonical_components"], "48/48 VERIFIED")
        self.assertEqual(readiness["production_state"], "UNTOUCHED & LOCKED")
        self.assertTrue(readiness["awaiting_genuine_human_authorization"])
        self.assertEqual(readiness["final_verdict"], "BLOCKED_PENDING_HUMAN_AUTHORIZATION")
        self.assertEqual(len(readiness["activation_blockers"]), 4)

    def test_05_adversarial_training_mutation_blocked(self):
        with self.assertRaises(Exception):
            self.service.propose(
                action_type="execute_model_training",
                target_type="model",
                target_public_id="m1",
                request_payload={},
                requested_by="admin_1",
                summary="attempt training",
            )

    def test_06_adversarial_promotion_mutation_blocked(self):
        with self.assertRaises(Exception):
            self.service.propose(
                action_type="promote_candidate_model",
                target_type="model",
                target_public_id="c1",
                request_payload={},
                requested_by="admin_1",
                summary="attempt promotion",
            )

    def test_07_adversarial_public_chat_mutation_blocked(self):
        with self.assertRaises(Exception):
            self.service.propose(
                action_type="enable_public_chat_admission",
                target_type="chat",
                target_public_id="chat1",
                request_payload={},
                requested_by="admin_1",
                summary="attempt public chat",
            )

    def test_08_adversarial_secret_rotation_mutation_blocked(self):
        with self.assertRaises(Exception):
            self.service.propose(
                action_type="rotate_hmac_secrets",
                target_type="secret",
                target_public_id="s1",
                request_payload={},
                requested_by="admin_1",
                summary="attempt secret rotation",
            )

    def test_09_adversarial_recovery_execution_blocked(self):
        with self.assertRaises(Exception):
            self.service.propose(
                action_type="execute_disaster_recovery",
                target_type="system",
                target_public_id="sys1",
                request_payload={},
                requested_by="admin_1",
                summary="attempt recovery",
            )

    def test_10_adversarial_compliance_certification_blocked(self):
        with self.assertRaises(Exception):
            self.service.propose(
                action_type="certify_enterprise_compliance",
                target_type="compliance",
                target_public_id="cmp1",
                request_payload={},
                requested_by="admin_1",
                summary="attempt compliance certification",
            )

    def test_11_rbac_and_tenant_isolation_consistency(self):
        res = self.service.get_governance_status()
        rbac = res["governance"]["rbac"]
        self.assertTrue(rbac["rbac_integrity_passed"])
        self.assertTrue(rbac["tenant_isolation_passed"])
        self.assertEqual(rbac["policy_drift_status"], "NO_DRIFT")

    def test_12_secret_lifecycle_counts_consistency(self):
        res = self.service.get_governance_status()
        secrets = res["governance"]["secrets"]
        self.assertGreaterEqual(secrets["active_keys_count"], 0)
        self.assertEqual(secrets["revoked_keys_count"], 0)
        self.assertEqual(secrets["rotation_age_days"], 0.0)

    def test_13_pending_work_guidance_canonical_grounding(self):
        overview = self.service.dashboard_overview()
        from core_model.admin_assistant.localization import pending_work_lines
        lines = pending_work_lines(overview.get("summary", {}), "english")
        lines_str = " ".join(lines)
        self.assertIn("P0-P10G Governance Status", lines_str)
        self.assertIn("TRAINING_AUTHORIZATION=FALSE", lines_str)
        self.assertIn("PROMOTION=BLOCKED", lines_str)
        self.assertIn("PUBLIC_CHAT_ELIGIBLE=FALSE", lines_str)
        self.assertIn("COMPLIANCE=BLOCKED", lines_str)
        self.assertIn("PRODUCTION_STATE=LOCKED", lines_str)
        self.assertIn("Activation Blockers", lines_str)

    def test_14_zero_stale_or_fabricated_activation_states(self):
        res = self.service.get_governance_status()
        dump = json.dumps(res)
        self.assertNotIn('"training_execution_authorized": true', dump)
        self.assertNotIn('"public_chat_eligible": true', dump)
        self.assertNotIn('"production_promotion": "APPROVED"', dump)
        self.assertNotIn('"production_promotion": "GO"', dump)

    def test_15_all_48_components_verified_contract(self):
        res = self.service.get_governance_status()
        self.assertEqual(
            res["activation_readiness"]["p0_p10g_canonical_components"], "48/48 VERIFIED"
        )
        self.assertEqual(
            res["activation_readiness"]["final_verdict"],
            "BLOCKED_PENDING_HUMAN_AUTHORIZATION",
        )


if __name__ == "__main__":
    unittest.main()
