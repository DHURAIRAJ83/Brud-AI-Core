# Phase 20 — MCP-Ready Contract & Security Boundary

## 1. The contract (`core_model/tool_gateway/mcp_contract.py`)

`ToolDescriptor`, `ToolInvocationRequest`, `ToolInvocationResult`,
`ToolPermissionContext`, `ToolExecutionError` — a stable internal
shape every current and future tool source must satisfy. Three
`source` values distinguish where a tool comes from:
`built_in_deterministic` (the only one with a real, executing
implementation this phase — calculator/unit_conversion/
date_time_arithmetic), `internal_service` (defined, empty — future
approved internal services), `external_mcp` (defined, empty, and
structurally refused — see §2).

`ToolPermissionContext.external_mcp_enabled` defaults `False`
(`Settings.external_mcp_enabled`, `BRUD_EXTERNAL_MCP_ENABLED`). No
public or Admin API in this phase accepts an external MCP server
configuration — the flag exists only so a future phase has one
documented, auditable place to eventually change it.

## 2. Proof external MCP is disabled

Three independent layers, not one:

1. **No registry entry exists.** `deterministic_tool_registry.py`'s
   `TOOL_DESCRIPTORS` tuple contains exactly the three built-in tools
   — there is no code path that could construct an `external_mcp`
   descriptor at all in this phase. `get_tool_descriptor("anything else")`
   always returns `None`.
2. **Unconditional refusal if one ever existed.**
   `DeterministicToolExecutionService.execute()`:
   ```python
   # `context.external_mcp_enabled` is deliberately never consulted here --
   # any `external_mcp`-sourced descriptor is refused unconditionally in
   # this phase.
   if descriptor.source == "external_mcp":
       raise ToolExecutionError("mcp_disabled")
   ```
   The flag is not even checked — refusal is unconditional regardless
   of its value.
3. **No public tool-name passthrough.** `select_tool_for_request()`
   only ever returns one of three fixed strings or `None` — a public
   user's free text can never select an arbitrary tool name, MCP or
   otherwise.

Verified live: `GET /api/chat/capabilities` and the Admin `Health`/
`MCP Readiness` tabs all report `external_mcp_enabled: false` against
the real running server; `get_mcp_readiness_summary` (Admin Assistant
tool) reports `internal_service_tools: []`/`external_mcp_tools: []`
alongside the three active built-in tools. A dedicated structural test
confirms `ToolInvocationRequest` has no field a caller could use to
specify an arbitrary server/endpoint — only a `tool_name` string
resolved against the closed registry.

## 3. Tool permission tiers

`public_safe_deterministic` (all three built-in tools),
`admin_read_only` (the read-only Admin Assistant tools/Admin API GETs),
`disabled` (the conceptual tier every `external_mcp`/hypothetical
risky tool sits in — no descriptor is defined at that tier this
phase). Explicitly never defined or enabled in this phase's registry:
`file_write`, `shell`, browser automation, `email`, `calendar`,
`payment`, database mutation, system configuration. Full tool-
permission governance (dynamic tier assignment, risk scoring,
approval workflows for higher tiers) is Phase 22's own scope.

## 4. Admin Assistant boundary

The 5 new proposal actions (`propose_trusted_web_policy_issue`,
`propose_source_block`, `propose_source_allowlist_review`,
`propose_tool_enablement_review`, `propose_tool_permission_issue`) are
**all** record/flag-only:

- The two trusted-web-policy ones write a real, auditable
  `trusted_web_policy_events` row (`issue_flagged`/
  `source_block_proposed`/`allowlist_review_proposed`) but never touch
  `config/trusted_web_policy.json` on disk — proven by a dedicated
  test asserting the policy's checksum is byte-identical before and
  after a confirmed-and-executed `propose_source_block` action.
- The two tool-registry ones return a descriptive result (persisted
  via the existing, generic `admin_assistant_actions` audit trail —
  every action already gets one regardless of executor) but never
  mutate `deterministic_tool_registry.py`'s fixed, code-level
  `TOOL_DESCRIPTORS` — proven by a dedicated test asserting
  `get_tool_descriptor("calculator")` is byte-identical before and
  after a confirmed-and-executed `propose_tool_enablement_review`
  action.

None of the 5 can reveal an API key (verified: `get_trusted_web_health`/
`get_trusted_web_providers`-equivalent tools never include `api_key`/
`base_url` in their output), enable a paid provider, enable arbitrary
MCP, execute an arbitrary URL, enable shell/file-write tools, or
change a production model/RAG assignment — none of these operations
exist anywhere in the 5 new executors' code paths at all, not merely
blocked by a runtime check.

## 5. Defense in depth summary

| Layer | Mechanism |
|---|---|
| URL/network | `validate_fetch_url()` — scheme, credentials, hostname, domain scope, DNS/IP safety, re-validated per redirect hop |
| Content | Content-type allowlist, byte-size bound, no script execution (extraction strips, never runs) |
| Evidence | Injection filter (3rd extension of the RAG→conversation→Web lineage), privacy scan before any persistence or public quoting |
| Tool input | Deterministic regex extraction (never guesses), JSON-schema-shaped required-field validation |
| Tool execution | AST allowlist (calculator), explicit unit tables (conversion), ISO-8601-only parsing (dates) — no `eval`/`exec`/shell/subprocess anywhere in this phase's code |
| Tool registry | Closed, hand-written, three entries — no reflection, no dynamic import, no plugin loading |
| MCP | No registry entry can exist; unconditional refusal even if one did; flag never gates anything that currently executes |
| Admin Assistant | Every write is propose→preview→confirm-with-stale-check→execute→verify→audit; the 5 new actions never mutate policy/registry state, only record proposals |
