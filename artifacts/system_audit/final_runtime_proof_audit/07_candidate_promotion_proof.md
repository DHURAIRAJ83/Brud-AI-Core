# 07 CANDIDATE PROMOTION & RELEASE GATE PROOF

- Promotion Gate: `ProductionPromotionGate` enforces cryptographic signature verification.
- Release & Canary Gate: `ProductionReleaseRegistry` & `CanaryDeploymentController` lock candidate traffic share at `0.0`.
- Status: `PROMOTION = BLOCKED`, `PUBLIC_CHAT_ELIGIBLE = FALSE` (`GOVERNANCE_BLOCKED`).
