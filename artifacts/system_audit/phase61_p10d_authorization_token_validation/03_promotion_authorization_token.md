# 03 PROMOTION AUTHORIZATION TOKEN AUDIT

- Token Class: `SignedPromotionAuthorizationToken`.
- Validation: Missing token / expired token / bad signature fails closed with `PromotionAuthorizationError`.
- Production Status: `BLOCKED_PENDING_HUMAN_SIGNATURE`.
