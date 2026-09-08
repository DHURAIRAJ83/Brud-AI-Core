# 04 PUBLIC CHAT AUTHORIZATION TOKEN AUDIT

- Token Class: `SignedPublicChatAdmissionToken`.
- Validation: Missing token / expired token / bad signature fails closed with `PublicChatAdmissionError`.
- Production Status: `BLOCKED_PENDING_HUMAN_SIGNATURE`.
