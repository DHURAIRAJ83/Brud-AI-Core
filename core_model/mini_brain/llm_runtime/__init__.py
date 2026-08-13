"""MB-28: Real Mini Brain LLM Runtime & Admin Assistant Intelligence
Layer -- pure policy/planning helpers only. Every module here is
deterministic and side-effect free.

Real model inference (llama-cpp-python) and real outbound HTTP to
external chat-completion providers do NOT live in this package --
they live in `backend/services/mini_brain_llm_adapter.py`, the same
"one designated impure exception module" pattern MB-25's
`timeout_runner.py`, MB-26's speech/TTS backends, and MB-27's
`secret_encryptor.py` already established, keeping this package's
"never httpx/subprocess/sqlite3/os-execution" rule unconditional.

This phase does not touch the separate, pre-existing "Phase 8" Admin
Assistant system (`backend/services/admin_assistant_service.py`,
`admin_assistant_chat_service.py`, `admin_assistant_tools.py`,
`core_model/admin_assistant/action_registry.py`) at all -- MB-28 is a
new, additive, parallel capability living under its own
`/admin/mini-brain/llm-runtime` route prefix.
"""
