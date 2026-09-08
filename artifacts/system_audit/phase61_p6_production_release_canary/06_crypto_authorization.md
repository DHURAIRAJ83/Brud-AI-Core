# 06 CRYPTOGRAPHIC AUTHORIZATION AUDIT

- Cryptographic Gate: `ProductionPromotionGate` via HMAC-SHA256 tokens bound to candidate model hash, dataset hash, tokenizer hash, config hash, admin ID, and expiration epoch.
