"""Phase 61: Admin Assistant Governance Route Test Suite."""

import unittest
from backend.core.config import Settings
from backend.services.admin_assistant_service import AdminAssistantService


class TestAdminAssistantGovernanceRoute(unittest.TestCase):

    def setUp(self):
        self.settings = Settings()
        self.service = AdminAssistantService(self.settings)

    def test_01_get_governance_status_returns_canonical_contract_structure(self):
        res = self.service.get_governance_status()
        self.assertEqual(res["status"], "success")
        self.assertIn("governance", res)
        self.assertIn("activation_readiness", res)
        self.assertEqual(res["admin_assistant_authority"], "ADVISORY_ONLY")

        gov = res["governance"]
        self.assertEqual(gov["invariants"]["production_promotion"], "BLOCKED")
        self.assertFalse(gov["invariants"]["public_chat_eligible"])
        self.assertEqual(gov["invariants"]["candidate_traffic_share"], 0.0)
        self.assertFalse(gov["invariants"]["training_execution_authorized"])
        self.assertFalse(gov["invariants"]["optimizer_stepping"])
        self.assertFalse(gov["invariants"]["tokenizer_mutation"])
        self.assertFalse(gov["invariants"]["recovery_executed"])

        readiness = res["activation_readiness"]
        self.assertEqual(readiness["p0_p10g_canonical_components"], "48/48 VERIFIED")
        self.assertEqual(readiness["production_state"], "UNTOUCHED & LOCKED")
        self.assertTrue(readiness["awaiting_genuine_human_authorization"])
        self.assertEqual(readiness["final_verdict"], "BLOCKED_PENDING_HUMAN_AUTHORIZATION")
        self.assertEqual(len(readiness["activation_blockers"]), 4)

    def test_02_get_governance_status_zero_secret_exposure(self):
        res = self.service.get_governance_status()
        raw_dump = str(res).lower()
        self.assertNotIn("secret_key", raw_dump)
        self.assertNotIn("private_key", raw_dump)
        self.assertNotIn("hmac_secret", raw_dump)
        self.assertNotIn("signature_key", raw_dump)


if __name__ == "__main__":
    unittest.main()
