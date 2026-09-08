"""Phase 48 Robust Capability & Generalization Evaluation Engine.

Solves the 1.00 benchmark ceiling with a 5-level reasoning hierarchy,
repeated stochastic generative evaluations, unseen generalization battery,
and dimension-specific denominator-protected capability gain analysis.
"""

from __future__ import annotations

import json
import math
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Sequence


@dataclass
class StochasticTrialResult:
    prompt: str
    trials: list[float]
    mean: float
    median: float
    stddev: float
    confidence_interval_95: tuple[float, float]
    is_deterministic: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DimensionScore:
    dimension: str
    score: float
    sample_count: int
    trials: int
    is_deterministic: bool
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Phase48CapabilitySnapshot:
    checkpoint_id: str
    model_hash: str
    tokens_accumulated: int
    validation_loss: float
    timestamp: float
    # Reasoning Levels 1 - 5
    reasoning_level_1: float
    reasoning_level_2: float
    reasoning_level_3: float
    reasoning_level_4: float
    reasoning_level_5: float
    # Linguistic & Grounding
    tamil_score: float
    english_score: float
    tanglish_policy_score: float
    grounding_score: float
    instruction_score: float
    # Generalization
    in_distribution_score: float
    unseen_generalization_score: float
    generalization_verdict: str
    # Aggregates
    structured_benchmark_score: float
    open_domain_capability_score: float
    overall_score: float
    progression_verdict: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DimensionGainResult:
    dimension: str
    delta_tokens: int
    delta_score: float
    gain_per_thousand_tokens: float | None
    status: str  # VALID, INCONCLUSIVE, CEILING
    confidence_level: float
    statistically_meaningful: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Phase48CapabilityEvaluator:
    """Rigorous capability benchmarking with 5-level reasoning, unseen generalization, and stochastic trials."""

    # Level 5 Counterfactual / Abstract Probes (Mandatory Correction 4)
    LEVEL_5_PROBES = {
        "If gravity pushed objects away from Earth, where would rain fall?": ["sky", "upward", "space"],
        "All glims are toves. Some toves are wabs. Are all glims wabs?": ["no", "cannot be determined", "indeterminate"],
        "Premise: Light travels slower than sound in this universe. What do you observe during a distant explosion?": ["hear first", "sound first"],
    }

    # Unseen Out-of-Distribution Generalization Probes
    UNSEEN_GENERALIZATION_PROBES = {
        "நவீன தொழில்நுட்பம் தமிழ் வளர்ச்சிக்கு எவ்வாறு உதவுகிறது? சுருக்கமாக கூறுக.": ["தொழில்நுட்பம்", "தமிழ்", "வளர்ச்சி"],
        "Explain quantum entanglement in one plain sentence:": ["particles", "connected", "state"],
        "enna da ippadi solra?": ["அப்படி", "சொல்ல"],
    }

    def __init__(self, telemetry_file: Path | None = None) -> None:
        self.telemetry_file = telemetry_file

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

    def evaluate_checkpoint(
        self,
        checkpoint_id: str,
        model_hash: str,
        tokens_accumulated: int,
        validation_loss: float,
        model_responses: dict[str, str],
        stochastic_trials: int = 3,
        prior_snapshot: Phase48CapabilitySnapshot | None = None,
    ) -> Phase48CapabilitySnapshot:
        """Evaluates complete 5-level reasoning, language, and generalization profile."""

        # 1. Reasoning Levels 1 - 4 (Inherited & Standardized)
        r1_keys = ["42", "3, 8, 11", "animal"]
        r1_hits = sum(1 for k in r1_keys if any(k in v for v in model_responses.values()))
        r1_score = r1_hits / len(r1_keys) if r1_keys else 0.0

        r2_keys = ["yes", "chair", "mortal"]
        r2_hits = sum(1 for k in r2_keys if any(k.lower() in v.lower() for v in model_responses.values()))
        r2_score = r2_hits / len(r2_keys) if r2_keys else 0.0

        r3_keys = ["send message", "grandfather"]
        r3_hits = sum(1 for k in r3_keys if any(k.lower() in v.lower() for v in model_responses.values()))
        r3_score = r3_hits / len(r3_keys) if r3_keys else 0.0

        r4_keys = ["ஆதாரம் இல்லை", "தவறான அனுமானம்", "key x-99"]
        r4_hits = sum(1 for k in r4_keys if any(k in v for v in model_responses.values()))
        r4_score = r4_hits / len(r4_keys) if r4_keys else 0.0

        # 2. Reasoning Level 5 (Counterfactual / Abstract - Mandatory Correction 4)
        l5_scores: list[float] = []
        for p, keywords in self.LEVEL_5_PROBES.items():
            resp = model_responses.get(p, "")
            score = 1.0 if any(k.lower() in resp.lower() for k in keywords) else 0.0
            l5_scores.append(score)
        r5_score = sum(l5_scores) / len(l5_scores) if l5_scores else 0.0

        # 3. Linguistic & Policy
        ta_keys = ["சென்னை", "திருவள்ளுவர்"]
        ta_hits = sum(1 for k in ta_keys if any(k in v for v in model_responses.values()))
        ta_score = ta_hits / len(ta_keys) if ta_keys else 0.0

        en_keys = ["paris", "flies"]
        en_hits = sum(1 for k in en_keys if any(k.lower() in v.lower() for v in model_responses.values()))
        en_score = en_hits / len(en_keys) if en_keys else 0.0

        # Tanglish policy: pure Tamil response enforced, zero unauthorized Latin characters
        tgl_resp = model_responses.get("epdi irukinga?", "")
        has_latin = bool(re.search(r"[a-zA-Z]", tgl_resp))
        tgl_policy_score = 1.0 if (tgl_resp and not has_latin) else (0.5 if tgl_resp else 0.0)

        # Grounding & Instruction
        grounding_score = 1.0 if any("2024" in v for v in model_responses.values()) else 0.0
        instruction_score = 1.0 if any("3, 8, 11" in v for v in model_responses.values()) else 0.0

        # 4. In-Distribution vs Unseen Generalization
        in_dist_scores = [r1_score, r2_score, r3_score, r4_score, ta_score, en_score]
        in_dist_score = sum(in_dist_scores) / len(in_dist_scores)

        unseen_hits: list[float] = []
        for p, keywords in self.UNSEEN_GENERALIZATION_PROBES.items():
            resp = model_responses.get(p, "")
            unseen_hits.append(1.0 if any(k.lower() in resp.lower() for k in keywords) else 0.0)
        unseen_score = sum(unseen_hits) / len(unseen_hits) if unseen_hits else 0.0

        if unseen_score > (prior_snapshot.unseen_generalization_score if prior_snapshot else 0.0):
            gen_verdict = "GENERALIZATION_GAIN"
        elif prior_snapshot and unseen_score < prior_snapshot.unseen_generalization_score:
            gen_verdict = "GENERALIZATION_FAILURE"
        else:
            gen_verdict = "NO_MEANINGFUL_CHANGE"

        # Structured benchmark vs open-domain separation
        structured_score = (r1_score + r2_score + r3_score + r4_score + r5_score + ta_score + en_score + tgl_policy_score) / 8.0
        open_domain_score = (unseen_score + r5_score) / 2.0
        overall_score = (structured_score * 0.65) + (open_domain_score * 0.35)

        if prior_snapshot:
            if overall_score > prior_snapshot.overall_score:
                prog_verdict = "IMPROVING"
            elif overall_score < prior_snapshot.overall_score:
                prog_verdict = "REGRESSING"
            else:
                prog_verdict = "STAGNANT"
        else:
            prog_verdict = "BASELINE"

        snap = Phase48CapabilitySnapshot(
            checkpoint_id=checkpoint_id,
            model_hash=model_hash,
            tokens_accumulated=tokens_accumulated,
            validation_loss=validation_loss,
            timestamp=time.time(),
            reasoning_level_1=r1_score,
            reasoning_level_2=r2_score,
            reasoning_level_3=r3_score,
            reasoning_level_4=r4_score,
            reasoning_level_5=r5_score,
            tamil_score=ta_score,
            english_score=en_score,
            tanglish_policy_score=tgl_policy_score,
            grounding_score=grounding_score,
            instruction_score=instruction_score,
            in_distribution_score=round(in_dist_score, 4),
            unseen_generalization_score=round(unseen_score, 4),
            generalization_verdict=gen_verdict,
            structured_benchmark_score=round(structured_score, 4),
            open_domain_capability_score=round(open_domain_score, 4),
            overall_score=round(overall_score, 4),
            progression_verdict=prog_verdict,
        )

        if self.telemetry_file:
            self.telemetry_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.telemetry_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(snap.to_dict()) + "\n")

        return snap

    @classmethod
    def compute_gain_per_token(
        cls,
        prior: Phase48CapabilitySnapshot,
        candidate: Phase48CapabilitySnapshot,
        dimension: str = "overall",
    ) -> DimensionGainResult:
        """Calculates dimension-specific gain with denominator protection and ceiling detection."""
        delta_tokens = candidate.tokens_accumulated - prior.tokens_accumulated

        val_prior = getattr(prior, f"{dimension}_score", prior.overall_score)
        val_cand = getattr(candidate, f"{dimension}_score", candidate.overall_score)
        delta_score = val_cand - val_prior

        # Ceiling detection (Mandatory Correction 4)
        if val_prior >= 0.95 and val_cand >= 0.95:
            return DimensionGainResult(
                dimension=dimension,
                delta_tokens=delta_tokens,
                delta_score=round(delta_score, 4),
                gain_per_thousand_tokens=0.0,
                status="CEILING",
                confidence_level=0.95,
                statistically_meaningful=False,
            )

        # Denominator protection: must have accumulated at least 1,000 tokens
        if delta_tokens < 1000:
            return DimensionGainResult(
                dimension=dimension,
                delta_tokens=delta_tokens,
                delta_score=round(delta_score, 4),
                gain_per_thousand_tokens=None,
                status="INCONCLUSIVE (insufficient token delta)",
                confidence_level=0.50,
                statistically_meaningful=False,
            )

        gain = (delta_score / delta_tokens) * 1000.0
        # Mandatory Correction 5: statistical caution
        meaningful = abs(delta_score) >= 0.05 and delta_tokens >= 1000

        return DimensionGainResult(
            dimension=dimension,
            delta_tokens=delta_tokens,
            delta_score=round(delta_score, 4),
            gain_per_thousand_tokens=round(gain, 4),
            status="VALID",
            confidence_level=0.95 if meaningful else 0.70,
            statistically_meaningful=meaningful,
        )

    @classmethod
    def classify_loss_vs_capability(
        cls,
        loss_delta: float,
        capability_delta: float,
    ) -> str:
        """Classifies the relationship between loss reduction and capability progression."""
        # Loss decreased and capability improved
        if loss_delta < -0.01 and capability_delta > 0.02:
            return "CORRELATED"
        # Loss decreased but capability unchanged
        if loss_delta < -0.01 and abs(capability_delta) <= 0.02:
            return "UNCORRELATED"
        # Loss unchanged or increased
        if loss_delta >= 0.0:
            return "WEAKLY_CORRELATED"
        return "INCONCLUSIVE"
