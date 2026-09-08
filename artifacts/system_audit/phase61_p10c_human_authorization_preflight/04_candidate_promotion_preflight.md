# 04 CANDIDATE PROMOTION PREFLIGHT AUDIT

- Promotion Gate Mechanism: `ProductionPromotionGate`.
- Verification: `verify_promotion_token(None, None)` raises `PromotionAuthorizationError`.
- State: `PROMOTION_BLOCKED`.
