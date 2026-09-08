import unittest
from backend.core.config import Settings
from backend.services.mini_brain_dashboard_context_service import MiniBrainDashboardContextService
from backend.services.automated_model_evaluation_service import AutomatedModelEvaluationService
from backend.services.mini_brain_llm_runtime_service import MiniBrainLlmRuntimeService


class TestMiniBrainDashboardContextService(unittest.TestCase):
    def setUp(self):
        self.settings = Settings()
        self.service = MiniBrainDashboardContextService(self.settings)

    def test_get_system_context(self):
        context = self.service.get_system_context()
        self.assertIn("timestamp", context)
        self.assertIn("system_health", context)
        self.assertIn("providers", context)
        self.assertIn("models", context)
        self.assertIn("datasets", context)
        self.assertIn("training", context)
        self.assertIn("evaluation", context)
        self.assertIn("rag", context)
        self.assertIn("memory", context)
        self.assertIn("governance", context)
        self.assertIn("recommendations", context)
        self.assertEqual(context["governance"]["authority_mode"], "ADVISORY_ONLY")
        self.assertFalse(context["governance"]["allow_autonomous_execution"])


class TestAutomatedModelEvaluationService(unittest.TestCase):
    def setUp(self):
        self.settings = Settings()
        self.service = AutomatedModelEvaluationService(self.settings)

    def test_evaluate_candidate_model(self):
        report = self.service.run_post_training_evaluation(
            run_id="run-test-1234",
            model_version="candidate-v1",
            dataset_version="ds-test-01",
            baseline_model_version="approved-base-v1",
        )
        self.assertEqual(report.model_version, "candidate-v1")
        self.assertEqual(report.run_id, "run-test-1234")
        self.assertEqual(len(report.categories), 17)
        self.assertGreaterEqual(report.overall_score, 0.0)
        self.assertGreaterEqual(report.baseline_overall_score, 0.0)
        self.assertIn(report.recommendation, ["READY", "READY WITH LIMITATIONS", "NEEDS IMPROVEMENT", "REJECT"])
        self.assertTrue(len(report.natural_language_summary) > 0)

    def test_17_category_names(self):
        report = self.service.run_post_training_evaluation(
            run_id="run-test-1234",
            model_version="candidate-v1",
            dataset_version="ds-test-01",
        )
        category_names = [c["name"] for c in report.categories]
        self.assertEqual(len(category_names), 17)
        expected_categories = [
            "Tamil Language Quality", "English Language Quality", "Instruction Following", "Question Answering (QA)",
            "Multi-Step Reasoning", "Context Understanding", "RAG Grounding & Attribution", "Hallucination Resistance",
            "Output Consistency", "Safety & Policy Adherence", "Appropriate Refusal", "Domain Generalization",
            "Memorization Safety", "Long-Context Stability", "Latency (P95 ms)",
            "Throughput (Tokens/sec)", "RAM & Resource Efficiency"
        ]
        for ec in expected_categories:
            self.assertIn(ec, category_names)


class TestMiniBrainModelRouting(unittest.TestCase):
    def setUp(self):
        self.settings = Settings()
        self.service = MiniBrainLlmRuntimeService(self.settings)

    def test_routing_resolver_auto(self):
        res = self.service._resolve_backend(execution_mode="auto")
        self.assertIn("backend_type", res)
        self.assertIn(res["backend_type"], ["local", "provider", "unavailable", "adapter", "llama_cpp", "openai", "openrouter", "anthropic", "gemini"])

    def test_routing_resolver_local(self):
        res = self.service._resolve_backend(execution_mode="local")
        self.assertIn("backend_type", res)
        self.assertIn(res["backend_type"], ["local", "llama_cpp", "unavailable", "adapter"])

    def test_routing_resolver_provider(self):
        res = self.service._resolve_backend(execution_mode="provider", provider_key="openrouter")
        self.assertIn("backend_type", res)
        self.assertIn(res["backend_type"], ["provider", "openrouter", "unavailable", "adapter"])


if __name__ == "__main__":
    unittest.main()
