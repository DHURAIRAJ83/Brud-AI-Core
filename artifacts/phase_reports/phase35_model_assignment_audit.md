# Phase 35 — Model Assignment & Scoping Audit

## 1. Scoped Assignment Architecture
- **Resolver**: [`backend/services/public_model_assignment_resolver.py`](file:///home/dhurai/Projects/brud-ai/backend/services/public_model_assignment_resolver.py)
- **Scope Restriction**: Only assignments linked to `inference_assignment_scopes` with `scope_key = 'public_chat'`, `enabled = 1`, and `status = 'active'` can be resolved by Public Chat.
- **Admin Isolation**: Admin diagnostic or internal canary assignments (`scope_key = 'admin_diagnostic'`) cannot be resolved or accessed by Public Chat requests.
- **Master Kill-Switch**: `Settings.public_chat_model_enabled` allows immediate disablement of public model inference at runtime without database mutations.
