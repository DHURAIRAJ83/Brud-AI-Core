# 13 SECURITY AUDIT

- Secret Isolation: Provider API keys restricted to environment variables.
- CLI Bypass: Sealed via Signed Training Gate.
- Tool Permissions: Executed via `core_model/tool_gateway/` allowlist.
