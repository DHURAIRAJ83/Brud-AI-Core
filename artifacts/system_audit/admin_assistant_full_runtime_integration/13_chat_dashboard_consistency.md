# 13 CHAT ↔ DASHBOARD CONSISTENCY AUDIT

- Pending Work Guidance: Chat query "What is pending right now?" returns identical counts for dataset proposals, governance readiness, and token blockers as the Admin Dashboard Overview page.
- Governance Invariants: Chat, Admin Assistant Page, and `GET /api/admin/assistant/governance-status` return 100% identical status values (`TRAINING_AUTHORIZATION=FALSE`, `PROMOTION=BLOCKED`, `PUBLIC_CHAT_ELIGIBLE=FALSE`, `COMPLIANCE=BLOCKED`, `PRODUCTION_STATE=LOCKED`).
