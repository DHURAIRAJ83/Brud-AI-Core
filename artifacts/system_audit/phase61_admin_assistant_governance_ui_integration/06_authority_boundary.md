# 06 AUTHORITY BOUNDARY REPORT

- **Authority Model**: `ADMIN_ASSISTANT_AUTHORITY = ADVISORY_ONLY`.
- **Enforcement**: The Admin Assistant API endpoints remain strictly read-only and proposal-drafting only.
- **UI Safeguards**: No UI controls exist in the Admin Assistant to execute training, promote candidates, activate production, sign tokens, or rotate secrets.
- **Notice Banner**: Both `AdminAssistantPage.jsx` and `AdminAssistantWidget.jsx` display prominent notice banners emphasizing that the Admin Assistant provides status & guidance only.
