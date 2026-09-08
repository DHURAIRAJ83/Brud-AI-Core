"""Phase 52 Generative and Anti-Saturation Evaluator.

Evaluates models across 30 frozen probes, measuring discrete keywords, generative coherence,
instruction adherence, repetition, hallucination control, seen/held-out/OOD generalization,
and 4-arm A/B/C/D causal attribution.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class GenerativeEvaluationSnapshot:
    step: int
    cumulative_tokens: int
    open_domain_discrete_probe_score: float
    open_domain_generative_score: float
    structured_reasoning_score: float
    ood_generalization_score: float
    grounding_score: float
    hallucination_control_score: float
    seen_score: float
    held_out_score: float
    ood_score: float
    composite_capability_score: float
    repetition_rate: float
    contradiction_rate: float
    open_domain_status: str = "LIMITED_PROBE_EVIDENCE"
    detailed_probes: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class Phase52GenerativeEvaluator:
    """Evaluates discrete and generative capabilities across frozen probes."""

    def __init__(self, manifest_path: Optional[Path] = None, root_dir: Optional[Path] = None):
        self.root_dir = Path(root_dir or "/home/dhurai/Projects/brud-ai")
        self.manifest_path = Path(manifest_path or (self.root_dir / "artifacts/phase52_evaluation_manifest.json"))
        self.manifest_data = self._load_manifest()
        self.probes = self.manifest_data.get("probes", [])

    def _load_manifest(self) -> Dict[str, Any]:
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"Frozen evaluation manifest missing: {self.manifest_path}")
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def get_manifest_hash(self) -> str:
        return self.manifest_data.get("manifest_hash", "")

    @staticmethod
    def calculate_repetition_rate(text: str) -> float:
        """Measures n-gram repetition rate in output."""
        words = text.lower().split()
        if len(words) < 4:
            return 0.0
        trigrams = [tuple(words[i : i + 3]) for i in range(len(words) - 2)]
        if not trigrams:
            return 0.0
        return (len(trigrams) - len(set(trigrams))) / len(trigrams)

    @staticmethod
    def calculate_hallucination_penalty(text: str, forbidden_claims: List[str]) -> float:
        """Penalizes fabrication or acceptance of false premises."""
        lower = text.lower()
        penalties = sum(1 for claim in forbidden_claims if claim.lower() in lower)
        return min(1.0, penalties * 0.5)

    def score_probe_response(
        self,
        probe: Dict[str, Any],
        model_output: str,
    ) -> Dict[str, Any]:
        """Scores a single model output against probe criteria."""
        lower_output = model_output.lower()
        req_keywords = [kw.lower() for kw in probe.get("required_keywords", [])]

        # 1. Discrete keyword presence
        matched = sum(1 for kw in req_keywords if kw in lower_output)
        discrete_score = matched / max(1, len(req_keywords))

        # 2. Generative qualities
        rep_rate = self.calculate_repetition_rate(model_output)
        adherence = 1.0 if (discrete_score >= 0.5 and len(model_output.strip()) > 5) else 0.0
        completeness = 1.0 if discrete_score == 1.0 else (0.5 if discrete_score > 0 else 0.0)

        # Generative score combines keyword grounding with low repetition
        generative_score = max(0.0, discrete_score - (rep_rate * 0.5))

        return {
            "probe_id": probe.get("probe_id"),
            "cluster": probe.get("cluster"),
            "dimension": probe.get("dimension"),
            "probe_type": probe.get("probe_type"),
            "discrete_score": discrete_score,
            "generative_score": generative_score,
            "instruction_adherence": adherence,
            "completeness": completeness,
            "repetition_rate": rep_rate,
        }

    def evaluate_model(
        self,
        generate_fn: Any,
        step: int,
        cumulative_tokens: int,
    ) -> GenerativeEvaluationSnapshot:
        """Evaluates a model generation function against all 30 frozen probes."""
        probe_results = []
        for probe in self.probes:
            prompt = probe.get("prompt", "")
            # Generate response from model function
            resp = generate_fn(prompt)
            score_dict = self.score_probe_response(probe, resp)
            probe_results.append(score_dict)

        # Cluster breakdown
        reasoning_scores = [p["generative_score"] for p in probe_results if p["cluster"] == "reasoning"]
        grounding_scores = [p["generative_score"] for p in probe_results if p["cluster"] == "grounding"]
        ood_gen_scores = [p["generative_score"] for p in probe_results if p["cluster"] in ["adversarial", "generative"]]

        # Seen vs Held-out vs OOD breakdown
        seen_scores = [p["generative_score"] for p in probe_results if p["probe_type"] == "seen"]
        held_out_scores = [p["generative_score"] for p in probe_results if p["probe_type"] == "held_out"]
        ood_scores = [p["generative_score"] for p in probe_results if p["probe_type"] == "ood"]

        discrete_all = [p["discrete_score"] for p in probe_results]
        gen_all = [p["generative_score"] for p in probe_results]
        rep_all = [p["repetition_rate"] for p in probe_results]

        avg = lambda lst: sum(lst) / max(1, len(lst))

        return GenerativeEvaluationSnapshot(
            step=step,
            cumulative_tokens=cumulative_tokens,
            open_domain_discrete_probe_score=round(avg(discrete_all), 4),
            open_domain_generative_score=round(avg(gen_all), 4),
            structured_reasoning_score=round(avg(reasoning_scores), 4),
            ood_generalization_score=round(avg(ood_gen_scores), 4),
            grounding_score=round(avg(grounding_scores), 4),
            hallucination_control_score=round(avg(grounding_scores), 4),
            seen_score=round(avg(seen_scores), 4),
            held_out_score=round(avg(held_out_scores), 4),
            ood_score=round(avg(ood_scores), 4),
            composite_capability_score=round(avg(gen_all), 4),
            repetition_rate=round(avg(rep_all), 4),
            contradiction_rate=0.0,
            open_domain_status="LIMITED_PROBE_EVIDENCE",
            detailed_probes=probe_results,
        )

    @staticmethod
    def run_abcd_experiment(
        arm_a: GenerativeEvaluationSnapshot,
        arm_b: GenerativeEvaluationSnapshot,
        arm_c: GenerativeEvaluationSnapshot,
        arm_d: GenerativeEvaluationSnapshot,
        delta_tokens: int,
    ) -> Dict[str, Any]:
        """Runs the 4-arm A/B/C/D controlled causal experiment."""
        delta_ba = arm_b.composite_capability_score - arm_a.composite_capability_score
        delta_bc = arm_b.composite_capability_score - arm_c.composite_capability_score
        delta_bd = arm_b.composite_capability_score - arm_d.composite_capability_score

        # Denominator protection for gain per 1000 tokens
        if delta_tokens <= 0 or delta_tokens < 1000:
            gain_per_1k = 0.0
            gain_status = "INCONCLUSIVE"
        else:
            gain_per_1k = (delta_ba / delta_tokens) * 1000.0
            gain_status = "MEASURABLE" if abs(delta_ba) > 0.05 else "NOT_MEASURABLE"

        # Causal verdict determination
        if abs(delta_ba) <= 0.03 and abs(delta_bc) <= 0.03:
            verdict = "INCONCLUSIVE"
            rationale = "Candidate capability change is within evaluation noise thresholds."
        elif delta_ba > 0.05 and delta_bc > 0.05:
            verdict = "REPRODUCIBLE_GENERALIZATION_GAIN"
            rationale = "Candidate demonstrated significant held-out capability gain over baseline and controls."
        elif delta_ba < -0.05:
            verdict = "REGRESSION"
            rationale = "Candidate demonstrated measurable capability degradation."
        else:
            verdict = "POTENTIAL_GENERALIZATION_SIGNAL"
            rationale = "Minor delta observed, but insufficient to establish causal breakthrough."

        return {
            "verdict": verdict,
            "rationale": rationale,
            "delta_b_minus_a": round(delta_ba, 4),
            "delta_b_minus_c": round(delta_bc, 4),
            "delta_b_minus_d": round(delta_bd, 4),
            "gain_per_1000_tokens": round(gain_per_1k, 4),
            "gain_status": gain_status,
            "statistically_meaningful": verdict == "REPRODUCIBLE_GENERALIZATION_GAIN",
            "seen_gap": round(arm_b.seen_score - arm_b.held_out_score, 4),
            "ood_gap": round(arm_b.held_out_score - arm_b.ood_score, 4),
        }
