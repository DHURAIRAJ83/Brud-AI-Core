"""P11.8 Live Smoke Test Suite for Brud AI Mini Brain LLM Runtime.

Tests 11 live real-world administrative interactions:
1. தமிழ் கேள்வி (Tamil question)
2. English question
3. Tamil + English mixed question
4. System status enquiry
5. Active model enquiry
6. Dataset status enquiry
7. Training status enquiry (locked check)
8. RAG question (knowledge base grounded)
9. Memory follow-up turn
10. Provider failure graceful handling
11. Local failure / unavailable fallback handling
"""

import unittest
from starlette.testclient import TestClient
from backend.core.config import get_settings
from backend.services.mini_brain_llm_adapter import MockMiniBrainAdapter
from backend.services.mini_brain_llm_runtime_service import MiniBrainLlmRuntimeService




class TestLiveSmokeScenarios(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings = get_settings()
        cls.admin_id = "00000000-0000-0000-0000-000000000001"
        cls.headers = {
            "x-admin-id": cls.admin_id,
            "x-csrf-token": "test-csrf-token",
        }


    def setUp(self):
        self.mock_adapter = MockMiniBrainAdapter()
        self.service = MiniBrainLlmRuntimeService(
            self.settings,
            adapter_factory=lambda: self.mock_adapter,
        )

    # 1. தமிழ் கேள்வி
    def test_smoke_01_tamil_question(self):
        res = self.service.chat(
            session_id=None,
            message="கணினி நிலைமை மற்றும் தற்போதைய மாதிரியின் விவரங்களை கூறுக",
            admin_id=self.admin_id,
        )
        self.assertIn("session", res)
        self.assertIn("reply", res)
        self.assertEqual(res["reply"]["capability"], "chat")
        self.assertTrue(len(res["reply"]["sanitized_text"]) > 0)

    # 2. English question
    def test_smoke_02_english_question(self):
        res = self.service.chat(
            session_id=None,
            message="What is the overall system operational health?",
            admin_id=self.admin_id,
        )
        self.assertIn("session", res)
        self.assertEqual(res["reply"]["capability"], "chat")

    # 3. Tamil + English mixed input
    def test_smoke_03_tamil_english_mixed(self):
        res = self.service.chat(
            session_id=None,
            message="Model inference latency மற்றும் GPU memory status என்ன?",
            admin_id=self.admin_id,
        )
        self.assertIn("session", res)
        self.assertIn("reply", res)

    # 4. System status enquiry
    def test_smoke_04_system_status(self):
        from backend.services.mini_brain_dashboard_context_service import (
            MiniBrainDashboardContextService,
        )
        ctx_service = MiniBrainDashboardContextService(self.settings)
        overview = ctx_service.get_system_context()
        self.assertIn("system", overview)
        self.assertIn("models", overview)
        res = self.service.chat(
            session_id=None,
            message="Show me the health status of all subsystems",
            admin_id=self.admin_id,
        )
        self.assertIn("reply", res)

    # 5. Active model enquiry
    def test_smoke_05_active_model(self):
        diagnostics = self.service.diagnostics()
        self.assertIn("local_available", diagnostics)
        self.assertIn("configured_model_path", diagnostics)
        res = self.service.chat(
            session_id=None,
            message="Which LLM model is currently loaded in memory?",
            admin_id=self.admin_id,
        )
        self.assertIn("reply", res)

    # 6. Dataset status enquiry
    def test_smoke_06_dataset_status(self):
        res = self.service.chat(
            session_id=None,
            message="List recent dataset generation batches and sample counts",
            admin_id=self.admin_id,
        )
        self.assertIn("reply", res)

    # 7. Training status enquiry (locked check)
    def test_smoke_07_training_status_locked(self):
        from core_model.admin_assistant.chat_action_bridge import (
            _BLOCKED_MESSAGE_SUBSTRINGS,
            match_actionable_intent,
        )
        self.assertIn("train", _BLOCKED_MESSAGE_SUBSTRINGS)
        # Direct action execution is blocked
        intent = match_actionable_intent("train this model immediately")
        self.assertIsNone(intent)
        # Runtime chat does not trigger any autonomous mutation
        res = self.service.chat(
            session_id=None,
            message="Train production model now",
            admin_id=self.admin_id,
        )
        self.assertNotEqual(res["backend_type"], "tool_executed")


    # 8. RAG question (knowledge base grounded)
    def test_smoke_08_rag_grounded_question(self):
        class _StubRag:
            def retrieve(self, payload, admin_id):
                return {
                    "public_id": "rag-smoke-run",
                    "results": [{
                        "source_public_id": "src-smoke-1",
                        "source_title": "Production Deployment Policy",
                        "rank": 1,
                        "combined_score": 0.94,
                        "normalized_text": "Model promotion strictly requires 17 automated benchmark passes and signed governance authorization.",
                    }],
                }

        service = MiniBrainLlmRuntimeService(
            self.settings,
            adapter_factory=lambda: self.mock_adapter,
            retrieval_service=_StubRag(),
        )
        res = service.grounded_chat(
            session_id=None,
            message="What are the promotion requirements for production models?",
            retrieval_profile_public_id="mock-smoke-profile",
            top_k=2,
            admin_id=self.admin_id,
        )
        self.assertEqual(len(res["citations"]), 1)
        self.assertEqual(res["citations"][0]["source_name"], "Production Deployment Policy")

    # 9. Memory follow-up turn
    def test_smoke_09_memory_followup(self):
        first = self.service.chat(
            session_id=None,
            message="We are auditing the Tamil ASR pipeline.",
            admin_id=self.admin_id,
        )
        session_id = first["session"]["public_id"]
        second = self.service.chat(
            session_id=session_id,
            message="What was the pipeline we just discussed?",
            admin_id=self.admin_id,
        )
        history = self.service.list_messages(session_id)["items"]
        self.assertEqual(len(history), 4)  # user1, bot1, user2, bot2

    # 10. Provider failure graceful handling
    def test_smoke_10_provider_failure(self):
        class FailingAdapter:
            def is_available(self):
                return True
            def generate(self, messages, max_tokens=1024, temperature=0.2):
                return {
                    "text": "",
                    "backend_type": "external",
                    "tokens_generated": 0,
                    "latency_ms": 12.0,
                    "error_message": "Cloud provider rate limit exceeded (HTTP 429)",
                }

        service = MiniBrainLlmRuntimeService(
            self.settings,
            adapter_factory=lambda: FailingAdapter(),
        )
        res = service.chat(
            session_id=None,
            message="Status check under provider load",
            admin_id=self.admin_id,
        )
        self.assertIsNotNone(res["error_message"])
        self.assertIn("rate limit", res["error_message"].lower())

    # 11. Local backend routing truthfulness
    def test_smoke_11_local_routing_truthfulness(self):
        service = MiniBrainLlmRuntimeService(self.settings)
        backend = service._resolve_backend(execution_mode="local")
        self.assertIn(backend["backend_type"], ["local", "unavailable"])
        if backend["backend_type"] == "local":
            self.assertTrue(backend["adapter"].is_available())
        else:
            self.assertIn("not available", backend["reason"].lower())


if __name__ == "__main__":
    unittest.main()

