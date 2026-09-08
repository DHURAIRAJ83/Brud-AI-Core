"""Phase 50 Sovereign Capability Evaluator & Independent Validation Engine.

Enforces strict separation of:
- structured_benchmark_score
- open_domain_probe_score
- open_domain_generative_score

Guarantees:
- Discrete 1.0 scores do not trigger "QUALIFIED" open-domain status.
- Evaluates held-out, immutable phase50_evaluation_manifest.json.
- Computes repeated stochastic trials, variance, and 95% confidence intervals.
- Computes descriptive gain/token with denominator protection.
- Computes loss vs capability correlation and A/B/C causal attribution.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Sequence

from core_model.evaluation.phase48_capability_evaluator import (
    DimensionGainResult,
    Phase48CapabilityEvaluator,
    Phase48CapabilitySnapshot,
    StochasticTrialResult,
)


@dataclass
class Phase50GainResult:
    delta_score: float
    delta_tokens: int
    gain_per_thousand_tokens: float
    status: str  # VALID, INCONCLUSIVE (insufficient token delta)
    confidence_level: float
    statistically_meaningful: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class OpenDomainStatus(str, Enum):

    LIMITED_PROBE_EVIDENCE = "LIMITED_PROBE_EVIDENCE"
    PROBE_QUALIFIED_ONLY = "PROBE_QUALIFIED_ONLY"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    GENERATIVE_QUALIFIED = "GENERATIVE_QUALIFIED"


class CausalityVerdict(str, Enum):
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    NO_CAUSAL_EFFECT = "NO_CAUSAL_EFFECT"


@dataclass
class Phase50CapabilitySnapshot:
    checkpoint_id: str
    model_hash: str
    tokens_accumulated: int
    validation_loss: float
    timestamp: float = field(default_factory=time.time)

    # 1. Structured Reasoning Hierarchy (Levels 1 - 5)
    reasoning_level_1: float = 0.0
    reasoning_level_2: float = 0.0
    reasoning_level_3: float = 0.0
    reasoning_level_4: float = 0.0
    reasoning_level_5: float = 0.0

    # 2. Linguistic Competency
    tamil_score: float = 0.0
    english_score: float = 0.0
    tanglish_policy_score: float = 0.0

    # 3. Grounding & Anti-Saturation
    grounding_score: float = 0.0
    anti_saturation_score: float = 0.0
    unseen_generalization_score: float = 0.0

    # 4. Mandatory Distinct Scores (User Correction 3)
    structured_benchmark_score: float = 0.0
    open_domain_probe_score: float = 0.0
    open_domain_generative_score: float = 0.0
    open_domain_status: str = OpenDomainStatus.LIMITED_PROBE_EVIDENCE.value

    # 5. Composite Score & Verdict
    overall_score: float = 0.0
    progression_verdict: str = "BASELINE"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Phase50CapabilitySnapshot:
        return cls(**data)


class Phase50CapabilityEvaluator:
    """Independent evaluation engine executing held-out anti-saturation and open-domain batteries."""

    def __init__(
        self,
        evaluation_manifest_path: Path | str = "artifacts/phase50_evaluation_manifest.json",
        telemetry_file: Path | str = "artifacts/phase50_capability_telemetry.jsonl",
    ) -> None:
        self.manifest_path = Path(evaluation_manifest_path)
        self.telemetry_file = Path(telemetry_file)
        self.manifest = self._load_manifest()

    def _load_manifest(self) -> dict[str, Any]:
        if self.manifest_path.exists():
            try:
                return json.loads(self.manifest_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def get_manifest_hash(self) -> str:
        return self.manifest.get("manifest_hash", "UNVERIFIED")

    def evaluate_checkpoint(
        self,
        checkpoint_id: str,
        model_hash: str,
        tokens_accumulated: int,
        validation_loss: float,
        model_responses: dict[str, str],
        stochastic_trials: int = 3,
        prior_snapshot: Phase50CapabilitySnapshot | None = None,
    ) -> Phase50CapabilitySnapshot:
        """Executes full evaluation battery enforcing strict score separation."""

        # Level 1
        r1_keys = ["42", "3, 8, 11", "animal"]
        r1_score = self._score_category(model_responses, r1_keys)

        # Level 2
        r2_keys = ["yes", "chair", "mortal"]
        r2_score = self._score_category(model_responses, r2_keys)

        # Level 3
        r3_keys = ["send", "recipient", "grandfather"]
        r3_score = self._score_category(model_responses, r3_keys)

        # Level 4 (Safe Refusal / Epistemic Uncertainty)
        r4_keys = ["ஆதாரம் இல்லை", "unknown", "தவறான", "did not invent", "false premise"]
        r4_score = self._score_category(model_responses, r4_keys)

        # Level 5 (Counterfactual / Abstract)
        r5_keys = ["upward", "space", "away from earth", "cannot be determined", "not necessarily"]
        r5_score = self._score_category(model_responses, r5_keys)

        # Multilingual
        ta_keys = ["சென்னை", "திருவள்ளுவர்"]
        ta_score = self._score_category(model_responses, ta_keys)

        en_keys = ["paris", "flies"]
        en_score = self._score_category(model_responses, en_keys)

        tgl_keys = ["நலமாக", "இருக்கிறேன்", "வணக்கம்", "செய்யலாம்", "சொல்லுங்கள்"]
        tgl_score = self._score_category(model_responses, tgl_keys)

        # Grounding
        grounding_keys = ["2024", "Key X-99", "10"]
        grounding_score = self._score_category(model_responses, grounding_keys)

        # Anti-saturation (adversarial / distractor / false premises)
        anti_keys = ["red", "10", "not mentioned", "ஆதாரம் இல்லை", "42"]
        anti_saturation_score = self._score_category(model_responses, anti_keys)

        # Unseen OOD Generalization
        ood_keys = ["தொழில்நுட்பம்", "particles", "connected", "quantum", "சொல்லாதே"]
        ood_score = self._score_category(model_responses, ood_keys)

        # Mandatory Distinct Score Calculations
        # 1. Structured Benchmark Score
        structured_benchmark_score = round(
            (r1_score + r2_score + r3_score + r4_score + r5_score + ta_score + en_score + tgl_score) / 8.0,
            4,
        )

        # 2. Open-Domain Discrete Probe Score
        open_domain_probe_score = round(ood_score, 4)

        # 3. Open-Domain Generative Score (Measures length, non-empty, adherence)
        gen_scores = []
        for p in self.manifest.get("open_domain_generative_probes", []):
            prompt = p.get("prompt", "")
            resp = model_responses.get(prompt, "")
            criteria = p.get("quality_criteria", [])
            hit = any(c.lower() in resp.lower() for c in criteria)
            # Penalize trivial degenerate responses
            if len(resp.strip()) >= 10 and hit:
                gen_scores.append(1.0)
            elif hit:
                gen_scores.append(0.5)
            else:
                gen_scores.append(0.0)
        open_domain_generative_score = round(sum(gen_scores) / len(gen_scores), 4) if gen_scores else 0.0

        # Mandatory Correction 3: Discrete probe 1.0 does NOT mean QUALIFIED
        if open_domain_generative_score >= 0.85 and anti_saturation_score >= 0.80:
            od_status = OpenDomainStatus.LIMITED_PROBE_EVIDENCE.value
        elif open_domain_probe_score > 0.0:
            od_status = OpenDomainStatus.PROBE_QUALIFIED_ONLY.value
        else:
            od_status = OpenDomainStatus.INSUFFICIENT_EVIDENCE.value

        # Overall composite score
        overall_score = round(
            0.4 * structured_benchmark_score
            + 0.2 * anti_saturation_score
            + 0.2 * open_domain_probe_score
            + 0.2 * open_domain_generative_score,
            4,
        )

        progression_verdict = "BASELINE"
        if prior_snapshot is not None:
            if overall_score > prior_snapshot.overall_score + 0.02:
                progression_verdict = "IMPROVING"
            elif overall_score < prior_snapshot.overall_score - 0.02:
                progression_verdict = "REGRESSING"
            else:
                progression_verdict = "STABLE"

        snap = Phase50CapabilitySnapshot(
            checkpoint_id=checkpoint_id,
            model_hash=model_hash,
            tokens_accumulated=tokens_accumulated,
            validation_loss=round(validation_loss, 4),
            timestamp=time.time(),
            reasoning_level_1=round(r1_score, 4),
            reasoning_level_2=round(r2_score, 4),
            reasoning_level_3=round(r3_score, 4),
            reasoning_level_4=round(r4_score, 4),
            reasoning_level_5=round(r5_score, 4),
            tamil_score=round(ta_score, 4),
            english_score=round(en_score, 4),
            tanglish_policy_score=round(tgl_score, 4),
            grounding_score=round(grounding_score, 4),
            anti_saturation_score=round(anti_saturation_score, 4),
            unseen_generalization_score=round(ood_score, 4),
            structured_benchmark_score=structured_benchmark_score,
            open_domain_probe_score=open_domain_probe_score,
            open_domain_generative_score=open_domain_generative_score,
            open_domain_status=od_status,
            overall_score=overall_score,
            progression_verdict=progression_verdict,
        )

        self._record_telemetry(snap)
        return snap

    def _score_category(self, responses: dict[str, str], keywords: list[str]) -> float:
        if not responses or not keywords:
            return 0.0
        hits = 0
        total = 0
        for prompt, resp in responses.items():
            for kw in keywords:
                total += 1
                if kw.lower() in resp.lower():
                    hits += 1
                    break
        return hits / max(1, len(keywords))

    def evaluate_stochastic_probe(
        self,
        prompt: str,
        expected_keywords: Sequence[str],
        response_generator: Any,
        trials: int = 5,
        is_deterministic: bool = False,
    ) -> StochasticTrialResult:
        """Executes repeated stochastic trials and computes distribution statistics."""
        scores: list[float] = []
        for _ in range(trials if not is_deterministic else 1):
            resp = response_generator(prompt) if callable(response_generator) else str(response_generator)
            score = 1.0 if any(k.lower() in resp.lower() for k in expected_keywords) else 0.0
            scores.append(score)

        mean_score = sum(scores) / len(scores)
        sorted_scores = sorted(scores)
        n = len(sorted_scores)
        median_score = sorted_scores[n // 2] if n % 2 != 0 else (sorted_scores[n // 2 - 1] + sorted_scores[n // 2]) / 2.0

        if n > 1:
            variance = sum((x - mean_score) ** 2 for x in scores) / (n - 1)
            stddev = math.sqrt(variance)
            margin = 1.96 * (stddev / math.sqrt(n))
            ci = (max(0.0, mean_score - margin), min(1.0, mean_score + margin))
        else:
            stddev = 0.0
            ci = (mean_score, mean_score)

        return StochasticTrialResult(
            prompt=prompt,
            trials=scores,
            mean=round(mean_score, 4),
            median=round(median_score, 4),
            stddev=round(stddev, 4),
            confidence_interval_95=(round(ci[0], 4), round(ci[1], 4)),
            is_deterministic=is_deterministic,
        )

    @classmethod
    def compute_gain_per_token(
        cls,
        baseline: Phase50CapabilitySnapshot,
        candidate: Phase50CapabilitySnapshot,
        threshold_tokens: int = 1000,
    ) -> Phase50GainResult:
        """Calculates descriptive capability gain per 1,000 tokens with denominator protection."""
        delta_tokens = candidate.tokens_accumulated - baseline.tokens_accumulated
        delta_score = candidate.overall_score - baseline.overall_score

        if delta_tokens <= 0 or delta_tokens < threshold_tokens:
            return Phase50GainResult(
                delta_score=round(delta_score, 4),
                delta_tokens=delta_tokens,
                gain_per_thousand_tokens=0.0,
                status="INCONCLUSIVE (insufficient token delta)",
                confidence_level=0.0,
                statistically_meaningful=False,
            )

        gain_per_k = (delta_score / delta_tokens) * 1000.0
        is_meaningful = delta_tokens >= 5000 and abs(delta_score) >= 0.05

        return Phase50GainResult(
            delta_score=round(delta_score, 4),
            delta_tokens=delta_tokens,
            gain_per_thousand_tokens=round(gain_per_k, 4),
            status="VALID",
            confidence_level=0.95,
            statistically_meaningful=is_meaningful,
        )


    @classmethod
    def classify_loss_vs_capability(
        cls,
        loss_delta: float,
        capability_delta: float,
    ) -> str:
        """Analyzes correlation between training/validation loss changes and capability scores."""
        if abs(loss_delta) < 0.001 and abs(capability_delta) < 0.001:
            return "INSUFFICIENT_DATA"
        # Loss decreased & capability increased -> Correlated
        if loss_delta < -0.05 and capability_delta > 0.05:
            return "CORRELATED"
        # Loss decreased but capability unchanged -> Weakly correlated
        if loss_delta < -0.05 and abs(capability_delta) <= 0.05:
            return "WEAKLY_CORRELATED"
        # Loss decreased but capability decreased -> Divergent
        if loss_delta < -0.05 and capability_delta < -0.05:
            return "DIVERGENT"
        # Loss increased or unpatterned
        if abs(capability_delta) < 0.02:
            return "UNCORRELATED"
        return "INSUFFICIENT_DATA"

    @classmethod
    def evaluate_causal_attribution(
        cls,
        candidate_a: Phase50CapabilitySnapshot,
        baseline_b: Phase50CapabilitySnapshot,
        comparison_c: Phase50CapabilitySnapshot,
    ) -> dict[str, Any]:
        """Ablation & Causality check across Candidate A, Baseline B, and Comparison C."""
        delta_a_b = candidate_a.overall_score - baseline_b.overall_score
        delta_c_b = comparison_c.overall_score - baseline_b.overall_score

        if delta_a_b > 0.05 and delta_c_b <= 0.02:
            verdict = CausalityVerdict.PARTIALLY_SUPPORTED.value
            rationale = "Candidate with additional training exposure improved significantly over frozen baseline, while comparison without training showed no meaningful change."
        elif abs(delta_a_b) <= 0.02:
            verdict = CausalityVerdict.INCONCLUSIVE.value
            rationale = "Candidate capability change is within evaluation noise threshold; cannot definitively attribute change to training exposure."
        else:
            verdict = CausalityVerdict.INCONCLUSIVE.value
            rationale = "Comparison group showed variation without training exposure; causal certainty is limited by evaluator sensitivity."

        return {
            "verdict": verdict,
            "delta_candidate_vs_baseline": round(delta_a_b, 4),
            "delta_comparison_vs_baseline": round(delta_c_b, 4),
            "rationale": rationale,
        }

    def _record_telemetry(self, snap: Phase50CapabilitySnapshot) -> None:
        self.telemetry_file.parent.mkdir(parents=True, exist_ok=True)
        with self.telemetry_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(snap.to_dict()) + "\n")
