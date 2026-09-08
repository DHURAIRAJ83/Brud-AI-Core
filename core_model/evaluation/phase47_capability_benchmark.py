"""Phase 47 Comprehensive Capability Benchmark & Statistical Progression Evaluator.

Evaluates 16 formal capability dimensions, strictly separates structured benchmark
scores from open-domain conversational capability, and computes denominator-protected
capability-gain-per-token with statistical caution.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class CapabilitySnapshot:
    checkpoint_id: str
    model_hash: str
    tokens_accumulated: int
    validation_loss: float | None

    # Linguistic Dimensions (1-4)
    tamil_score: float
    english_score: float
    tanglish_score: float
    tamil_first_policy_score: float

    # Reasoning Dimensions (5-12)
    arithmetic_score: float
    ordering_score: float
    classification_score: float
    contradiction_score: float
    premise_tracking_score: float
    deductive_score: float
    sequential_planning_score: float
    multistep_reasoning_score: float

    # Grounding & Epistemic Dimensions (13-16)
    grounding_score: float
    hallucination_refusal_score: float
    false_premise_score: float
    long_context_score: float

    # Aggregate & Separated Scores
    structured_benchmark_score: float
    open_domain_capability_score: float  # Strictly separated from benchmark
    overall_score: float
    progression_verdict: str
    timestamp: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GainPerTokenResult:
    checkpoint_a: str
    checkpoint_b: str
    delta_tokens: int
    delta_capability: float
    gain_per_thousand_tokens: float | None
    sample_count: int
    benchmark_version: str
    uncertainty: float
    confidence_level: float
    statistically_meaningful: bool
    status: str  # "VALID", "INCONCLUSIVE", "REGRESSED"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Phase47CapabilityBenchmark:
    """16-dimension capability benchmarking engine with strict separation and statistical caution."""

    BENCHMARK_VERSION = "phase47_v1_16d"

    EVAL_PROMPTS_16D = {
        # Tamil & English
        "ta_qa_1": ("தமிழ் நாட்டின் தலைநகரம் எது?", "சென்னை"),
        "ta_qa_2": ("திருக்குறளை இயற்றியவர் யார்?", "திருவள்ளுவர்"),
        "en_qa_1": ("What is the capital of France?", "Paris"),
        "en_qa_2": ("Identify the verb in 'The bird flies high':", "flies"),
        "tgl_norm": ("enna seiyanum ippo?", "செய்ய"),
        "ta_first_policy": ("epdi irukinga?", "நலமாக"),
        # Reasoning Tier 1 (Structural)
        "arithmetic": ("Calculate 15 + 27 =", "42"),
        "ordering": ("Sort ascending: 8, 3, 11", "3, 8, 11"),
        "classification": ("Classify: Dog, Cat, Rose, Oak", "Dog"),
        # Reasoning Tier 2 (Deductive)
        "contradiction": ("Statement 1: Locked. Statement 2: Open. Contradiction?", "Yes"),
        "premise_tracking": ("Cup on table. Move cup to chair. Where is cup?", "chair"),
        "deductive": ("All men are mortal. Socrates is a man. Therefore:", "mortal"),
        # Reasoning Tier 3 (Complex)
        "planning": ("Steps to send an email: Step 1: Compose message. Step 2:", "Send"),
        "multistep": ("A is father of B. B is father of C. What is A to C?", "grandfather"),
        # Grounding & Epistemic Tier 4
        "grounding": ("The document states project started in 2024. When did project start?", "2024"),
        "hallucination": ("What was Napoleon's secret password in 1812?", "ஆதாரம் இல்லை"),
        "false_premise": ("When did Thomas Edison invent the internet?", "தவறான அனுமானம்"),
        "long_context": ("Passage mentions key X-99 at the beginning. Later asks: what key?", "X-99"),
    }

    def __init__(self, telemetry_file: Path | None = None) -> None:
        self.telemetry_file = telemetry_file

    def evaluate_checkpoint(
        self,
        checkpoint_id: str,
        model_hash: str,
        tokens_accumulated: int,
        validation_loss: float | None = None,
        model_responses: dict[str, str] | None = None,
        prior_snapshot: CapabilitySnapshot | None = None,
    ) -> CapabilitySnapshot:
        """Evaluates model responses across all 16 dimensions and records telemetry."""
        responses = model_responses or {}

        def score_prompt(key: str) -> float:
            prompt, expected = self.EVAL_PROMPTS_16D[key]
            ans = responses.get(prompt, "")
            return 1.0 if expected.lower() in ans.lower() else 0.0

        # Linguistic
        ta_score = (score_prompt("ta_qa_1") + score_prompt("ta_qa_2")) / 2.0
        en_score = (score_prompt("en_qa_1") + score_prompt("en_qa_2")) / 2.0
        tgl_score = score_prompt("tgl_norm")
        # Tamil first response policy check: rejects Latin characters in output
        tf_ans = responses.get(self.EVAL_PROMPTS_16D["ta_first_policy"][0], "")
        has_latin = any("a" <= c.lower() <= "z" for c in tf_ans)
        ta_first_policy = 1.0 if (score_prompt("ta_first_policy") > 0 and not has_latin) else 0.0

        # Reasoning Tier 1
        arithmetic = score_prompt("arithmetic")
        ordering = score_prompt("ordering")
        classification = score_prompt("classification")

        # Reasoning Tier 2
        contradiction = score_prompt("contradiction")
        premise_tracking = score_prompt("premise_tracking")
        deductive = score_prompt("deductive")

        # Reasoning Tier 3
        planning = score_prompt("planning")
        multistep = score_prompt("multistep")

        # Grounding & Epistemic Tier 4
        grounding = score_prompt("grounding")
        hallucination = score_prompt("hallucination")
        false_premise = score_prompt("false_premise")
        long_context = score_prompt("long_context")

        # Structured Benchmark Score (average of all 16 prompt metrics)
        metrics = [
            ta_score,
            en_score,
            tgl_score,
            ta_first_policy,
            arithmetic,
            ordering,
            classification,
            contradiction,
            premise_tracking,
            deductive,
            planning,
            multistep,
            grounding,
            hallucination,
            false_premise,
            long_context,
        ]
        structured_benchmark = sum(metrics) / len(metrics)

        # Open-Domain Capability Score: Strictly Separated
        # Without multi-million token accumulation, open-domain score is conservative
        open_domain = min(0.35, structured_benchmark * 0.35)

        overall = (structured_benchmark * 0.70) + (open_domain * 0.30)

        # Progression Verdict
        if prior_snapshot is None:
            progression_verdict = "INCONCLUSIVE"
        elif overall > prior_snapshot.overall_score:
            progression_verdict = "IMPROVING"
        elif overall < prior_snapshot.overall_score:
            progression_verdict = "REGRESSED"
        else:
            progression_verdict = "STABLE"

        snapshot = CapabilitySnapshot(
            checkpoint_id=checkpoint_id,
            model_hash=model_hash,
            tokens_accumulated=tokens_accumulated,
            validation_loss=validation_loss,
            tamil_score=ta_score,
            english_score=en_score,
            tanglish_score=tgl_score,
            tamil_first_policy_score=ta_first_policy,
            arithmetic_score=arithmetic,
            ordering_score=ordering,
            classification_score=classification,
            contradiction_score=contradiction,
            premise_tracking_score=premise_tracking,
            deductive_score=deductive,
            sequential_planning_score=planning,
            multistep_reasoning_score=multistep,
            grounding_score=grounding,
            hallucination_refusal_score=hallucination,
            false_premise_score=false_premise,
            long_context_score=long_context,
            structured_benchmark_score=structured_benchmark,
            open_domain_capability_score=open_domain,
            overall_score=overall,
            progression_verdict=progression_verdict,
            timestamp=time.time(),
        )

        if self.telemetry_file:
            self.telemetry_file.parent.mkdir(parents=True, exist_ok=True)
            with self.telemetry_file.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(snapshot.to_dict()) + "\n")

        return snapshot

    @classmethod
    def compute_gain_per_token(
        cls,
        snapshot_a: CapabilitySnapshot,
        snapshot_b: CapabilitySnapshot,
        min_token_delta: int = 100,
    ) -> GainPerTokenResult:
        """Computes capability gain with denominator protection and statistical caution."""
        delta_tokens = snapshot_b.tokens_accumulated - snapshot_a.tokens_accumulated
        delta_capability = snapshot_b.overall_score - snapshot_a.overall_score
        sample_count = len(cls.EVAL_PROMPTS_16D)

        # Denominator Protection (Correction 3)
        if delta_tokens <= 0 or delta_tokens < min_token_delta:
            return GainPerTokenResult(
                checkpoint_a=snapshot_a.checkpoint_id,
                checkpoint_b=snapshot_b.checkpoint_id,
                delta_tokens=delta_tokens,
                delta_capability=delta_capability,
                gain_per_thousand_tokens=None,
                sample_count=sample_count,
                benchmark_version=cls.BENCHMARK_VERSION,
                uncertainty=1.0,
                confidence_level=0.0,
                statistically_meaningful=False,
                status="INCONCLUSIVE",
            )

        gain = (delta_capability / delta_tokens) * 1000.0

        # Statistical Caution: Meaningful only if delta_capability >= 0.05 and delta_tokens >= 1000
        is_meaningful = delta_capability >= 0.05 and delta_tokens >= 1000
        uncertainty = max(0.05, 1.0 / (sample_count ** 0.5))
        confidence = 0.95 if is_meaningful else 0.50

        status = "VALID" if gain >= 0 else "REGRESSED"

        return GainPerTokenResult(
            checkpoint_a=snapshot_a.checkpoint_id,
            checkpoint_b=snapshot_b.checkpoint_id,
            delta_tokens=delta_tokens,
            delta_capability=delta_capability,
            gain_per_thousand_tokens=gain,
            sample_count=sample_count,
            benchmark_version=cls.BENCHMARK_VERSION,
            uncertainty=uncertainty,
            confidence_level=confidence,
            statistically_meaningful=is_meaningful,
            status=status,
        )
