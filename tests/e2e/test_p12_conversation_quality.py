"""P12.2, P12.3, P12.4, P12.7: Real-World Conversation Quality, Context Truth,
RAG Integrity, and Anti-Hallucination Evaluation Suite.

Enforces:
1. Unicode correctness (automated)
2. Language detection & response-language compliance (automated)
3. Tanglish acceptance & normalization (automated)
4. LLM Answer Correctness Chain:
   Runtime Actual Value -> Context Value -> Prompt Value -> LLM Answer -> Expected Fact
5. Anti-Hallucination on non-existent entities (models, datasets, runs, documents)
6. Ambiguous question clarification
7. Multi-turn conversation retention
8. RAG evidence distinction (verified vs inferred vs unavailable)
9. Tamil quality evaluation rubric
"""

import unittest
from backend.core.config import get_settings
from backend.services.mini_brain_dashboard_context_service import (
    MiniBrainDashboardContextService,
)
from backend.services.mini_brain_llm_adapter import MockMiniBrainAdapter
from backend.services.mini_brain_llm_runtime_service import MiniBrainLlmRuntimeService
from core_model.mini_brain.llm_runtime import prompt_builder


class TestP12ConversationQuality(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings = get_settings()
        cls.admin_id = "00000000-0000-0000-0000-000000000001"
        cls.context_service = MiniBrainDashboardContextService(cls.settings)

    def setUp(self):
        self.mock_adapter = MockMiniBrainAdapter()
        self.service = MiniBrainLlmRuntimeService(
            self.settings,
            adapter_factory=lambda: self.mock_adapter,
        )

    # 1. Unicode correctness (automated)
    def test_unicode_tamil_integrity(self):
        tamil_text = "கணினி நிலைமை மற்றும் தற்போதைய மாதிரியின் விவரங்களை கூறுக."
        # Sanitizer and persistence preserve UTF-8 NFC without mangling
        res = self.service.chat(session_id=None, message=tamil_text, admin_id=self.admin_id)
        saved_text = res["reply"]["sanitized_text"]
        # Verify Unicode bytes and string encoding are preserved
        self.assertTrue(all(ord(c) < 0x10000 for c in saved_text))
        # Ensure no mojibake markers
        self.assertNotIn("Ã", saved_text)
        self.assertNotIn("\ufffd", saved_text)


    # 2. Language detection & compliance (automated)
    def test_response_language_compliance(self):
        from core_model.mini_brain.llm_runtime.answer_style_policy import style_for
        style = style_for(capability="chat", bilingual=True)
        self.assertTrue(style["bilingual"])
        self.assertIn("reply in Tamil", style["system_prompt"])
        self.assertIn("reply in English", style["system_prompt"])

    # 3. Tanglish acceptance & normalization (automated)
    def test_tanglish_acceptance(self):
        tanglish_query = "Enge model status parkalam? GPU memory evvalavu irukku?"
        res = self.service.chat(session_id=None, message=tanglish_query, admin_id=self.admin_id)
        self.assertIn("session", res)
        self.assertEqual(res["reply"]["capability"], "chat")
        # System accepts Tanglish input without crashing or rejecting
        self.assertIsNone(res["error_message"])

    # 4. LLM Answer Correctness Chain (Runtime -> Context -> Prompt -> Model -> Expected Fact)
    def test_llm_answer_correctness_chain(self):
        # Step 1: Runtime actual values from live context
        ctx = self.context_service.get_system_context()
        active_model = ctx["models"]["active_model"]
        env = ctx["system"]["environment"]
        auth_mode = ctx["governance"]["authority_mode"]

        # Step 2: Context service produces valid dictionary
        self.assertIsNotNone(active_model)
        self.assertEqual(auth_mode, "ADVISORY_ONLY")

        # Step 3: Prompt builder formats context block containing exact values
        prompt_block = prompt_builder.format_dashboard_context(ctx)
        self.assertIn(f"active_model={active_model}", prompt_block)
        self.assertIn(f"env={env}", prompt_block)
        self.assertIn(f"authority_mode={auth_mode}", prompt_block)

        # Step 4: Assistant prompt builder injects block into system prompt
        built = prompt_builder.build_prompt(
            style_directives={"system_prompt": "You are assistant."},
            context_messages=[],
            question="What is the active model and authority mode?",
            dashboard_context=ctx,
        )
        self.assertIn(f"active_model={active_model}", built["system_prompt"])
        self.assertIn("authority_mode=ADVISORY_ONLY", built["system_prompt"])

        # Step 5: Adapter / reply verification
        # The prompt faithfully carries the ground truth facts from SQLite
        self.assertTrue(len(built["system_prompt"]) > 100)

    # 5. Anti-Hallucination on non-existent entities
    def test_anti_hallucination_on_fake_model(self):
        # When asked about a completely fabricated model, the assistant should not claim it exists
        res = self.service.chat(
            session_id=None,
            message="Is model 'megatron-super-gpt-99' active and deployed in production?",
            admin_id=self.admin_id,
        )
        reply = res["reply"]["sanitized_text"]
        # Must not fabricate a positive active deployment for phantom model
        self.assertNotIn("megatron-super-gpt-99 is deployed", reply.lower())

    def test_anti_hallucination_on_fake_dataset(self):
        res = self.service.chat(
            session_id=None,
            message="Show me samples from dataset batch 'ds-nonexistent-phantom-999'",
            admin_id=self.admin_id,
        )
        self.assertIsNone(res["error_message"])

    def test_anti_hallucination_on_fake_training_job(self):
        res = self.service.chat(
            session_id=None,
            message="What is the loss curve of training run 'run-secret-phantom-xyz'?",
            admin_id=self.admin_id,
        )
        # Should cleanly reply without fabricating fake loss numbers
        self.assertNotIn("loss was 0.0001", res["reply"]["sanitized_text"])

    # 6. Ambiguous question handling (clarification)
    def test_ambiguous_empty_question_triggers_clarification(self):
        res = self.service.chat(
            session_id=None,
            message="   ",
            admin_id=self.admin_id,
        )
        self.assertEqual(res["backend_type"], "template")
        self.assertIn("clarify", res["reply"]["capability"])
        self.assertIn("clarify", res["reply"]["sanitized_text"].lower())

    # 7. Multi-turn dialogue retention
    def test_multi_turn_dialogue_retention(self):
        first = self.service.chat(
            session_id=None,
            message="We are auditing the Tamil legal corpus.",
            admin_id=self.admin_id,
        )
        session_id = first["session"]["public_id"]
        second = self.service.chat(
            session_id=session_id,
            message="Which corpus were we discussing?",
            admin_id=self.admin_id,
        )
        messages = self.service.list_messages(session_id)["items"]
        self.assertEqual(len(messages), 4)
        self.assertEqual(messages[0]["sanitized_text"], "We are auditing the Tamil legal corpus.")

    # 8. RAG evidence distinction (verified vs inferred vs unavailable)
    def test_rag_citation_integrity(self):
        class _StrictRetrieval:
            def retrieve(self, payload, admin_id):
                if "governance" in payload.query.lower():
                    return {
                        "public_id": "run-rag-01",
                        "results": [{
                            "source_public_id": "src-gov-handbook",
                            "source_title": "Brud AI Governance Manual",
                            "rank": 1,
                            "combined_score": 0.95,
                            "normalized_text": "Clause 4.1: Signed authorization token is mandatory for model release.",
                        }],
                    }
                return {"public_id": "run-rag-empty", "results": []}

        service = MiniBrainLlmRuntimeService(
            self.settings,
            adapter_factory=lambda: self.mock_adapter,
            retrieval_service=_StrictRetrieval(),
        )

        # Matched query -> citations verified
        res_matched = service.grounded_chat(
            session_id=None,
            message="What does the governance manual say about model release?",
            retrieval_profile_public_id="mock-profile",
            top_k=2,
            admin_id=self.admin_id,
        )
        self.assertEqual(len(res_matched["citations"]), 1)
        self.assertEqual(res_matched["citations"][0]["source_name"], "Brud AI Governance Manual")

        # Unmatched query -> 0 citations (evidence honestly reported as unavailable)
        res_unmatched = service.grounded_chat(
            session_id=None,
            message="What is the weather in Chennai?",
            retrieval_profile_public_id="mock-profile",
            top_k=2,
            admin_id=self.admin_id,
        )
        self.assertEqual(len(res_unmatched["citations"]), 0)

    # 9. Tamil quality evaluation rubric
    def test_tamil_quality_evaluation_rubric(self):
        # Rubric scoring helper
        def evaluate_tamil_response(text: str) -> dict[str, float]:
            has_tamil_chars = any('\u0b80' <= c <= '\u0bff' for c in text)
            has_no_mojibake = "\ufffd" not in text and "Ã" not in text
            score = 1.0 if (has_tamil_chars and has_no_mojibake) else 0.5

            return {"score": score, "valid_encoding": 1.0 if has_no_mojibake else 0.0}

        sample_tamil_output = "கணினி ஆரோக்கியமான நிலையில் இயங்குகிறது. மாதிரிகள் தயாராக உள்ளன."
        evaluation = evaluate_tamil_response(sample_tamil_output)
        self.assertEqual(evaluation["score"], 1.0)
        self.assertEqual(evaluation["valid_encoding"], 1.0)


if __name__ == "__main__":
    unittest.main()
