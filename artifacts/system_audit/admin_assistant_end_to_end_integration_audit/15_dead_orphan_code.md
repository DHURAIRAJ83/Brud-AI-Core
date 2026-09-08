# 15 DEAD / ORPHAN CODE AUDIT

- Orphan Paths: None. All python modules compile and are covered by the 312 master regression tests.
- Disconnected UI Paths: `POST /api/admin/assistant/chat` (tool-using agent) is disconnected in the UI widget in favor of `/api/admin/mini-brain/llm-runtime/chat`.
