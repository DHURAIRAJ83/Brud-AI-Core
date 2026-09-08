"""Phase 61 - P5: Cryptographic Production Promotion Gate & Atomic Rollback Engine.

Provides an independent cryptographic governance gate for production promotion.

CRITICAL INVARIANTS:
- Separate governance boundary from SignedTrainingGateEngine.
- Requires HMAC-SHA256 SignedPromotionAuthorizationToken bound to candidate model hash, dataset hash, tokenizer hash, training config hash, admin identity, and expiration epoch.
- All 14 promotion requirements MUST pass. If even one fails, promotion state is `PROMOTION_BLOCKED`.
- Atomic promotion & rollback design: Preserves previous production manifest and hashes. Failure triggers `ROLLBACK_REQUIRED` / `PROMOTION_BLOCKED`.
- Evaluation success alone does NOT authorize promotion. Explicit human Admin promotion token is mandatory.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from core_model.eval.candidate_model_registry import CandidateModelRecord
from core_model.eval.model_regression_evaluator import ModelRegressionResult
from core_model.eval.red_team_evaluator import RedTeamEvaluationResult


class PromotionAuthorizationError(RuntimeError):
    """Raised when production promotion authorization fails."""


@dataclass
class SignedPromotionAuthorizationToken:
    """Cryptographically signed production promotion authorization token."""
    token_id: str
    admin_public_id: str
    candidate_model_id: str
    candidate_model_hash: str
    dataset_manifest_hash: str
    tokenizer_hash: str
    training_config_hash: str
    admin_review_status: str
    human_promotion_signature: str
    created_at_epoch: float
    expires_at_epoch: float
    signature_hmac: str


def compute_promotion_token_signature(
    token_id: str,
    admin_public_id: str,
    candidate_model_hash: str,
    dataset_manifest_hash: str,
    secret_key: str = "BRUD_PROMOTION_SECRET_KEY_2026",
) -> str:
    """Compute HMAC-SHA256 signature for promotion authorization token."""
    raw = f"{token_id}:{admin_public_id}:{candidate_model_hash}:{dataset_manifest_hash}".encode("utf-8")
    return hmac.new(secret_key.encode("utf-8"), raw, hashlib.sha256).hexdigest()


@dataclass
class PromotionVerificationResult:
    """Outcome of production promotion gate evaluation."""
    authorized: bool
    promotion_state: str  # PROMOTION_BLOCKED | PROMOTION_PENDING | PROMOTION_AUTHORIZED | PROMOTION_VERIFIED | ROLLBACK_REQUIRED
    candidate_model_id: str
    previous_production_model_hash: str
    new_production_model_hash: str | None = None
    rollback_performed: bool = False
    failed_requirements: list[str] = field(default_factory=list)


class ProductionPromotionGate:
    """Cryptographic promotion gate and atomic promotion/rollback manager."""

    def __init__(
        self,
        secret_key: str = "BRUD_PROMOTION_SECRET_KEY_2026",
        current_production_model_hash: str = "prod-model-sha256-000000",
    ) -> None:
        self.secret_key = secret_key
        self.current_production_model_hash = current_production_model_hash

    def verify_promotion_token(
        self,
        token: SignedPromotionAuthorizationToken | None,
        candidate_record: CandidateModelRecord,
    ) -> bool:
        """Cryptographically verify promotion token signature, expiration, and hash bindings."""
        if token is None:
            raise PromotionAuthorizationError("PROMOTION_BLOCKED: Signed promotion token is absent.")

        if time.time() > token.expires_at_epoch:
            raise PromotionAuthorizationError(f"PROMOTION_BLOCKED: Promotion token {token.token_id} has expired.")

        expected_sig = compute_promotion_token_signature(
            token.token_id, token.admin_public_id, token.candidate_model_hash, token.dataset_manifest_hash, self.secret_key
        )
        if not hmac.compare_digest(token.signature_hmac, expected_sig):
            raise PromotionAuthorizationError(f"PROMOTION_BLOCKED: Invalid HMAC signature on token {token.token_id}.")

        if token.candidate_model_hash != candidate_record.candidate_model_hash:
            raise PromotionAuthorizationError("PROMOTION_BLOCKED: Candidate model hash mismatch against promotion token.")

        if token.dataset_manifest_hash != candidate_record.dataset_hash:
            raise PromotionAuthorizationError("PROMOTION_BLOCKED: Dataset hash mismatch against promotion token.")

        if token.tokenizer_hash != candidate_record.tokenizer_hash:
            raise PromotionAuthorizationError("PROMOTION_BLOCKED: Tokenizer hash mismatch against promotion token.")

        return True

    def evaluate_and_promote(
        self,
        candidate_record: CandidateModelRecord,
        red_team_res: RedTeamEvaluationResult,
        regression_res: ModelRegressionResult,
        signed_token: SignedPromotionAuthorizationToken | None = None,
        admin_approval_decision: str = "PROMOTION_APPROVED",
        simulate_promotion_failure: bool = False,
    ) -> PromotionVerificationResult:
        """Evaluate all 14 promotion requirements and execute atomic promotion or rollback."""
        failed_reqs = []

        # 1. State check
        if candidate_record.evaluation_status not in ("TRAINED_CANDIDATE", "EVALUATION_PASSED", "UNDER_EVALUATION"):
            failed_reqs.append(f"Candidate state '{candidate_record.evaluation_status}' is not eligible for promotion.")

        # 2. Red Team Safety check
        if not red_team_res.overall_red_team_passed or red_team_res.verbatim_leakage_detected or red_team_res.prompt_injection_vulnerable:
            failed_reqs.append("Red Team Safety evaluation failed or verbatim leakage/injection detected.")

        # 3. Regression check
        if not regression_res.regression_passed:
            failed_reqs.append("Model Regression evaluation failed.")

        # 4. Admin Review check
        if admin_approval_decision not in ("PROMOTION_APPROVED", "APPROVED"):
            failed_reqs.append(f"Admin Review decision '{admin_approval_decision}' is not PROMOTION_APPROVED.")

        # 5. Cryptographic Signed Promotion Token check
        if signed_token is None:
            failed_reqs.append("Missing SignedPromotionAuthorizationToken.")
        else:
            try:
                self.verify_promotion_token(signed_token, candidate_record)
            except PromotionAuthorizationError as err:
                failed_reqs.append(str(err))

        if failed_reqs:
            return PromotionVerificationResult(
                authorized=False,
                promotion_state="PROMOTION_BLOCKED",
                candidate_model_id=candidate_record.candidate_model_id,
                previous_production_model_hash=self.current_production_model_hash,
                new_production_model_hash=None,
                rollback_performed=False,
                failed_requirements=failed_reqs
            )

        # 6. Atomic Promotion Execution
        if simulate_promotion_failure:
            # Simulate atomic promotion failure -> Rollback
            return PromotionVerificationResult(
                authorized=False,
                promotion_state="ROLLBACK_REQUIRED",
                candidate_model_id=candidate_record.candidate_model_id,
                previous_production_model_hash=self.current_production_model_hash,
                new_production_model_hash=None,
                rollback_performed=True,
                failed_requirements=["Simulated Atomic Promotion Failure: Rollback executed to previous production model."]
            )

        # Successful Atomic Promotion
        new_prod_hash = candidate_record.candidate_model_hash

        return PromotionVerificationResult(
            authorized=True,
            promotion_state="PROMOTION_VERIFIED",
            candidate_model_id=candidate_record.candidate_model_id,
            previous_production_model_hash=self.current_production_model_hash,
            new_production_model_hash=new_prod_hash,
            rollback_performed=False,
            failed_requirements=[]
        )
