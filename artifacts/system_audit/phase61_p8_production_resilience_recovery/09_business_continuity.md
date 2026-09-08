# 09 BUSINESS CONTINUITY CONTROLLER AUDIT

- Class: `BusinessContinuityController` in `core_model/ops/business_continuity_controller.py`.
- Invariant Enforcement: Non-operational states force `candidate_traffic_share = 0.0` and `public_chat_eligible = FALSE`.
