# 03 CANDIDATE MODEL REGISTRY AUDIT

- Class: `CandidateModelRegistry` in `core_model/eval/candidate_model_registry.py`
- State Machine: `TRAINED_CANDIDATE -> UNDER_EVALUATION -> RED_TEAM_REQUIRED -> EVALUATION_PASSED -> PROMOTION_PENDING -> PROMOTION_APPROVED -> PROMOTION_BLOCKED -> REJECTED -> QUARANTINED`
- Invariant: Production state remains separate. `candidate_traffic_share = 0.0` and `public_chat_eligible = FALSE` enforced by default.
