"""MB-27: Brud AI Secrets & Provider Settings UI -- pure policy/
planning helpers only. Every module here is deterministic and
side-effect free, except `secret_encryptor.py`, the one explicit
exception this phase's own spec names: it reads the encryption key
from an environment variable, and otherwise performs only CPU-only
Fernet cryptography given that key -- never a database write, never a
network call, never a subprocess.

Real outbound HTTP to third-party provider APIs (OpenAI, Anthropic,
Gemini, OpenRouter) does NOT live in this package at all -- it lives in
`backend/services/provider_settings_connection_adapters.py`, the same
place `external_ai_provider_client.py` (MB-21) already puts this class
of adapter, keeping this package's "never httpx/requests" rule
unconditional with zero additional exceptions.
"""
