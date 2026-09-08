# 04 PROVIDER RUNTIME & ROUTING TRACE

- Provider Adapters: Ollama, Gemini, OpenRouter, Groq, Claude, BrudMiniLLM.
- Provider Management: Configured via `ProviderSettingsTab.jsx` -> `POST /api/admin/mini-brain/provider-settings`.
- Diagnostic Status: `/api/admin/assistant/health` and `/api/admin/mini-brain/llm-runtime/diagnostics` return real provider availability.
- Credential Safety: API keys and HMAC signing keys are never exposed in logs, manifests, or API responses.
