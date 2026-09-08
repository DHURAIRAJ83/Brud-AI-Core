# 14 PROMOTION TOKEN SECURITY AUDIT

- Class: `SignedPromotionAuthorizationToken` in `core_model/eval/production_promotion_gate.py`.
- Signature: Cryptographic HMAC-SHA256 bound to candidate model hash, dataset hash, tokenizer hash, training config hash, admin ID, and expiration epoch.
