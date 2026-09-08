# 10 PUBLIC CHAT ADMISSION GATE AUDIT

- Class: `PublicChatAdmissionGate` in `core_model/eval/public_chat_admission_gate.py`.
- Invariant: Production release success alone does NOT authorize public chat admission. Requires explicit HMAC-SHA256 `SignedPublicChatAdmissionToken`. Fails closed (`public_chat_eligible = FALSE`) on any single missing requirement.
