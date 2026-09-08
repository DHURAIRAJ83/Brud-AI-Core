# 07 MODEL PROVIDER INTEGRATION AUDIT

- Supported Providers: Ollama, Gemini, OpenRouter, Groq, Claude, BrudMiniLLM.
- Dashboard Access: `ProviderSettingsTab.jsx`, `ExternalDataProvidersPage.jsx` (`END_TO_END_CONNECTED`).
- Admin Assistant Access: `assistantHealth()` queries LLM status (`END_TO_END_CONNECTED`).
- Chat Provider Switcher: `NOT_CONNECTED` via chat tools.
