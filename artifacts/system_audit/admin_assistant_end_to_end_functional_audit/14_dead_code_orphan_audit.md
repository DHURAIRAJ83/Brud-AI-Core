# 14 DEAD CODE & ORPHAN CODE AUDIT

- Core Modules: 0 un-imported or dead modules in `core_model/` (312 master regression tests cover all modules).
- Route Coverage: 94 route modules active.
- Un-invoked UI Route: `/api/admin/assistant/chat` (tool-using agent) exists in backend but the floating widget chat calls `/mini-brain/llm-runtime/chat` directly.
