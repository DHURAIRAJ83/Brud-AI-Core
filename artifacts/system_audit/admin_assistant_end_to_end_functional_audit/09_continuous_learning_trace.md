# 09 CONTINUOUS LEARNING FLOW TRACE

- Feedback Collection: Submitted via `POST /api/admin/assistant/feedback` -> stored in `AdminAssistantContextRepository`.
- Continuous Learning Pipeline: `mini_brain_continuous_learning.py` processes feedback candidates.
- Dashboard Visibility: `ContinuousLearningTab.jsx` and `ContinuousLearningCenterTab.jsx` display candidates and learning queues (`END_TO_END_CONNECTED`).
- Chat Visibility: `DASHBOARD_ONLY` (Chat does not invoke learning supervisor tools).
