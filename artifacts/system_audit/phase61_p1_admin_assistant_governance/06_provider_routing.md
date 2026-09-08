# 06 PROVIDER ROUTING

- Adapter Interface: `backend/services/external_ai_provider_client.py` (`ProviderClientProtocol`).
- Supported Providers: OpenRouter, OpenAI, Claude (Anthropic), Ollama, Groq, Gemini.
- Security: API keys read strictly from environment variables; zero logging of credentials.
