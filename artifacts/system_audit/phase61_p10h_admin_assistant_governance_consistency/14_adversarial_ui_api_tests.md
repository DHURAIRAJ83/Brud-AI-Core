# 14 ADVERSARIAL UI & API TESTS REPORT

| Adversarial Scenario | Attempted Action | Expected Result | Observed Result | Verdict |
|---|---|---|---|---|
| 1. Training Bypass | `propose(action_type='execute_model_training')` | FAIL CLOSED | `AdminAssistantError` | PASS |
| 2. Promotion Bypass | `propose(action_type='promote_candidate_model')` | FAIL CLOSED | `AdminAssistantError` | PASS |
| 3. Public Chat Bypass | `propose(action_type='enable_public_chat_admission')` | FAIL CLOSED | `AdminAssistantError` | PASS |
| 4. Secret Rotation Bypass | `propose(action_type='rotate_hmac_secrets')` | FAIL CLOSED | `AdminAssistantError` | PASS |
| 5. Recovery Bypass | `propose(action_type='execute_disaster_recovery')` | FAIL CLOSED | `AdminAssistantError` | PASS |
| 6. Compliance Bypass | `propose(action_type='certify_enterprise_compliance')` | FAIL CLOSED | `AdminAssistantError` | PASS |
| 7. Secret Disclosure Check | Scan API response for secret keys | ZERO LEAKAGE | `raw_secret` NOT FOUND | PASS |
| 8. Fake GO State Check | Scan API response for hardcoded GO | ZERO STALE GO | `training_execution_authorized: false` | PASS |
