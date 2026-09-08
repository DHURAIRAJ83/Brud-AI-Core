# 19 HUMAN AUTHORIZATION PACKAGE MATRIX

| Authorization | Required | Present | Valid | Authorized Role | Bound Correctly | Replay Safe | Status |
| ------------- | -------- | ------- | ----- | --------------- | --------------- | ----------- | ------ |
| Training | YES | NO | NO | HUMAN_ADMIN | YES | YES | BLOCKED_PENDING_HUMAN_SIGNATURE |
| Promotion | YES | NO | NO | HUMAN_ADMIN | YES | YES | BLOCKED_PENDING_HUMAN_SIGNATURE |
| Public Chat | YES | NO | NO | HUMAN_ADMIN | YES | YES | BLOCKED_PENDING_HUMAN_SIGNATURE |
| Compliance | YES | NO | NO | HUMAN_ADMIN/LEGAL_OFFICER | YES | YES | BLOCKED_PENDING_HUMAN_SIGNATURE |
| Recovery | YES | NO | NO | HUMAN_ADMIN | YES | YES | RECOVERY_UNEXECUTED |
| Rollback | YES | YES | YES | SYSTEM_OPERATOR/HUMAN_ADMIN | YES | YES | READY_FOR_EMERGENCY |
